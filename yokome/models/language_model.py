# -*- coding: utf-8 -*-

# Copyright 2019 Julian Betz
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#      http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import sys
import os
from datetime import datetime
import glob
import shutil
from collections.abc import Iterable, Mapping
import math
import numpy as np
from numpy.random import RandomState
import sklearn
import tensorflow as tf
from tensorflow.train import SessionRunHook, get_or_create_global_step
from tensorflow.estimator import Estimator, EstimatorSpec, ModeKeys, RunConfig
from tensorflow.data import Dataset
from tensorflow.contrib.cudnn_rnn import CudnnCompatibleLSTMCell
from tensorflow.contrib.layers import xavier_initializer
from tensorflow.contrib.estimator import stop_if_no_decrease_hook
import pickle


from ..language import Language
from ..features.symbol_stream import enumerate_alternatives, sample_alternatives
from ..util.math import prod
from ..util.progress import print_progress


class SaverHook(SessionRunHook):
    """A helper class that allows to save the model to one directory during training
    and to provide the best model from a different directory for production
    mode.

    """

    def __init__(self, model_dir):
        self._model_dir = model_dir


    def end(self, session):
        session.graph.get_collection('savers')[0].save(
            session,
            self._model_dir + '/model.ckpt',
            get_or_create_global_step(session.graph))


