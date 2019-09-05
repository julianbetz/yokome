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


"""Provides methods to access the Japanese corpus.

The corpus used is the JEITA Public Morphologically Tagged Corpus (in ChaSen
format).  All data is split into the following data sets:

* Reserve (rsv) set: Not for direct use in this project, but for testing if
  the model creation process might have overfit on every other set.

* Test (tst) set: For a final estimation of the quality of the best model
  built in this project.

* Development (dev) set: All data that goes into training a model *in this
  project*.

  * Validation (vld) set: In a k-fold cross-validation process, the set on
    which to determine the quality of the model trained on an evaluation
    and a training set.

  * Evaluation (evl) set: In a k-fold cross-validation process, the set
    with which to determine the quality of the model during training,
    espc. to allow for early stopping.

  * Training (trn) set: In a k-fold cross-validation process, the set on
    which to train the model.

The JEITA Aozora and Genpaku corpora are split independently, as they contain
different language content: The documents in the Aozora corpus were originally
written in Japanese, while the documents in the Genpaku corpus stem from sources
in other languages.

"""


import os
from numpy.random import RandomState
from sklearn.model_selection import train_test_split
import sklearn.utils
from nltk.corpus.reader.chasen import ChasenCorpusReader
import sqlite3 as sql
import json

from ...features.symbol_stream import in_ranges, validate_brackets, BracketingError
from ...features.corpus import load_sentence
from ...features.jpn import chasen_loader, BRACKET_DICT, ARCHAIC_CHARS, REPEAT_MARK, VOICED_REPEAT_MARK, repetition_contraction, WORD_RANGES, SUPPLEMENTAL_RANGES
from ...util.collections import shuffle
from ...util.math import prod


_SPLIT_SEED = 775607720
_SPLIT_R = RandomState(_SPLIT_SEED)
_SHUFFLE_SEED = 116957683
_JPN_RANGES = WORD_RANGES + SUPPLEMENTAL_RANGES
DATABASE = os.path.abspath(os.path.dirname(os.path.abspath(__file__))
                           + '/../../../data/processed/data.db')
"""The database file location."""
_CORPUS_DIR = None
_RSV_FILES, _TST_FILES, _DEV_FILES = None, None, None
_sentence_ids = None


def _chasen_file_finder(corpus_dir, corpus):
    if corpus not in ('aozora', 'genpaku'):
        raise ValueError('Unknown corpus')
    for _, _, files in os.walk(os.path.abspath(corpus_dir
                                               + '/jeita_%s' % (corpus,))):
        for f in sorted(files):
            if f.endswith('.chasen'):
                yield f


def _ensure_file_ids(corpus_dir):
    """Make sure the IDs for all document files of the corpus are loaded.

    :param str corpus_dir: The root directory of the corpus.
    
    :raises ValueError: If different root directories have been issued.

    """
    global _CORPUS_DIR, _RSV_FILES, _TST_FILES, _DEV_FILES
    # Ensure data is only loaded once (Thus random states are consistent for
    # every loading)
    if corpus_dir is None:
        raise TypeError("The corpus root directory has to be of type 'str'")
    if _CORPUS_DIR is None:
        jeita_aozora_files = tuple('jeita_aozora/%s' % (f,)
                                   for f in _chasen_file_finder(corpus_dir, 'aozora'))
        jeita_genpaku_files = tuple('jeita_genpaku/%s' % (f,)
                                    for f in _chasen_file_finder(corpus_dir, 'genpaku'))
        # Split off reserve and test set before filtering out bad files, as the
        # definition of 'bad' may change during the course of the project
        jeita_aozora_non_reserve_files, jeita_aozora_reserve_files = train_test_split(jeita_aozora_files, test_size=0.2, random_state=_SPLIT_R, shuffle=True)
        jeita_aozora_development_files, jeita_aozora_test_files = train_test_split(jeita_aozora_non_reserve_files, test_size=0.25, random_state=_SPLIT_R, shuffle=False)
        jeita_genpaku_non_reserve_files, jeita_genpaku_reserve_files = train_test_split(jeita_genpaku_files, test_size=0.2, random_state=_SPLIT_R, shuffle=True)
        jeita_genpaku_development_files, jeita_genpaku_test_files = train_test_split(jeita_genpaku_non_reserve_files, test_size=0.25, random_state=_SPLIT_R, shuffle=False)
        _RSV_FILES = tuple(shuffle(jeita_aozora_reserve_files + jeita_genpaku_reserve_files, random_state=_SPLIT_R))
        _TST_FILES = tuple(shuffle(jeita_aozora_test_files + jeita_genpaku_test_files, random_state=_SPLIT_R))
        _DEV_FILES = tuple(shuffle(jeita_aozora_development_files + jeita_genpaku_development_files, random_state=_SPLIT_R))
        _CORPUS_DIR = corpus_dir
    elif corpus_dir != _CORPUS_DIR:
        raise ValueError('Inconsistent second corpus root directory issued')


def rsv_files(corpus_dir):
    """Get the filenames of the reserved corpus documents.

    :param str corpus_dir: The root directory of the corpus.
    
    """
    global _RSV_FILES
    _ensure_file_ids(corpus_dir)
    return _RSV_FILES


def tst_files(corpus_dir):
    """Get the filenames of the corpus documents for tests.

    :param str corpus_dir: The root directory of the corpus.
    
    """
    global _TST_FILES
    _ensure_file_ids(corpus_dir)
    return _TST_FILES


