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


from . import Language
from ..data.corpus.jpn import load_dev_sentence_ids, _lookup_tokenizer, _lemma_extractor


JPN = Language('jpn', 'Japanese',
               loader=load_dev_sentence_ids,
               tokenizer=_lookup_tokenizer,
               max_sentence_samples=None,
               extractor=_lemma_extractor,
               parallel_extractor=_lemma_extractor)

# TODO Merge with JPN
JPN_UNSEEN = Language('jpn_unseen', 'Japanese',
                      loader=None,
                      tokenizer=lambda x: x,
                      max_sentence_samples=None,
                      extractor=_lemma_extractor,
                      parallel_extractor=_lemma_extractor)
