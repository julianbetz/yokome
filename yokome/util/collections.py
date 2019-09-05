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
    """Consistently shuffle sequences, accessing and yielding elements not
    before they are needed.

    :param sequences: Equally long sequences supporting the methods ``__len__``
        and ``__getitem__``.

    :param random_state: The random state to use for shuffling.  May be an
        ``int`` seed for the pseudo-random number generator, a random state
        instance, or ``None`` (in which case ``numpy.random`` is used).

    :param n_samples: The number of samples to generate.  If ``None``, all
        samples are provided.

    :return: An iterable over sequence elements, in randomly permuted order if
        only one sequence is provided.  Otherwise, an iterable over tuples of
        sequence elements, one per sequence.

    """
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