class LanguageModel:
    """A neural language model that estimates the probability of a sentence.
    
    :param str model_dir: Where to store all relevant model data.  If
        ``None``, a generic location based on the current date and time will
        be used.

    :param dict params: The model parameters.

    :param int seed: The seed to use for the underlying Tensorflow graph.

    :param str warm_start_from: A directory containing model parameter
        values for initialization.

    :param bool production_mode: Whether to use the production or the
        training model.

    :param int save_summary_steps: The periodicity at which to save
        summaries.

    :param int keep_checkpoint_max: The maximum number of recent checkpoint
        files to keep.

    :param yokome.language.Language language: The language of the language model.

    :param vocabulary: A mapping from input units to integer values, or a
        sequence of input units.  This is used to encode the incoming data
        numerically.  If ``None``, a pickled mapping is expected to be found
        in the model directory, named ``encoder.pickle``.  Every input unit
        that is not found in this vocabulary is considered to be an
        out-of-vocabulary unit.
    
    """

    def __init__(self, model_dir=None, params=None, seed=None, warm_start_from=None, production_mode=False, *, save_summary_steps=100, keep_checkpoint_max=5, language=None, vocabulary=None):
        if not isinstance(language, Language):
            raise TypeError(type(language).__name__)
        if model_dir is None:
            model_dir = os.path.abspath(
                os.path.dirname(os.path.abspath(__file__))
                + '/../../models'
                + datetime.now().strftime('/%Y-%m-%d_%H:%M:%S.%f'))
        self._ESTIMATOR = Estimator(
            model_fn=self.model_fn,
            config=RunConfig(model_dir=model_dir + ('/best_model' if production_mode else '/training'),
                             tf_random_seed=seed,
                             save_summary_steps=save_summary_steps,
                             # Force tensorflow to only save checkpoints after
                             # full epochs
                             save_checkpoints_steps=(None if production_mode else np.inf),
                             save_checkpoints_secs=None,
                             keep_checkpoint_max=keep_checkpoint_max,
                             keep_checkpoint_every_n_hours=np.inf,
                             log_step_count_steps=save_summary_steps),
            params=params,
            warm_start_from=warm_start_from)
        self._language = language
        if vocabulary is None:
            with open(model_dir + '/encoder.pickle', 'rb') as f:
                self._ENCODER = pickle.load(f)
        else:
            if isinstance(vocabulary, Mapping):
                self._ENCODER = vocabulary
            elif isinstance(vocabulary, Iterable):
                self._ENCODER = dict()
                for word in vocabulary:
                    if word not in self._ENCODER:
                        self._ENCODER[word] = len(self._ENCODER) + 1
            else:
                raise TypeError('Vocabulary cannot be of type %r'
                                % (type(vocabulary).__name__,))
            os.makedirs(model_dir, exist_ok=True)
            with open(model_dir + '/encoder.pickle', 'wb') as f:
                pickle.dump(self._ENCODER, f, pickle.HIGHEST_PROTOCOL)
        self._INPUT_DTYPES = ({'ids': tf.int64,
                               'length': tf.int64,
                               'n': tf.int64,
                               'contribution': tf.float32},
                              tf.int64)
        self._INPUT_SHAPES = ({'ids': tf.TensorShape((None,)),
                               'length': tf.TensorShape(()),
                               'n': tf.TensorShape(()),
                               'contribution': tf.TensorShape(())},
                              tf.TensorShape(()))
        self._INPUT_PADDING = ({'ids': np.array(len(self._ENCODER) + 1, dtype=np.int64),
                                'length': np.array(0, dtype=np.int64),
                                'n': np.array(1, dtype=np.int64),
                                'contribution': np.array(1.0, dtype=np.float32)},
                               np.array(0, dtype=np.int64))
        # self._INPUT_DUMMY = ({'ids': np.empty((0, 1), dtype=np.int64),
        #                       'length': np.empty((0,), dtype=np.int64),
        #                       'n': np.empty((0,), dtype=np.int64),
        #                       'contribution': np.empty((0,), dtype=np.float32)},
        #                      np.empty((0,), dtype=np.int64))

        # XXX Train once on batch of size zero to force tensorflow to initialize
        # variables and establish a checkpoint


    def _encode(self, words):
        return np.array((len(self._ENCODER) + 1,) # Beginning/end of sentence
                        + tuple(self._ENCODER[word]
                                if word in self._ENCODER
                                else 0  # Unknown word
                                for word in words),
                        dtype=np.int64)


    def model_fn(self, features, labels, mode, params):
        # tf.random.set_random_seed(params['seed'])

        ids = features['ids']

        # Embedding layer
        embeddings = tf.Variable(tf.random.uniform(
            (len(self._ENCODER) + 2, params['embedding_size']),
            -1.0,
            1.0,
            tf.float32))
        layer = tf.nn.embedding_lookup(embeddings, ids)

        # LSTM layer
        lengths = features['length']
        # XXX Use keras layers instead
        layer, _ = tf.nn.dynamic_rnn(
            CudnnCompatibleLSTMCell(params['lstm_size']),
            layer,
            lengths,
            dtype=tf.float32)

        # MLP layers
        for n_units in params['dense_sizes']:
            layer = tf.layers.dense(
                layer,
                n_units,
                activation=tf.nn.relu,
                kernel_initializer=xavier_initializer(),
                bias_initializer=tf.zeros_initializer())

        # Softmax layer
        layer = tf.layers.dense(
            layer,
            len(self._ENCODER) + 2,
            activation=None,
            kernel_initializer=xavier_initializer(),
            bias_initializer=tf.zeros_initializer())
        labels = tf.concat((ids[:, 1:], ids[:, :1]), 1)
        mask = tf.sequence_mask(lengths, dtype=tf.float32)
        layer = (tf.nn.sparse_softmax_cross_entropy_with_logits(logits=layer,
                                                                labels=labels)
                 * mask)

        if mode == ModeKeys.PREDICT:
            return EstimatorSpec(mode, predictions={
                'log2_word_probs': -layer,
                'log2_sentence_prob': -tf.reduce_sum(layer, 1),
                'length': lengths,
                'n': features['n'] #,
                # 'global_step': tf.identity(get_or_create_global_step())
            })
        
        contribution = tf.reshape(features['contribution'], (-1, 1))
        loss = tf.reduce_sum(layer * contribution) / tf.reduce_sum(mask)

        if mode == ModeKeys.EVAL:
            return EstimatorSpec(mode, loss=loss)
        
        elif mode == ModeKeys.TRAIN:
            train_op = tf.train.AdamOptimizer().minimize(
                loss, global_step=get_or_create_global_step())

            train_op = tf.group(
                # tf.print(ids),
                train_op)
            return EstimatorSpec(mode, loss=loss, train_op=train_op)


    def _provide_features(self, sentences, sample_size):
        for sentence in sentences:
            sentence = list(self._language.tokenize(sentence))
            if sample_size > 0:
                graphic_originals = ''.join(
                    candidates[0]['surface_form']['graphic']
                    for candidates in sentence
                    if 'surface_form' in candidates[0])
                phonetic_originals = ''.join(
                    candidates[0]['surface_form']['phonetic']
                    for candidates in sentence
                    if 'surface_form' in candidates[0])
                graphic_substitutes = ''.join(
                    candidates[0]['lemma']['graphic']
                    for candidates in sentence
                    if 'surface_form' not in candidates[0])
                phonetic_substitutes = ''.join(
                    candidates[0]['lemma']['phonetic']
                    for candidates in sentence
                    if 'surface_form' not in candidates[0])
                seed = (hash((graphic_originals,
                              phonetic_originals,
                              graphic_substitutes,
                              phonetic_substitutes))
                        % 0x100000000)
                n = sample_size
                sentence = sample_alternatives(sentence, n, seed)
            else:
                n = prod(len(candidates) for candidates in sentence)
                sentence = enumerate_alternatives(sentence)
            contribution = 1 / n
            for tokens in sentence:
                ids = self._encode(self._language.extract(tokens))
                yield ({'ids': ids,
                        'length': np.array(ids.shape[0], dtype=np.int64),
                        'n': np.array(n, dtype=np.int64),
                        'contribution': np.array(contribution, dtype=np.float32)},
                       np.array(0, dtype=np.int64))


    def _input_fn(self, sentences, batch_size, sample_size=0):
        # if batch_size <= 0:
        #     raise ValueError('Batch size must be positive')
        dataset = Dataset.from_generator(
            lambda: self._provide_features(sentences, sample_size),
            self._INPUT_DTYPES,
            self._INPUT_SHAPES)
        dataset = dataset.padded_batch(
            batch_size,
            self._INPUT_SHAPES,
            self._INPUT_PADDING)
        return dataset


    def train(self, trn_set, evl_set, max_epochs=1, batch_size=1, max_generalization_loss=None, shuffle=False, random_state=None, verbose=False):
        """Train the model.

        :param trn_set: A sequence of sentences, a training set.  Each
            sentence will be tokenized using the language object provided at
            language model creation.

        :param trn_set: A sequence of sentences, an evaluation set.  Each
            sentence will be tokenized using the language object provided at
            language model creation.

        :param int max_epochs: The maximum number of epochs to train for.  The
            actual number of epochs may be less if the training process stops
            early.

        :param int batch_size: The number of sentences to estimate the
            probability for in parallel.

        :param float max_generalization_loss: The maximum generalization loss at
            which the training process is still continued.

        :param bool shuffle: Whether to shuffle the samples for each epoch.

        :param random_state: The random state used for shuffling.  May be a
            :class:`numpy.RandomState` instance, an ``int`` seed, or ``None``.
            If ``None``, an unseeded pseudo-random number generator will be
            used.

        :param bool verbose: Whether to show progress indicators.

        """
        if verbose:
            print('Training language model:')
        current_model_dir = os.path.abspath(self._ESTIMATOR.model_dir
                                            + '/../current_model')
        best_model_dir = os.path.abspath(self._ESTIMATOR.model_dir
                                         + '/../best_model')
        if os.path.exists(best_model_dir) or os.path.exists(current_model_dir) or glob.glob(self._ESTIMATOR.model_dir + '/*'):
            # XXX Prompt user
            if verbose:
                print('    Overriding model in %r' % (os.path.dirname(self._ESTIMATOR.model_dir),))
            for directory in (best_model_dir, current_model_dir, self._ESTIMATOR.model_dir):
                try:
                    shutil.rmtree(directory)
                except FileNotFoundError as e:
                    pass
        trn_set = tuple(trn_set)
        evl_set = tuple(evl_set)
        if random_state is None or isinstance(random_state, int):
            random_state = RandomState(random_state)
        # XXX Early stopping does currently only take epochs into account that
        # happen during this run of ``train``, but not prior, saved checkpoints
        min_evl_loss = np.inf
        min_evl_loss_epoch = 0
        for _ in (print_progress(range(max_epochs),
                                 prefix=lambda i, element: '    |',
                                 suffix=lambda i, element: '| Epoch %d '
                                 % (i if element is None else i + 1,))
                  if verbose
                  else range(max_epochs)):
            sentences = (sklearn.utils.shuffle(trn_set,
                                               # Ensure that ``random_state`` is run exactly once per epoch
                                               random_state=random_state.randint(0x100000000))
                         if shuffle
                         else trn_set)
            os.makedirs(current_model_dir, exist_ok=False)
            # Train for one epoch
            self._ESTIMATOR.train(input_fn=lambda:
                                  self._input_fn(sentences,
                                                 batch_size),
                                  hooks=[SaverHook(current_model_dir)],
                                  steps=math.ceil(len(trn_set) / batch_size))
            metrics = self._ESTIMATOR.evaluate(input_fn=lambda:
                                               self._input_fn(evl_set,
                                                              batch_size),
                                               name='evl')
            if min_evl_loss > metrics['loss']:
                # XXX Non-atomic replacement
                try:
                    shutil.rmtree(best_model_dir)
                except FileNotFoundError as e:
                    pass
                os.replace(current_model_dir, best_model_dir)
                min_evl_loss = metrics['loss']
                min_evl_loss_epoch = metrics['global_step']
            else:
                try:
                    shutil.rmtree(current_model_dir)
                except FileNotFoundError as e:
                    pass
            # Early stopping based on generalization loss criterion
            if (max_generalization_loss is not None
                and ((metrics['loss'] - min_evl_loss) / min_evl_loss
                     > max_generalization_loss)):
                if verbose:
                    print('\n    Stopping early')
                break
        return min_evl_loss_epoch


    def validate(self, vld_set, batch_size=1):
        """Evaluate the model performance on a validation set.

        :param vld_set: A sequence of sentences, a validation set.  Each
            sentence will be tokenized using the language object provided at
            language model creation.

        :param int batch_size: The number of sentences to estimate the
            probability for in parallel.

        :return: A dictionary containing the metrics evaluated on the validation
            set.  Contains an entry ``'loss'`` for the loss and an entry
            ``'global_step'`` for the global step for which this validation was
            performed.

        """
        return self._ESTIMATOR.evaluate(input_fn=lambda:
                                        self._input_fn(vld_set,
                                                       batch_size),
                                        name='vld')


    def estimate_probability(self, sentences, batch_size, sample_size=0):
        """Estimate the probability of the specified sentences.

        :param sentences: A sequence of sentences.  Each sentence will be
            tokenized using the language object provided at language model
            creation.

        :param int batch_size: The number of sentences to estimate the
            probability for in parallel.

        :param int sample_size: The number of sentence alternatives to sample.
            If this is greater than zero, for every list of token candidates
            after tokenization, one token candidate is chosen for each sample.
            If it is ``0``, all sentence alternatives (i.e. all combinations of
            token candidates) are enumerated and used for probability
            estimation.

        :return: An iterable over one dictionary per sentence, each of the form
        
            .. code-block:: python
    
               {
                 'log2_word_probs': <word log-probabilities per alternative>,
                 'log2_sentence_probs': <sentence log-probability per alternative>
               }

        """
        aggregation = []
        i = 0
        for prediction in self._ESTIMATOR.predict(
                input_fn=lambda: self._input_fn(sentences,
                                                batch_size,
                                                sample_size)):
            if i <= 0:
                if aggregation:
                    yield {'log2_word_probs': tuple(a['log2_word_probs'] for a in aggregation),
                           'log2_sentence_probs': np.array([a['log2_sentence_prob'] for a in aggregation], dtype=np.float32)}
                    aggregation = []
                i = prediction['n']
            aggregation.append({'log2_word_probs': prediction['log2_word_probs'][:prediction['length']],
                                'log2_sentence_prob': prediction['log2_sentence_prob']})
            i -= 1
        if aggregation:
            yield {'log2_word_probs': tuple(a['log2_word_probs'] for a in aggregation),
                   'log2_sentence_probs': np.array([a['log2_sentence_prob'] for a in aggregation], dtype=np.float32)}


    def training_dir(self):
        """Get the directory where the model for training is stored."""
        return os.path.abspath(self._ESTIMATOR.model_dir + '/../training')


    def production_dir(self):
        """Get the directory where the model for production is stored."""
        return os.path.abspath(self._ESTIMATOR.model_dir + '/../best_model')
