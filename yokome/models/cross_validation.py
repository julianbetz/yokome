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
