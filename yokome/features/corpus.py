#!/usr/bin/python3
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


from collections import defaultdict
from fractions import Fraction
import json
import sqlite3 as sql

from ..util.persistence import list_as_tuple_hook


def lemma_coverage(conn, graphic, phonetic) -> int:
    """Provide a measure of difficulty/infrequency for the specified lemma.
    
    We here define a type's corpus coverage as the proportion of tokens in a
    corpus that are instances of types that are at least as frequent as the type
    of interest.

    :param conn: Database connection for statistics.

    :param str graphic: Graphic lemma variant of interest.

    :param str phonetic: Phonetic lemma variant of interest.

    :return: The portion of tokens in the background corpus that are instances 
        of types that are at least as frequent as the type of interest.

    """
    c = conn.cursor()
    cumulative_count = next(c.execute(
        '''SELECT MAX(cumulative_count)
           FROM statistics
           WHERE language = "jpn"
           AND form = "lemma"
           AND count = (SELECT count FROM statistics 
                        WHERE language = "jpn"
                        AND form = "lemma"
                        AND graphic = ?
                        AND phonetic = ?)''',
        (graphic, phonetic)))[0]
    if cumulative_count is None:
        # Unknown word: The whole corpus has to be covered
        return 1.0
    total_count = next(c.execute(
        '''SELECT MAX(cumulative_count)
           FROM statistics
           WHERE language = "jpn" 
           AND form = "lemma"'''))[0]
    return cumulative_count / total_count


def generate_lemma_vocabulary(conn, min_coverage):
    """Generate a vocabulary of lemmas with the specified minimal corpus
    coverage.

    This is the smallest vocabulary of the most frequent words so that these
    words together cover at least a portion of ``min_coverage`` of the corpus.

    :param conn: Database connection for statistics.

    :param float min_coverage: The minimal coverage.

    :return: A dictionary from lemmas to their frequency rank.

    """
    if min_coverage < 0 or min_coverage > 1:
        raise ValueError('The minimum coverage must be between 0 (inclusive) and 1 (inclusive)')
    if min_coverage == 0:
        return dict()
    return {(graphic, phonetic): rank
            for graphic, phonetic, rank in conn.cursor().execute(
                    '''SELECT graphic, phonetic, rank FROM statistics
                       WHERE language = "jpn" 
                       AND form = "lemma" 
                       AND count >= (
                           SELECT MAX(count) FROM statistics
                           WHERE language = "jpn"
                           AND form = "lemma"
                           AND cumulative_count >= (
                               SELECT MAX(cumulative_count)
                               FROM statistics
                               WHERE language = "jpn" 
                               AND form = "lemma") * ?)''',
                    (min_coverage,))}


def generate_graphic_character_vocabulary(conn, min_coverage):
    """Generate a vocabulary of characters from graphic representations of
    lemmas with the specified minimal corpus coverage.

    This is the smallest vocabulary of the most frequent characters so that
    these characters together cover at least a portion of ``min_coverage`` of
    the corpus.

    :param conn: Database connection for statistics.

    :param float min_coverage: The minimal coverage.

    :return: A dictionary from characters from graphic representations of lemmas
        to their frequency rank.

    """
    if min_coverage < 0 or min_coverage > 1:
        raise ValueError('The minimum coverage must be between 0 (inclusive) and 1 (inclusive)')
    if min_coverage == 0:
        return dict()
    return {graphic_c: rank
            for graphic_c, rank in conn.cursor().execute(
                    '''SELECT graphic, rank FROM statistics
                       WHERE language = "jpn" 
                       AND form = "lemma:graphic:character" 
                       AND count >= (
                           SELECT MAX(count) FROM statistics
                           WHERE language = "jpn"
                           AND form = "lemma:graphic:character"
                           AND cumulative_count >= (
                               SELECT MAX(cumulative_count)
                               FROM statistics
                               WHERE language = "jpn" 
                               AND form = "lemma:graphic:character") * ?)''',
                    (min_coverage,))}


