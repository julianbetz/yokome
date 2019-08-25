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


class Language:
    _LANGUAGES = dict()


    def __init__(self, code, name, *, loader, tokenizer, max_sentence_samples=None, extractor, parallel_extractor):
        if code in Language._LANGUAGES:
            raise ValueError('Language code has to be unique')
        self._CODE = code
        self._NAME = name
        self._LOADER = loader
        self._TOKENIZER = tokenizer
        self._MAX_SENTENCE_SAMPLES = max_sentence_samples # TODO Remove
        self._EXTRACTOR = extractor
        self._PARALLEL_EXTRACTOR = parallel_extractor
        Language._LANGUAGES[code] = self


    @staticmethod
    def by_code(code):
        return Language._LANGUAGES[code]
        

    @property
    def code(self):
        return self._CODE


    @property
    def load(self):
        return self._LOADER


    @property
    def tokenize(self):
        return self._TOKENIZER


    @property
    def max_sentence_samples(self):
        return self._MAX_SENTENCE_SAMPLES


    @property
    def extract(self):
        return self._EXTRACTOR


    @property
    def extract_parallel(self):
        return self._PARALLEL_EXTRACTOR


    def __repr__(self):
        return '<%s %s>' % (type(self).__name__, self._CODE)


    def __str__(self):
        return self._NAME
