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
import math
import numpy as np
import sqlite3 as sql
import json
from elasticsearch import Elasticsearch
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
import tensorflow as tf
tf.logging.set_verbosity(tf.logging.ERROR)

_PROJECT_ROOT = os.path.abspath(os.path.dirname(os.path.abspath(__file__))
                                + '/../..')
if _PROJECT_ROOT not in sys.path:
    sys.path.append(_PROJECT_ROOT)
from yokome.language import Language
from yokome.features.dictionary import Lexeme, circled_number, GLOSS_SEPARATOR
from yokome.features.tree import TemplateTree
from yokome.features.symbol_stream import to_symbol_stream, ascii_fold
from yokome.features.jpn import combining_voice_mark_fold, repetition_contraction, iteration_fold, fullwidth_fold, stream_tokenizer
from yokome.models.language_model import LanguageModel
from yokome.util.persistence import list_as_tuple_hook


# Database
DATABASE = os.path.abspath(_PROJECT_ROOT + '/data/processed/data.db')
# Language
LANGUAGE = Language.by_code('jpn_unseen')
LANGUAGE_CODE = 'jpn'
# Part-of-speech tags
with open(os.path.abspath(_PROJECT_ROOT + '/data/crafted/jpn_pos_restrictions.json'), 'r') as f:
    RESTRICTIONS = json.load(f)
# Language model
with open(os.path.abspath(_PROJECT_ROOT + '/hyperparameter_optimization/xvld/best_hyperparams.json'), 'r') as f:
    HYPERPARAMS = json.load(f, object_hook=list_as_tuple_hook)
MODEL = LanguageModel(os.path.abspath(_PROJECT_ROOT + '/models/trn'),
                      params=HYPERPARAMS,
                      production_mode=True,
                      language=LANGUAGE,
                      vocabulary=None)
BATCH_SIZE = 25
SAMPLE_SIZE = 5
# Glosses
ES = Elasticsearch(['localhost:9200'])
INDEX_NAME = 'jpn_inverse_dictionary'
RESULT_SIZE = 25


def n_lexemes_for_lemma(conn, language_code, lemma) -> int:
    """Get the number of dictionary entries with ``lemma`` as headword.
    
    :param conn: The database connection for the dictionary.
    :param str language_code: ISO 639-3 language code of the language of interest.
    :param lemma: A dictionary that contains the keys ``graphic`` and
        ``phonetic``.

    :return: The number of entries in the dictionary that have the specified
        lemma as one of its headwords.

    """
    # TODO Use language code
    return next(conn.cursor().execute(
        'SELECT COUNT(DISTINCT entry_id) '
        '    FROM lemmas '
        '    WHERE language = ? AND graphic = ? AND phonetic = ?',
        (language_code, lemma['graphic'], lemma['phonetic'])))[0]


def lexeme_lemma_count(conn, language_code, lemma):
    """Estimate the number of occurrences of a lexeme-lemma combination.

    Get the number of occurrences of a lemma in the background corpus and
    estimate its contribution to the number of occurrences to one of its
    corresponding lexemes by dividing it by the number of lexemes for which it
    is listed as a headword.

    :param conn: The database connection for the dictionary and statistics.
    :param language_code: ISO 639-3 language code of the language of interest.
    :param lemma: A dictionary that contains the keys ``graphic`` and ``phonetic``.

    :return: The number of estimated occurrences of the specified lemma with one
        of its lexemes, assuming equal distribution of the lemma among its
        lexemes.

    """
    c = conn.cursor()
    n_lexemes = n_lexemes_for_lemma(conn, language_code, lemma)
    try:
        return (next(c.execute(
            'SELECT count '
            '    FROM statistics '
            '    WHERE language = ? AND form = "lemma" '
            '        AND graphic = ? AND phonetic = ?',
            (language_code, lemma['graphic'], lemma['phonetic'])))[0]
                / n_lexemes)
    except StopIteration:
        return 0


def total_lemmas(conn, language_code):
    """Get the number of lemmas (i.e. of tokens) in the background corpus.

    :param conn: The database connection for statistics.
    :param language_code: ISO 639-3 language code of the language of interest.

    :return: The total number of lemmas in the background corpus.

    """
    return next(conn.cursor().execute(
        'SELECT MAX(cumulative_count) '
        '    FROM statistics '
        '    WHERE language = ? AND form = "lemma"',
        (language_code,)))[0]