def generate_phonetic_character_vocabulary(conn, min_coverage):
    """Generate a vocabulary of characters from phonetic representations of
    lemmas with the specified minimal corpus coverage.

    This is the smallest vocabulary of the most frequent characters so that
    these characters together cover at least a portion of ``min_coverage`` of
    the corpus.

    :param conn: Database connection for statistics.

    :param float min_coverage: The minimal coverage.

    :return: A dictionary from characters from phonetic representations of lemmas
        to their frequency rank.

    """
    if min_coverage < 0 or min_coverage > 1:
        raise ValueError('The minimum coverage must be between 0 (inclusive) and 1 (inclusive)')
    if min_coverage == 0:
        return dict()
    return {phonetic_c: rank
            for phonetic_c, rank in conn.cursor().execute(
                    '''SELECT phonetic, rank FROM statistics
                       WHERE language = "jpn" 
                       AND form = "lemma:phonetic:character" 
                       AND count >= (
                           SELECT MAX(count) FROM statistics
                           WHERE language = "jpn"
                           AND form = "lemma:phonetic:character"
                           AND cumulative_count >= (
                               SELECT MAX(cumulative_count)
                               FROM statistics
                               WHERE language = "jpn" 
                               AND form = "lemma:phonetic:character") * ?)''',
                    (min_coverage,))}


def generate_vocabulary_from(language, sentences, min_coverage):
    """Generate a vocabulary with the specified minimal sentence coverage.
    
    This is the smallest vocabulary of the most frequent tokens so that these
    tokens together cover at least a portion of ``min_coverage`` of the
    sentences.  The tokens are determined by the ``tokenize`` method of the
    language.

    :param yokome.language.Language language: The language of interest.

    :param sentences: A sequence of sentences, in a form that each sentence can
        be tokenized using the ``tokenize`` method of the language.

    :param float min_coverage: The minimal coverage.

    :return: A dictionary from tokens to their frequency rank w.r.t. the
        sentences.

    """
    counts = defaultdict(lambda: Fraction(0, 1))
    for sentence in sentences:
        for candidates in language.tokenize(sentence):
            contribution = Fraction(1, len(candidates))
            # XXX Only works for word-level extracts, for character-level
            # extracts, the contribution has to be computed differently
            for word in language.extract_parallel(candidates):
                counts[word] += contribution
    counts = sorted(counts.items(), key=lambda x: x[1], reverse=True)
    covered_count = sum(count for _, count in counts) * min_coverage
    cumulative_count = Fraction(0, 1)
    min_count = None
    vocabulary = dict()
    for i, (word, count) in enumerate(counts, start=1):
        if min_count is None or count == min_count:
            vocabulary[word] = i
            cumulative_count += count
            if cumulative_count >= covered_count:
                min_count = count
        else:
            break
    return vocabulary


def _prepare_sentence_from_database(sentence):
    sentence = json.loads(sentence, object_hook=list_as_tuple_hook)
    if isinstance(sentence, str):
        return sentence
    return tuple(tuple(candidates) for candidates in sentence)


def load_sentence(DATABASE, language, file, sequence_id):
    """Load a sentence from the database.

    :param str DATABASE: The database file.
    
    :param str language: ISO 639-3 language code of the language of interest.

    :param str file: ID of the corpus document from which the sentence stems.

    :param int sequence_id: The number of the sentence in the document,
        1-indexed.

    :return: A string if the sentence only contains stop-character content
        (espc. whitespace); a tokenized sentence otherwise.

    """
    with sql.connect(DATABASE) as conn:
        try:
            (sentence,) = next(conn.cursor().execute('SELECT sentence FROM sentences WHERE language = ? AND file = ? AND sequence_id = ?', (language, file, sequence_id)))
        except StopIteration:
            raise KeyError('Sentence for %r %r %d not found in %r'
                           % (language, file, sequence_id, DATABASE))
    return _prepare_sentence_from_database(sentence)