def dev_files(corpus_dir):
    """Get the filenames of the corpus documents for development.

    :param str corpus_dir: The root directory of the corpus.
    
    """
    global _DEV_FILES
    _ensure_file_ids(corpus_dir)
    return _DEV_FILES


def load_dev_sentence_ids(n_samples=None):
    """Load the identifiers of sentences from the development files of the Japanese
    corpus.

    The order of identifiers is randomized (independently of the number of
    samples requested and consistently in between calls requesting the same
    number of samples).

    :param int n_samples: The number of sample identifiers to load.  If
        ``None``, load all identifiers.

    :return: A tuple of sentence identifiers of the form ``(<file name>,
        <sentence number>)``.

    """
    global _sentence_ids
    if _sentence_ids is None:
        with sql.connect(DATABASE) as conn:
            _sentence_ids = tuple((file, i)
                                  for file, i, sentence
                                  in ((file, i, json.loads(sentence))
                                      for file, i, sentence in conn.cursor().execute(
                                              '''SELECT file, sequence_id, sentence
                                                 FROM sentences
                                                 WHERE language = "jpn"
                                                 ORDER BY file, sequence_id'''))
                                  if not isinstance(sentence, str)
                                  # Do not consider overly long sentences; they
                                  # exceed memory restrictions
                                  and len(sentence) <= 200
                                  # Do not consider sentences with excessive
                                  # numbers of alternatives; combinatorial
                                  # explosion here leads to sentences with
                                  # marginal contributions and greatly increases
                                  # training duration without much actual
                                  # learning taking place
                                  and prod(len(candidates)
                                           for candidates in sentence) <= 100)
    # Shuffle the IDs differently for different numbers of samples, so as not to
    # always return the same first samples
    return tuple(sklearn.utils.shuffle(_sentence_ids,
                                       random_state=(_SHUFFLE_SEED
                                                     + (len(_sentence_ids)
                                                        if n_samples is None
                                                        else n_samples)),
                                       n_samples=n_samples))


# XXX Make public
def _lookup_tokenizer(sentence):
    """Tokenize the specified sentence.

    The manner of tokenization is a simple lookup in the database table of
    precomputed tokenized sentences.

    :param sentence: A pair of the form ``(<file name>, <sentence number>)``.

    :return: A tuple of tokens (See
        :meth:`...language._lang.Language.tokenize`).

    """
    file, sequence_id = sentence
    # We have to establish a new connection to the database for every
    # sentence, as tensorflow works in multithreaded mode and the connection
    # from sqlite3 is not thread-safe
    return load_sentence(DATABASE, 'jpn', file, sequence_id)


# def _graphic_character_extractor(tokens):
#     return ''.join(token['lemma']['graphic'] for token in tokens)


# XXX Make public
def _lemma_extractor(tokens):
    """Turn an iterable of tokens into language model input.

    :param tokens: An iterable of tokens (see :meth:`tokenize` for the token
        representation).

    :return: An iterable of token identifiers of the form ``(<graphic lemma
    variant>, <phonetic lemma variant>)``.

    """
    return ((token['lemma']['graphic'], token['lemma']['phonetic'])
            for token in tokens)


# def _generate_file_names_and_symbol_streams(files):
#     for f in files:
#         yield f, chasen_loader(f)


# def kfolds(n_samples=None, n_splits=5, evl_size=0.25):
#     for fold in kfolds_files(n_samples, n_splits, evl_size):
#         yield tuple(_generate_file_names_and_symbol_streams(files)
#                     for files in fold)


# def tests(corpus_dir):
#     yield from _generate_file_names_and_symbol_streams(tst_files(corpus_dir))


# XXX Couln't this be done without else clauses after for?
def validate_file(f):
    """Determine whether the file has high data quality.

    Filter out documents with archaic writing styles, excess foreign content or
    improper bracketing structures.

    :return: ``True`` if the file passes all tests, ``False`` otherwise.

    """
    try:
        # Filter out files with archaic writing styles
        for j, (s, *_) in enumerate(validate_brackets(repetition_contraction(chasen_loader(f)), BRACKET_DICT), start=1):
            if s in ARCHAIC_CHARS:
                # print('%s\t\033[31mREJECT\033[0m\t%s\tContains archaic %r' % (file_tag(files), f, chr(s)))
                return False
            elif s == REPEAT_MARK or s == VOICED_REPEAT_MARK:
                # print('%s\t\033[31mREJECT\033[0m\t%s\tContains obsolete repeat mark'
                #       % (file_tag(files), f))
                return False
        else:
            # Filter out files with excess foreign content
            previous_non_jpn_word = None
            for word in ChasenCorpusReader(
                    os.path.abspath(os.path.dirname(os.path.abspath(__file__))
                                    + '/../../../data/raw/yokome-jpn-corpus'),
                    f, encoding='utf-8').words():
                if any(in_ranges(ord(c), _JPN_RANGES) for c in word):
                    previous_non_jpn_word = None
                else:
                    if previous_non_jpn_word is not None:
                        # print(('%s\t\033[31mREJECT\033[0m\t%s\tContains excess non-'
                        #        'target language content: ... %r %r ...')
                        #       % (file_tag(files), f, previous_non_jpn_word, word))
                        return False
                    previous_non_jpn_word = word
            else:
                # print('%s\t\033[32mACCEPT\033[0m\t%s\t%d characters' % (file_tag(files), f, j))
                return True
    except BracketingError as e:
        # print('%s\t\033[31mREJECT\033[0m\t%s\t%s: %r' % (file_tag(files), f, e, to_text(e.value)))
        return False
