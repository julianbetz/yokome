#!/usr/bin/python3
# -*- coding: utf-8 -*-

# Copyright 2018, 2019 Julian Betz
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
import math
from collections.abc import Sized


_BLOCKS = (' ', ' ', '▏', '▎', '▍', '▌', '▋', '▊', '▉', '▉')


def print_bar(i, element, iterable_len, *, bar_size, prefix=lambda i, element: '|', suffix=lambda i, element: '|', delimiter='\r', end='\n', file=sys.stdout):
    complete = i / iterable_len * bar_size
    floored = math.floor(complete)
    rest = math.floor((complete - floored) * 8) + 1
    print(prefix(i, element) + '█' * floored
          + _BLOCKS[rest]
          + ' ' * (bar_size - floored - 1) + suffix(i, element),
          end=delimiter if i < iterable_len else end, file=file, flush=True)


def print_progress(iterable, iterable_len=None, *, bar_size=20, prefix=lambda i, element: '|', suffix=lambda i, element: '|', delimiter='\r', end='\n'):
    if iterable_len is None:
        if isinstance(iterable, Sized):
            iterable_len = len(iterable)
        else:
            raise ValueError('Unable to determine length of iterable')
    if not isinstance(iterable_len, int) or iterable_len < 0:
        raise ValueError('Unable to print bar for iterable of size %r'
                         % (iterable_len,))
    for i, element in zip(range(iterable_len), iterable):
        complete = i / iterable_len * bar_size
        floored = math.floor(complete)
        rest = math.floor((complete - floored) * 8) + 1
        print(prefix(i, element) + '█' * floored
              + _BLOCKS[rest]
              + ' ' * (bar_size - floored - 1) + suffix(i, element),
              end='', flush=True)
        yield element
        print(delimiter, end='', flush=True)
    print(prefix(iterable_len, None) + '█' * bar_size + suffix(iterable_len, None), end=end, flush=True)


class ProgressBar:
    def __init__(self, iterable_len, *, bar_size=20, prefix=lambda i, element: '|', suffix=lambda i, element: '|', delimiter='\r', end='\n', file=sys.stdout):
        if not isinstance(iterable_len, int) or iterable_len < 0:
            raise ValueError('Unable to print bar for iterable of size %r'
                             % (iterable_len,))
        self._i = 0
        self._iterable_len = iterable_len
        self._bar_size = bar_size
        self._prefix = prefix
        self._suffix = suffix
        self._delimiter = delimiter
        self._end = end
        self._file = file


    def print_next(self, element=None):
        self._i += 1
        self.print_current(element)


    def print_current(self, element=None):
        if self._i > 0:
            print(self._delimiter, end='', file=self._file, flush=False)
        if self._i < self._iterable_len:
            complete = self._i / self._iterable_len * self._bar_size
            floored = math.floor(complete)
            rest = math.floor((complete - floored) * 8) + 1
            print(self._prefix(self._i, element) + '█' * floored
                  + _BLOCKS[rest]
                  + ' ' * (self._bar_size - floored - 1)
                  + self._suffix(self._i, element),
                  end='', file=self._file, flush=True)
        else:
            print(self._prefix(self._iterable_len, element)
                  + '█' * self._bar_size
                  + self._suffix(self._iterable_len, element),
                  end=self._end, file=self._file, flush=True)