def has_statistics(conn, language_code, lemma):
    """See if ``lemma`` can be found in both the dictionary and the corpus.

    :param conn: The database connection for the dictionary and statistics.
    :param str language_code: ISO 639-3 language code of the language of interest.
    :param lemma: A dictionary that contains the keys ``graphic`` and ``phonetic``.

    :returns: ``True`` if the lemma can be found in both the dictionary and the 
        corpus, ``False`` otherwise.
    
    """
    return (any(True for _ in conn.cursor().execute(
        'SELECT * '
        '    FROM statistics '
        '    WHERE language = ? AND form = "lemma" '
        '        AND graphic = ? AND phonetic = ?',
        (language_code, lemma['graphic'], lemma['phonetic'])))
            and any(True for _ in conn.cursor().execute(
                'SELECT * '
                '    FROM lemmas '
                '    WHERE language = ? AND graphic = ? AND phonetic = ?',
                (language_code, lemma['graphic'], lemma['phonetic']))))


def retrieve_substitute_lexemes(entry_id, n_senses, sense):
    """Search for substitute lexemes with senses similary to the specified one.

    :param entry_int id: The ID of the lexeme of interest in the dictionary.
    :param int n_senses: The total number of senses of the lexeme with ID
            ``entry_id``.
    :param sense: A list of gloss descriptions of the form ``(gloss_type, gloss)``.
    
    :return: A list of dictionaries of the form

        .. code-block:: python

           {'entry_id': <entry ID of lexeme>,
            'lemmas': <list of headwords of lexeme>,
            'pos': <tree of POS-tags>,
            'glosses': <list of glosses>,
            'ir_score': <information retrieval score>}

        of the connotations (i.e. lexeme-sense combinations) that most closely
        resemble ``sense`` in terms of their glosses.  All connotations that
        pertain to the lexeme with the ID ``entry_id`` are excluded.

    """
    # XXX Handle timeout/error
    # Construct query
    retrieval_query = ' '.join([gloss for _, gloss in sense.glosses])
    request_body = {'query':
                    {'match': {'glosses': {'query': retrieval_query}}},
                    '_source': ['lemmas', 'pos', 'glosses'],
                    'size': RESULT_SIZE + n_senses}
    if not ES.indices.analyze(index=INDEX_NAME,
                              body={'analyzer': 'eng_stop_analyzer',
                                    'text': retrieval_query})['tokens']:
        # Fallback for stopword-only queries (e.g. ノー【のー】❶): Also consider
        # stop-words while querying
        request_body['query']['match']['glosses']['analyzer'] = 'eng_analyzer'
    # Find lexemes with glosses similar to the original sense
    hits = [{'entry_id': int(hit['_id'].split(':')[1]),
             'ir_score': hit['_score'],
             'lemmas': hit['_source']['lemmas'],
             'pos': TemplateTree.parse(hit['_source']['pos'], RESTRICTIONS),
             'glosses': hit['_source']['glosses']}
            for hit in ES.search(index=INDEX_NAME,
                                 doc_type='_doc',
                                 body=request_body)['hits']['hits']]
    # Return the best ``RESULT_SIZE`` hits that do not pertain to the original
    # lexeme itself
    return [hit
            for hit in hits
            if hit['entry_id'] != entry_id][:RESULT_SIZE]
    

