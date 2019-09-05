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


import os
from subprocess import Popen, DEVNULL
from numpy.random import RandomState
from sklearn.model_selection import train_test_split, KFold
import json

from yokome.features.corpus import generate_vocabulary_from
from yokome.models.language_model import LanguageModel


# XXX Choose different k-folding seed for different datasets
_KFOLD_SEED = 341099899


def kfold(language, n_samples=None, n_splits=5, evl_size=0.25):
    """Create splits of corpus sentences to be used in cross-validation.

    The sentences are loaded using the languages ``load`` method.  The splits
    are performed randomly, and differently for different numbers of samples.

    :param yokome.language.Language language: The language to train on.

    :param int n_samples: The number of sample sentences to load.

    :param int n_splits: The number ``k`` of folds.

    :param float evl_size: The portion of evaluation samples w.r.t. the
        non-validation part of all samples.

    :return: An iterable over triples of tuples over sentences.  Each triple
        consists of the training, evaluation and validation splits,
        respectively.

    """
    sentences = language.load(n_samples)
    # Split differently for different lengths
    r = RandomState(_KFOLD_SEED + len(sentences))
    kfolder = KFold(n_splits=n_splits, shuffle=False)
    for non_vld_indices, vld_indices in kfolder.split(sentences):
        # Randomly permute before splitting so as not to always take the last
        # few samples as the evaluation set
        trn_indices, evl_indices = train_test_split(
            non_vld_indices, test_size=evl_size, random_state=r, shuffle=True)
        yield tuple(tuple(sentences[i] for i in indices)
                    for indices in (trn_indices, evl_indices, vld_indices))


def cross_validate(seed_dir, language,
                   n_samples, n_splits, evl_size, max_epochs, batch_size,
                   max_generalization_loss, min_coverage, hyperparams,
                   seed=None, verbose=False, dashboard_port=6006):
    """Perform cross-validation on the

    The process is designed to be able to continue with minimal additional
    effort after a crash.  It can therefore be stopped and taken up again later.

    Tensorboard is served during each training run.

    :param str seed_dir: Where to store model data for this seed.  If
        cross-validation is performed for multiple seeds, multiple seed
        directories are needed.

    :param yokome.language.Language language: The language to train on.

    :param int n_samples: The number of sample sentences to load.

    :param int n_splits: The number ``k`` of folds.

    :param float evl_size: The portion of evaluation samples w.r.t. the
        non-validation part of all samples.

    :param int max_epochs: The maximum number of epochs to train for.  The
        actual number of epochs may be less if the training process stops early.

    :param int batch_size: The number of sentences to estimate the probability
        for in parallel.

    :param float max_generalization_loss: The maximum generalization loss at
        which the training process is still continued.

    :param min_coverage: The portion of the corpus that has to be covered by the
        minimal vocabulary of the most frequent words that is used to encode
        incoming data.

    :param hyperparams: The model parameters used in this pass of
        cross-validation.

    :param int seed: The seed used for the pseudo-random number generator that
        generates the seeds for the models to be trained.

    :param bool verbose: Whether to print progress indiation.

    :param int dashboard_port: On which port to serve Tensorboard.
    
    :return: The average loss over all folds.

    """
    total_loss = 0
    r = RandomState(seed)
    for i, (trn, evl, vld) in enumerate(kfold(language, n_samples, n_splits, evl_size),
                                        start=1):
        fold_dir = seed_dir + ('/fold_%d' % (i,))
        if verbose:
            print('            Fold %d...' % (i,))
        try:
            with open(fold_dir + '/report.json', 'r') as f:
                total_loss += json.load(f)['loss']
        except OSError:
            pass
        else:
            r.randint(0x100000000)
            r.randint(0x100000000)
            continue
        vocabulary = generate_vocabulary_from(language, trn + evl, min_coverage)
        model_seed = r.randint(0x100000000)
        os.makedirs(fold_dir, exist_ok=True)
        model = LanguageModel(fold_dir,
                              params=hyperparams,
                              seed=model_seed,
                              production_mode=False,
                              language=language,
                              vocabulary=vocabulary)
        tensorboard = Popen(['tensorboard',
                             '--logdir', model.training_dir(),
                             '--port', str(dashboard_port)],
                            stdout=DEVNULL,
                            stderr=DEVNULL)
        model.train(trn, evl, max_epochs, batch_size,
                    max_generalization_loss=max_generalization_loss,
                    shuffle=True, random_state=r.randint(0x100000000),
                    verbose=False)
        # Load the best model
        model = LanguageModel(fold_dir,
                              params=hyperparams,
                              seed=model_seed,
                              production_mode=True,
                              language=language,
                              vocabulary=None)
        loss = float(
            model.validate(vld, batch_size)['loss'])
        with open(fold_dir + '/.tmp.report.json', 'w') as f:
            json.dump({'loss': loss}, f)
        os.replace(fold_dir + '/.tmp.report.json', fold_dir + '/report.json')
        total_loss += loss
        tensorboard.terminate()
        tensorboard.wait()
    return total_loss / n_splits
