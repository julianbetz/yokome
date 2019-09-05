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
import logging
import traceback
import click
import re
from collections import defaultdict
from collections.abc import Sequence
from urllib.parse import unquote_plus
# from http.server import BaseHTTPRequestHandler, HTTPServer
from flask import Flask, Response, url_for, request
import json


if __name__ == '__main__':
    sys.path.append(os.path.abspath(os.path.dirname(os.path.abspath(__file__))
                                    + '/../..'))
    from yokome.features.symbol_stream import to_symbol_stream, ascii_fold
    from yokome.features.jpn import segmenter, strip, stream_tokenizer, stream_tokenizer, fullwidth_fold, iteration_fold, repetition_contraction, combining_voice_mark_fold
    from yokome.models import wsd
else:
    from ..features.symbol_stream import to_symbol_stream, ascii_fold
    from ..features.jpn import segmenter, strip, stream_tokenizer, stream_tokenizer, fullwidth_fold, iteration_fold, repetition_contraction, combining_voice_mark_fold
    from ..models import wsd


# Server settings

PORT = 5003
"""int: Server port to start on."""

TOKEN_SERVANT = 'tokenizer'
"""str: Tokenizer API location."""

TOKEN_SERVICE = 'tokenize'
"""str: Tokenization API location for tokenizer API."""

WSD_SERVANT = 'wsd'
"""str: WSD API location."""

WSD_SERVICE = 'disambiguate'
"""str: Disambiguation API location for WSD API."""


# ISO 639-3 language codes

ENGLISH = 'eng'
"""str: ISO 639-3 language code for English."""

JAPANESE = 'jpn'
"""str: ISO 639-3 language code for Japanese."""


# Japanese language detection settings

KANA_RATIO = 0.05
"""float: Minimum kana rate for immediate JPN detection."""

KANA_RANGES = ((0x3041, 0x3096),        # Hiragana
               (0x30a1, 0x30fa))        # Katakana
"""tuple<tuple<int>>: Character ranges of kana characters.

The ranges contain pronouncable characters only and are expressed as pairs of
start (including) and end (including) characters.

"""


# HTTP protocol-based errors

class BadRequestError(Exception):
    """HTTP ``Bad Request Error``."""
    pass


class NotFoundError(Exception):
    """HTTP ``Not Found Error``."""
    pass


class UnsupportedMediaTypeError(Exception):
    """HTTP ``Unsupported Media Type Error``."""
    pass


class UnprocessableEntityError(Exception):
    """HTTP ``Unprocessable Entity Error``."""
    pass


# XXX Improve, discriminate CJK better
def detect_language(text):
    """Detect the language in which the text was written.

    Currently only support Japanese.
    
    :param str text: The text to detect a language in.

    :return: An ISO 639-3 language code, if a language was detected, ``None``
        otherwise.

    """
    min_kana = len(text) * KANA_RATIO
    n_kana = 0
    for c in text:
        c = ord(c)
        if any([c >= start and c <= end for start, end in KANA_RANGES]):
            n_kana += 1
            if n_kana >= min_kana:
                return JAPANESE
    # Standard value
    return None


app = Flask(__name__)

@app.route('/%s/%s' % (TOKEN_SERVANT, TOKEN_SERVICE), methods=['OPTIONS'])
def api_tokenizer_inform():
    """Respond to an HTTP OPTIONS request at the tokenizer endpoint.

    Allow the POST method from all origins.

    """
    response = Response('', status=200)
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    response.headers['Allow'] = 'POST'
    response.headers['Access-Control-Allow-Methods'] = 'POST'
    return response


def tokenize(text, language=None):
    """Tokenize the specified text for the specified language.

    Attempt to detect the language of the text if no language is provided.  For
    Japanese, apply the JUMAN++ morphological analyzer (Morita, Kawahara,
    Kurohashi 2015).

    :param str text: The text to tokenize.

    :param str language: ISO 639-3 language code of the language the text is
        written in.  If ``None``, the language is detected.

    :return: A dictionary containing the language. The tokenized sentences are
        contained only if there are a segmenter and tokenizer for the language.

    """
    if language is None:
        language = detect_language(text)
    if language == JAPANESE:
        # XXX Handle case that there is no token (only omitted characters)
        sentences = list(
            list(stream_tokenizer(fullwidth_fold(ascii_fold(iteration_fold(
                repetition_contraction(combining_voice_mark_fold(
                    sentence)))))))
            for sentence in strip(segmenter(to_symbol_stream(text))))
        response = {'language': language, 'sentences': sentences}
    else:
        response = {'language': language}
    return response


@app.route('/%s/%s' % (TOKEN_SERVANT, TOKEN_SERVICE), methods=['POST'])
def api_tokenize():
    """Respond to an HTTP POST request at the tokenizer endpoint.

    The expected data has the following form:
    
    .. code-block:: python

       {
         'language': <ISO 639-3 language code or null>,
         'text': <the text to tokenize>
       }

    :return: An HTTP response.  If the request was successful, the data is a
        JSON dictionary that has an entry ``'language'`` for the
        provided/detected language and may have an entry ``'sentences'`` for the
        tokenized sentences.  Otherwise, send an error message, see
        :meth:`handle_error`.

    """
    try:
        data = request.get_json()
        if not isinstance(data, dict):
            raise UnprocessableEntityError('Malformed message body')
        data = defaultdict(lambda: None, data)
        language = data['language']
        text = data['text']
        if not isinstance(text, str):
            raise BadRequestError("'text' value missing or not of type 'str'")
        if language in (None, JAPANESE):
            response = Response(json.dumps(tokenize(text, language),
                                           ensure_ascii=True),
                                status=200,
                                mimetype='application/json')
        else:
            # XXX Apply proper error handling
            raise NotImplementedError('Language not supported')
    except Exception as error:
        response = handle_error(error)
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response