def score_connotation(tokens, i, sense_prior, pos_tree, role_pos_score, conn,
                      substitute_lexemes, TOTAL_LEMMAS):
    """Score the substitution of the token at ``i`` with ``substitute_lexemes``.

    :param tokens: A sentence, split into tokens.
    :param i: The position of the token of interest in ``tokens``.
    :param sense_prior: The prior probability of the sense given the lexeme.
    :param yokome.features.tree.TemplateTree pos_tree: The POS tree of the role to
            which the connotation belongs.
    :param role_pos_score: The summed scores of the matches between ``pos_tree``
            and each POS tree that pertains to a candidate lemma of the token of
            interest so that the candidate lemma is a headword of the lexeme to
            which the connotation belongs.
    :param conn: The database connection for the dictionary and statistics.
    :param substitute_lexemes: A list of dicts that describe lexemes that could be
            used as substitutes for the token of interest.
    :param TOTAL_LEMMAS: The total number of lemmas (i.e. of tokens) in the corpus.

    :return: A score for the suitability of the connotation that suggested
        ``substitute_lexemes`` to describe the meaning of the token at ``i``.

    """
    # print('     | Lexeme  | IR score | POS scr. | LM score    |')
    # print('     +---------+----------+----------+-------------+')
    ir_scores = []
    pos_scores = []
    lm_scores = []
    for substitute_lexeme in substitute_lexemes:
        # Filter out unknown lemmas
        # XXX Check substitute_lexeme filter
        substitute_lemmas = [substitute_lemma
                             for code, substitute_lemma
                             in zip(
                                 # XXX Check encoding via public method
                                 MODEL._encode(LANGUAGE.extract([
                                     {'lemma': substitute_lemma}
                                     for substitute_lemma
                                     in substitute_lexeme['lemmas']]))[1:],
                                 substitute_lexeme['lemmas'])
                             if code != 0 and has_statistics(conn,
                                                             LANGUAGE_CODE,
                                                             substitute_lemma)]
        if substitute_lemmas:          # Only consider lexemes with known lemmas
            ir_scores.append(substitute_lexeme['ir_score'])
            pos_score, _ = pos_tree.score(substitute_lexeme['pos'])
            pos_scores.append(pos_score)
            altered_sentences = [tokens[:i]
                                 + [[{'lemma': substitute_lemma}]]
                                 + tokens[i + 1:]
                                 for substitute_lemma in substitute_lemmas]
            lm_score = sum((2 ** estimate['log2_sentence_probs']).mean()
                           / n_lexemes_for_lemma(conn,
                                                 LANGUAGE_CODE,
                                                 substitute_lemma)
                           for estimate, substitute_lemma
                           in zip(
                               MODEL.estimate_probability(altered_sentences,
                                                          BATCH_SIZE,
                                                          SAMPLE_SIZE),
                               substitute_lemmas))
            lm_score /= (sum(lexeme_lemma_count(conn,
                                                LANGUAGE_CODE,
                                                substitute_lemma)
                             for substitute_lemma in substitute_lemmas)
                         / TOTAL_LEMMAS)
            lm_scores.append(lm_score)
            # print('     | %7d | %8.4f | %8.4f | %g | %s' % (substitute_lexeme['entry_id'], ir_scores[-1], pos_scores[-1], lm_scores[-1], (' ' + GLOSS_SEPARATOR + ' ').join(substitute_lexeme['glosses'])))
            # print(substitute_lexeme['pos']._str(prefix='     |         |          |          |             | '), end='')
            # for substitute_lemma in substitute_lemmas:
            #     print('     |         |          |          |             | %s【%s】' % (substitute_lemma['graphic'], substitute_lemma['phonetic']))
    if lm_scores:
        ir_scores = np.array(ir_scores, dtype=np.float32)
        pos_scores = np.array(pos_scores, dtype=np.float32)
        lm_scores = np.array(lm_scores, dtype=np.float32)
        conditional_score = ((ir_scores * pos_scores * lm_scores).sum()
                             / (ir_scores * pos_scores).sum())
    else:
        conditional_score = 0.0
    return role_pos_score * sense_prior * conditional_score


def score_lexeme(tokens, i, pos_trees, conn, lexeme, TOTAL_LEMMAS):
    """Disambiguate the token at ``i`` using the connotations of ``lexeme``.

    :param tokens: A sentence, split into its tokens.
    :param i: The position of the token of interest in ``tokens``.
    :param list[yokome.features.tree.TemplateTree] pos_trees: A list of POS trees of
            the token at ``i``, each pertaining to one of the candidate lemmas
            of this token, restricted to those tokens that are headwords of
            ``lexeme``.
    :param conn: The database connection for the dictionary and statistics.
    :param yokome.features.dictionary.Lexeme lexeme: An entry in the dictionary that
            possibly describes the meaning of the token at ``i``.
    :param TOTAL_LEMMAS: The total number of lemmas (i.e. of tokens) in the corpus.

    :return: A dictionary of data on the lexeme, together with the lexemes overall
        suitability to describe the meaning of the token at ``i``. Each
        connotations in turn is associated with its suitability.  The dictionary
        is of the following form:

        .. code-block:: python

           {
             'entry_id': <ID of the lexeme in the dictionary>,
             'headwords': <list of lemmas for the lexeme>,
             'discriminator': <int for lexemes with the same main headword>,
             'roles': [
               {
                 'poss': <POS tag list for the role>,
                 'connotations': [
                   {
                     'sense_id': <the ID of the connotation within the lexeme>,
                     'glosses': ((<gloss_type>, <gloss>), ...),
                     'score': <connotation score>
                   },
                   ...
                 ]
               },
               ...
             ],
             'score': <overall lexeme score>
           }
    
    """
    n_senses = sum(len(role.senses) for role in lexeme.roles)
    total_sense_contribution = (n_senses * (n_senses + 1)) / 2
    k = n_senses
    lexeme_score = 0
    total_pos_score = 0
    lexeme_result = {'entry_id': lexeme.entry_id,
                     'headwords': lexeme.headwords,
                     'discriminator': lexeme.discriminator,
                     'roles': []}
    for role in lexeme.roles:
        # Compute POS tree match between role and token lemmas
        pos_score = 0
        for pos_tree in pos_trees:
            pos_score += role.pos_tree().score(pos_tree)[0]
        # Score each connotation by substituting the token of interest with
        # lemmas of other lexemes
        role_result = {'poss': role.pos_tags, 'connotations': []}
        for sense in role.senses:
            substitute_lexemes = retrieve_substitute_lexemes(
                lexeme.entry_id, n_senses, sense)
            score = score_connotation(tokens,
                                      i,
                                      # Use a connotation prior that decreases
                                      # linearly with the sense_id
                                      k / total_sense_contribution,
                                      role.pos_tree(),
                                      pos_score,
                                      conn,
                                      substitute_lexemes,
                                      TOTAL_LEMMAS)
            role_result['connotations'].append({'sense_id': sense.sense_id,
                                                'glosses': sense.glosses,
                                                'score': score})
            lexeme_score += score
            total_pos_score += pos_score
            k -= 1
        lexeme_result['roles'].append(role_result)
    lexeme_score *= n_senses / total_pos_score # TODO Correct?
    lexeme_result['score'] = lexeme_score
    return lexeme_result


