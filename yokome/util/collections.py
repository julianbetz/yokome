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


import sklearn.utils


def shuffle(*sequences, random_state=None, n_samples=None):
    if len(sequences) <= 0:
        raise ValueError('No sequences specified')
    if any(not hasattr(s, '__len__') or not hasattr(s, '__getitem__')
           for s in sequences):
        raise TypeError("Sequences have to support '__len__' and '__getitem__'")
    length = len(sequences[0])
    if any(len(s) != length for s in sequences):
        raise ValueError('Inconsistent lengths')
    permutation = sklearn.utils.shuffle(range(length),
                                        random_state=random_state,
                                        n_samples=n_samples)
    for i in permutation:
        yield (sequences[0][i]
               if len(sequences) == 1
               else tuple(s[i] for s in sequences))
