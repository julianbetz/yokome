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


"""Script to optimize language model hyperparameters."""


import sys
import os
import click
from itertools import count
from datetime import datetime
import json
import sqlite3 as sql
import numpy as np
from numpy.random import RandomState
# np.set_printoptions(threshold=sys.maxsize)
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
import tensorflow as tf
tf.logging.set_verbosity(tf.logging.ERROR)
from hyperopt import hp, fmin, tpe, Trials, STATUS_OK
from hyperopt.pyll import scope


_PROJECT_ROOT = os.path.abspath(os.path.dirname(os.path.abspath(__file__))
                                + '/../..')

if _PROJECT_ROOT not in sys.path:
    sys.path.append(_PROJECT_ROOT)
from yokome.language import Language
from yokome.features.corpus import generate_lemma_vocabulary, generate_graphic_character_vocabulary, generate_phonetic_character_vocabulary, load_sentence
from yokome.models.cross_validation import cross_validate
from yokome.util.math import prod
from yokome.util.collections import shuffle
from yokome.util.progress import ProgressBar


MODELS = _PROJECT_ROOT + '/models'
HYPEROPT = _PROJECT_ROOT + '/hyperparameter_optimization'
HYPERPARAM_SPACE = {'embedding_size':
                    hp.qloguniform('embedding_size', 3.0, 7.0, 1),
                    'lstm_size':
                    hp.qloguniform('lstm_size', 3.0, 5.0, 1),
                    'dense_sizes':
                    hp.qloguniform('dense_sizes', 3.0, 5.0, 1)}
HYPERPARAM_TRANSFORMS = {'embedding_size': int,
                         'lstm_size': int,
                         'dense_sizes': lambda x: (int(x),)}
assert set(HYPERPARAM_SPACE) == set(HYPERPARAM_TRANSFORMS)


def _transform_hyperparams(hyperparams):
    return {hyperparam: HYPERPARAM_TRANSFORMS[hyperparam](value)
            for hyperparam, value in hyperparams.items()}


_HYPEROPT_SEED = 1305247952
_MODEL_SEED = 413483266


@click.command()
@click.option('--dump_dir', '-d', default=None, type=str,
              help='Where to store model data.')
@click.option('--language', '--lang', '-l', type=str, required=True,
              help='The language for which to train models.')
@click.option('--max_hyperparam_sets', '-p', default=100,
              help='The maximum number of hyperparameter sets to try during hyperparameter optimization.',
              show_default=True)
@click.option('--n_seeds', '-s', default=5,
              help='The number of seeds to average over for one hyperparameter set during hyperparameter optimization.',
              show_default=True)
@click.option('--n_samples', '-n', default=None, type=int,
              help='The number of samples to use in k-fold cross-validation from the development portion of the dataset. If not specified, the whole development portion is used.')
@click.option('--n_splits', '-k', default=5,
              help='The number k of splits for cross-validation.',
              show_default=True)
@click.option('--evl_size', '-z', default=0.25,
              help='The proportion of the non-validation data to use for evaluation for each fold in cross-validation. The remaining non-validation data of this fold is used as training data.',
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
              help='The minimum portion of tokens of the non-validation data of each fold that is covered by words known to the language model. The remaining tokens are considered unknown words.',
              show_default=True)
@click.option('--verbose/--silent', '-v/', default=False,
              help='Whether to print out detailed progress information.',
              show_default=True)
@click.option('--dashboard_port', '-t', default=6006,
              help='The port on which to serve tensorboard.',
              show_default=True)