@app.route('/%s/%s' % (WSD_SERVANT, WSD_SERVICE), methods=['OPTIONS'])
def api_wsd_inform():
    """Respond to an HTTP OPTIONS request at the disambiguation endpoint.

    Allow the POST method from all origins.

    """
    response = Response('', status=200)
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    response.headers['Allow'] = 'POST'
    response.headers['Access-Control-Allow-Methods'] = 'POST'
    return response


def disambiguate(tokens, i, language):
    """Disambiguate the token at index ``i`` for the specified language.

    Currently only support Japanese.

    :param tokens: A sentence, split into its tokens.

    :param int i: The position of the token of interest in ``tokens``.

    :param str language: ISO 639-3 language code of the language of the tokens.

    :return: A dictionary containing an entry ``'language'`` for the language
        and an entry ``'lexemes'`` for the lexemes of the token at index ``i``.

        The entry ``'lexemes'`` is list of data on lexemes, ranked by their
        overall suitability to describe the meaning of the token at ``i``, with
        their connotations in turn associated with their suitability.  Each
        element is a dictionary of the following form:

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

    :raises NotImplementedError: If the requested language is not supported.

    """
    if language == JAPANESE:
        return {'language': language, 'lexemes': wsd.disambiguate(tokens, i)}
    raise NotImplementedError('Language not supported')


# XXX Apply proper error handling
@app.route('/%s/%s' % (WSD_SERVANT, WSD_SERVICE), methods=['POST'])
def api_disambiguate():
    """Respond to an HTTP POST request at the disambiguation endpoint.

    The expected data has the following form:
    
    .. code-block:: python

       {
         'language': <ISO 639-3 language code or null>,
         'tokens': <A sentence, split into its tokens>,
         'i': <position of the token of interest>
       }

    :return: An HTTP response.  If the request was successful, the data is a
        JSON of the dictionary returned by :meth:`disambiguate`.  Otherwise,
        send an error message, see :meth:`handle_error`.

    """
    try:
        data = request.get_json()
        if not isinstance(data, dict):
            raise UnprocessableEntityError('Malformed message body')
        data = defaultdict(lambda: None, data)
        language = data['language']
        if not isinstance(language, str):
            raise BadRequestError("'language' value missing or not of type 'str'")
        if data['i'] is None:
            raise BadRequestError("Value for token index 'i' missing")
        if not isinstance(data['tokens'], Sequence):
            raise BadRequestError("'tokens' value missing or not a sequence")
        if language in (JAPANESE,):
            response = Response(json.dumps(disambiguate(data['tokens'],
                                                        int(data['i']),
                                                        language),
                                           ensure_ascii=True),
                                status=200,
                                mimetype='application/json')
        else:
            raise NotImplementedError('Language not supported')
    except Exception as error:
        response = handle_error(error)
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response


def handle_error(error):
    """Catch errors for HTTP requests and provide apt responses.

    Handle the following errors:

    * ``Bad Request Error`` (400)

    * ``Not Found Error`` (404)

    * ``Unsupported Media Type Error`` (415)

    * ``Unprocessable Entity Error`` (422) (also while catching
      ``TypeError``/``ValueError``)

    * ``Not Implemented Error`` (501)

    All remaining errors results in an ``Internal Server Error`` (500).

    The data in the response is an error message.  In case of the debug mode, a
    traceback is appended.

    :return: An HTTP response with the respective error.

    """
    if isinstance(error, BadRequestError):
        status = 400                    # BAD REQUEST
        error_message = str(error)
    elif isinstance(error, NotFoundError):
        status = 404                    # NOT FOUND
        error_message = str(error)
    elif isinstance(error, UnsupportedMediaTypeError):
        status = 415                    # UNSUPPORTED MEDIA TYPE
        error_message = str(error)
    elif isinstance(error, TypeError) or isinstance(error, ValueError):
        status = 422                    # UNPROCESSABLE ENTITY
        error_message = 'Semantically malformed request'
    elif isinstance(error, UnprocessableEntityError):
        status = 422                    # UNPROCESSABLE ENTITY
        error_message = str(error)
    elif isinstance(error, NotImplementedError):
        status = 501                    # NOT IMPLEMENTED
        error_message = 'Not implemented'
    else:
        status = 500                    # INTERNAL SERVER ERROR
        error_message = 'Internal server error'
    if app.debug:
        print(traceback.format_exc(), file=sys.stderr)
    # Write the error message to the response body.  For security purposes,
    # internal error messages are masked.
    return Response(error_message + '\n\n' + traceback.format_exc()
                    if app.debug
                    else error_message,
                    status=status,
                    mimetype='text/plain')


@click.command()
@click.option('--debug/--no-debug', default=False,
              help='Whether to activate debug mode.')
@click.option('--secure/--insecure', default=True,
              help='Whether to use HTTPS instead of HTTP. '
              'In case of secure connections, use a self-signed certificate.')
def run_app(debug, secure):
    """Start the server.

    :param bool debug: Whether to activate debug mode.

    :param bool secure: Whether to use HTTPS instead of HTTP.  In case of secure
        connections, use a self-signed certificate.
    
    """
    app.run(host='0.0.0.0', port='5003', debug=debug,
            ssl_context='adhoc' if secure else None)


if __name__ == '__main__':
    # main()
    run_app()
