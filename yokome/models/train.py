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
import click
from subprocess import Popen, DEVNULL
from numpy.random import RandomState
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
import tensorflow as tf
tf.logging.set_verbosity(tf.logging.ERROR)
from sklearn.model_selection import train_test_split
import json


PROJECT_ROOT = os.path.abspath(os.path.dirname(os.path.abspath(__file__))
                                + '/../..')
MODEL_DIR = PROJECT_ROOT + '/models'
MASTER_SEED = 1895349505


if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)
from yokome.language import Language
from yokome.features.corpus import generate_vocabulary_from
from yokome.models.language_model import LanguageModel
from yokome.util.persistence import list_as_tuple_hook


@click.command()
@click.option('--dump_dir', '-d', default=None, type=str,
              help='Where to store model data.')
@click.option('--language', '--lang', '-l', type=str, required=True,
              help='The language for which to train the model.')
@click.option('--n_samples', '-n', default=None, type=int,
              help='The number of samples to use in training from the development portion of the dataset. If not specified, the whole development portion is used.')
@click.option('--vld_size', '-Z', default=0.2,
              help='The proportion of samples to use for validation after training. The remaining samples are used as training and evaluation data.',
              show_default=True)
@click.option('--evl_size', '-z', default=0.25,
              help='The proportion of the non-validation data to use for evaluation during training. The remaining non-validation data of this fold is used as training data.',
              show_default=True)
@click.option('--max_epochs', '-e', default=300,
              help='The maximum number of passes over the whole training set. Due to early stopping, the actual number of epochs may differ for each training run.',
              show_default=True)
@click.option('--batch_size', '-b', default=25,
              help='The batch size for training.', show_default=True)
@click.option('--max_generalization_loss', '-g', default=0.4,
              help='The generalization loss up to which training continues. Early stopping is triggered when it is exceeded.',
              show_default=True)
@click.option('--min_coverage', '-c', default=0.98,
              help='The minimum portion of tokens of the non-validation data that is covered by words known to the language model. The remaining tokens are considered unknown words.',
              show_default=True)
@click.option('--hyperparam_file', '-H', type=str, required=True,
              help='A JSON file containing the hyperparameters to use.')
@click.option('--verbose/--silent', '-v/', default=False,
              help='Whether to print out detailed progress information.',
              show_default=True)
@click.option('--dashboard_port', '-t', default=6006,
              help='The port on which to serve tensorboard.',
              show_default=True)
def main(dump_dir, language, n_samples, vld_size, evl_size, max_epochs, batch_size, max_generalization_loss, min_coverage, hyperparam_file, verbose, dashboard_port):
    if dump_dir is None:
        dump_dir = MODEL_DIR + datetime.now().strftime('/%Y-%m-%d_%H:%M:%S.%f')
    language = Language.by_code(language)
    # Preload samples
    if verbose:
        print('Loading sentences...')
    samples = language.load(n_samples)
    with open(hyperparam_file, 'r') as f:
        hyperparams = json.load(f, object_hook=list_as_tuple_hook)
    if verbose:
        print('\nTraining settings:')
        for param, value in (('Dump directory:', repr(dump_dir)),
                             ('Language:', language),
                             ('Samples:', len(samples)),
                             ('Validation set portion:', vld_size),
                             ('Evaluation set portion:', evl_size),
                             ('Max epochs:', max_epochs),
                             ('Batch size:', batch_size),
                             ('Max generalization loss:', max_generalization_loss),
                             ('Min token coverage:', min_coverage)):
            print('    %-24s %s' % (param, value))
        print('    Hyperparameters:')
        max_param_name_length = max(len(param) for param in hyperparams)
        for hyperparam, value in sorted(hyperparams.items()):
            print(('        %%-%ds %%s' % (max_param_name_length + 1,)) % (hyperparam + ':', value))
        print('\n    Serving tensorboard on port %d\n' % (dashboard_port,))
    os.makedirs(dump_dir, exist_ok=True)
    with open(dump_dir + '/meta.json', 'w') as f:
        json.dump({'language': language.code,
                   'n_samples': len(samples),
                   'vld_size': vld_size,
                   'evl_size': evl_size,
                   'max_epochs': max_epochs,
                   'batch_size': batch_size,
                   'max_generalization_loss': max_generalization_loss,
                   'min_coverage': min_coverage,
                   'hyperparams': hyperparams},
                  f)
    r = RandomState(MASTER_SEED)
    non_vld, vld = train_test_split(samples, test_size=vld_size, random_state=r.randint(0x100000000), shuffle=True)
    trn, evl = train_test_split(non_vld, test_size=evl_size, shuffle=False)
    vocabulary = generate_vocabulary_from(language, non_vld, min_coverage)
    model_seed = r.randint(0x100000000)
    # XXX Adapt old hyperparameters
    model = LanguageModel(dump_dir,
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
                verbose=verbose)
    # Load the best model
    model = LanguageModel(dump_dir,
                          params=hyperparams,
                          seed=model_seed,
                          production_mode=True,
                          language=language,
                          vocabulary=None)
    loss = float(
        model.validate(vld, batch_size)['loss'])
    print('\n    Loss: %g' % (loss,))
    tensorboard.terminate()
    tensorboard.wait()


if __name__ == '__main__':
    main()