def disambiguate(tokens, i):
    """Disambiguate the token at ``i`` in the tokenized sentence ``tokens``.

    :param tokens: A sentence, split into its tokens.
    :param int i: The position of the token of interest in ``tokens``.

    :return: A list of data on lexemes, ranked by their overall suitability to
        describe the meaning of the token at ``i``, with their connotations in
        turn associated with their suitability.  Each element is a dictionary of
        the following form:

        .. code-block:: python

           {
             'entry_id': <ID of the lexeme in the dictionary>,
             'headwords': <list of lemmas for the lexeme>,
             'discriminator': <int for lexemes with the same main headword>,
             'roles': [
               {
                 'poss': <POS tag list for the role>,
                 'connotations': [
                   {
                     'sense_id': <the ID of the connotation within the lexeme>,
                     'glosses': ((<gloss_type>, <gloss>), ...),
                     'score': <connotation score>
                   },
                   ...
                 ]
               },
               ...
             ],
             'score': <overall lexeme score>
           }

    """
    with sql.connect(DATABASE) as conn:
        TOTAL_LEMMAS = total_lemmas(conn, LANGUAGE_CODE)
        # Look up all possible lexemes for all possible candidates (i.e. equally
        # best-ranked lemmas that the tokenizer found for the token at ``i``)
        # and store them alongside the POS trees pertaining to these lemma
        # tokens
        lexemes = dict()
        token_pos_trees_per_lexeme = dict()
        for j, candidate in enumerate(tokens[i]):
            lemma = candidate['lemma']
            pos_tree = TemplateTree.parse(candidate['pos'], RESTRICTIONS)
            for lexeme in Lexeme.lookup(conn,
                                        LANGUAGE_CODE,
                                        lemma['graphic'],
                                        lemma['phonetic'],
                                        RESTRICTIONS):
                if lexeme.entry_id not in lexemes:
                    lexemes[lexeme.entry_id] = lexeme
                    token_pos_trees_per_lexeme[lexeme.entry_id] = []
                token_pos_trees_per_lexeme[lexeme.entry_id].append(pos_tree)
        # For each possible lexeme, rank its connotations according to how well
        # they describe the token at ``i``, and compute an overall score for the
        # lexeme
        result = []
        for entry_id in lexemes:
            lexeme = lexemes[entry_id]
            token_pos_trees = token_pos_trees_per_lexeme[entry_id]
            lexeme_result = score_lexeme(tokens, i, token_pos_trees, conn,
                                         lexeme, TOTAL_LEMMAS)
            result.append(lexeme_result)
    # Sort the lexemes by their overall score
    return sorted(result, key=lambda x: x['score'], reverse=True)


def test():
    tokens = tuple(stream_tokenizer(fullwidth_fold(ascii_fold(iteration_fold(
        repetition_contraction(combining_voice_mark_fold(to_symbol_stream(
            'あそこに元がある。'))))))))
    i = 2
    for lexeme_result in disambiguate(tokens, i):
        print(lexeme_result['entry_id'])
        print('\033[35m%s【%s】%s\033[0m' % (lexeme_result['headwords'][0][0], lexeme_result['headwords'][0][1], (circled_number(lexeme_result['discriminator'], False) if lexeme_result['discriminator'] is not None else '')))
        for headword in lexeme_result['headwords'][1:]:
            print('%s【%s】' % (headword[0], headword[1]))
        for role in lexeme_result['roles']:
            print(role['poss'])
            for connotation in role['connotations']:
                print('  %2d %s' % (connotation['sense_id'], (' ' + GLOSS_SEPARATOR + ' ').join(gloss for _, gloss in connotation['glosses'])))
                print('     Score: %g' % (connotation['score'],))
        print('Lexeme score: %g' % (lexeme_result['score'],))
        print()


if __name__ == '__main__':
    test()