def main(dump_dir, language, max_hyperparam_sets, n_seeds, n_samples, n_splits, evl_size, max_epochs, batch_size, max_generalization_loss, min_coverage, verbose, dashboard_port):
    if dump_dir is None:
        dump_dir = HYPEROPT + datetime.now().strftime('/%Y-%m-%d_%H:%M:%S.%f')
    language = Language.by_code(language)
    if verbose:
        print('Loading sentences...')
    # Preload, only incurs long processing time the first time it is called
    max_samples = len(language.load())
    if verbose:
        print('Hyperparameter optimization:')
        for param, value in (('Dump directory:', repr(dump_dir)),
                             ('Language:', language),
                             ('Max trials:', max_hyperparam_sets),
                             ('Seeds:', n_seeds),
                             ('Samples:', max_samples if n_samples is None else n_samples),
                             ('Splits:', n_splits),
                             ('Evaluation set portion:', evl_size),
                             ('Max epochs:', max_epochs),
                             ('Batch size:', batch_size),
                             ('Max generalization loss:', max_generalization_loss),
                             ('Min token coverage:', min_coverage)):
            print('    %-24s %s' % (param, value))
        print('\n    Serving tensorboard on port %d\n' % (dashboard_port,))
    # XXX Dump meta information to meta.json
    os.makedirs(dump_dir, exist_ok=True)
    trial_index = count(1)

    def objective(hyperparams):
        hyperparams = _transform_hyperparams(hyperparams)
        trial_id = next(trial_index)
        trial_dir = dump_dir + ('/trial_%d' % (trial_id,))
        if verbose:
            print('    Trial %d:' % (trial_id,))
            max_param_name_length = max(len(param) for param in hyperparams)
            print('\n'.join(('        %%-%ds %%s' % (max_param_name_length + 1,)) % (param + ':', value) for param, value in sorted(hyperparams.items())) + '\n')
        try:
            with open(trial_dir + '/report.json', 'r') as f:
                report = json.load(f)
        except OSError:
            pass
        else:
            if verbose:
                print('        Loss: %g\n' % (report['loss'],))
            return report
        os.makedirs(trial_dir, exist_ok=True)
        with open(trial_dir + '/hyperparams.json', 'w') as f:
            json.dump(hyperparams, f)
        total_loss = 0
        r = RandomState(_MODEL_SEED)
        for i in range(1, n_seeds + 1):
            seed_dir = trial_dir + ('/seed_%d' % (i,))
            if verbose:
                print('        Seed %d:' % (i,))
            try:
                with open(seed_dir + '/report.json', 'r') as f:
                    total_loss += json.load(f)['loss']
            except OSError:
                pass
            else:
                # For reproducibility, use the random number generator the same
                # number of times as in the case that the file was not found
                r.randint(0x100000000)
                continue
            os.makedirs(seed_dir, exist_ok=True)
            loss = cross_validate(
                seed_dir, language,
                n_samples, n_splits, evl_size, max_epochs, batch_size,
                max_generalization_loss, min_coverage,
                hyperparams,
                seed=r.randint(0x100000000),
                verbose=verbose,
                dashboard_port=dashboard_port)
            with open(seed_dir + '/.tmp.report.json', 'w') as f:
                json.dump({'loss': loss}, f)
            os.replace(seed_dir + '/.tmp.report.json', seed_dir + '/report.json')
            total_loss += loss
        report = {'loss': total_loss / n_seeds, 'status': STATUS_OK}
        # Write results to disc. Ensure this happens atomically
        with open(trial_dir + '/.tmp.report.json', 'w') as f:
            json.dump(report, f)
        os.replace(trial_dir + '/.tmp.report.json', trial_dir + '/report.json')
        if verbose:
            print('\n        Loss: %g\n' % (report['loss'],))
        return report

    trials = Trials()
    best_hyperparams = fmin(fn=objective,
                            space=HYPERPARAM_SPACE,
                            algo=tpe.suggest,
                            max_evals=max_hyperparam_sets,
                            trials=trials,
                            rstate=RandomState(_HYPEROPT_SEED),
                            show_progressbar=verbose)
    best_hyperparams = _transform_hyperparams(best_hyperparams)
    with open(dump_dir + '/best_hyperparams.json', 'w') as f:
        json.dump(best_hyperparams, f)
    if verbose:
        print('\n    Best hyperparameters:')
        max_param_name_length = max(len(param) for param in best_hyperparams)
        for hyperparam, value in sorted(best_hyperparams.items()):
            print(('        %%-%ds %%s' % (max_param_name_length + 1,)) % (hyperparam + ':', value))


if __name__ == '__main__':
    main()
