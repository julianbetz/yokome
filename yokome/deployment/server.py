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
from urllib.parse import unquote_plus
from http.server import BaseHTTPRequestHandler, HTTPServer
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

JUMAN_TRANSLATOR_FILE = os.path.abspath(
    os.path.dirname(os.path.abspath(__file__))
    + '/../../data/interim/juman_pos_translator.json')
with open(JUMAN_TRANSLATOR_FILE, 'r') as f:
    JUMAN_TRANSLATOR = json.load(f)


# HTTP protocol-based errors

class BadRequestError(Exception):
    pass

class NotFoundError(Exception):
    pass

class UnsupportedMediaTypeError(Exception):
    pass

class UnprocessableEntityError(Exception):
    pass


# Application-specific HTTP errors

class EmptyBodyException(Exception):
    pass


# TODO Improve, discriminate CJK better
def detect_language(text):
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


class Handler(BaseHTTPRequestHandler):
    """Handler for all incoming HTTP requests.
    
    Defines the API.
    
    """
    
    debug = False
    """bool: Whether to output detailed information in case of errors."""

    def parse_params(params):
        """Turn a URL parameter string into a dictionary."""
        if params == '':
            return dict()
        # TODO Raise error when not able to parse
        params = [param.split('=') for param in params.split('&')]
        if any(len(param) != 2 for param in params):
            raise BadRequestError('Parameters could not be parsed')
        return {unquote_plus(k): unquote_plus(v) for k, v in params}

    # TODO Catch cases in which headers are not present
    def parse_body(self):
        """Turn a JSON-encoded HTTP response body into Python objects."""
        content_length = self.headers.get('Content-Length')
        if content_length is None:
            raise EmptyBodyException
        try:
            content_length = int(content_length)
            if content_length < 0:
                raise ValueError
        except ValueError as error:
            raise BadRequestError("Malformed 'Content-Length' header")
        if content_length == 0:
            raise EmptyBodyException
        # TODO Catch errors while reading
        body = self.rfile.read(content_length)
        if (self.headers.get('Content-Type') != 'application/json'):
            raise UnsupportedMediaTypeError(
                "Expected mimetype 'application/json'")
        try:
            return json.loads(body)
        except json.decoder.JSONDecodeError as error:
            raise BadRequestError('JSON decode error: %s' % (str(error),))

    def check_tokenize(params, data):
        """Check data and tokenize it.
        
        First, check whether all data that is required by Handler.tokenize is
        provided.  Then, return the tokenized data.

        """
        if isinstance(data, EmptyBodyException):
            raise UnprocessableEntityError('Message body missing')
        if type(data) != str:
            raise UnprocessableEntityError('Malformed message body')
        if 'lang' in params:
            if params['lang'] != JAPANESE:
                raise NotImplementedError('Language not supported')
            return Handler.tokenize(data, params['lang'])
        return Handler.tokenize(data)

    def tokenize(text, language=None):
        """Tokenize the specified text for the specified language.
        
        Attempt to detect the language of the text if no language is
        provided.  For Japanese, apply the JUMAN++ morphological analyzer
        (Morita et al. 2015).

        """
        if language is None:
            language = detect_language(text)
        if language == JAPANESE:
            # TODO Handle case that there is no token (only omitted characters)
            sentences = list(
                list(stream_tokenizer(fullwidth_fold(ascii_fold(iteration_fold(
                    repetition_contraction(combining_voice_mark_fold(
                        sentence)))))))
                for sentence in strip(segmenter(to_symbol_stream(text))))
            response = {'language': language, 'sentences': sentences}
        else:
            response = {'language': language}
        return response

    def check_disambiguate(params, data):
        """Check data and disambiguate it.
        
        First, check whether all data that is required by Handler.disambiguate
        is provided.  Then, return scored lexeme entries.

        """
        if isinstance(data, EmptyBodyException):
            raise UnprocessableEntityError('Message body missing')
        if type(data) != dict:
            raise UnprocessableEntityError('Malformed message body')
        if 'lang' not in params:
            raise BadRequestError("Language 'lang' missing")
        if 'i' not in data:
            raise BadRequestError("Token index 'i' missing")
        if 'tokens' not in data:
            raise BadRequestError("Tokens 'tokens' missing")
        return Handler.disambiguate(data['tokens'], int(data['i']), params['lang'])


    def disambiguate(tokens, i, language):
        """Disambiguate the token at index ``i`` for the specified language."""
        if language != JAPANESE:
            raise NotImplementedError('Language not supported')
        return {'language': language, 'lexemes': wsd.disambiguate(tokens, i)}


    def do_OPTIONS(self):
        """Respond to an HTTP OPTIONS request.
        
        Allow the HTTP POST method for cross-origin resource sharing (CORS).

        """
        self.send_response(200)         # OK
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Allow', 'POST')
        self.send_header('Access-Control-Allow-Methods', 'POST')
        self.end_headers()
    
    def handle_POST(self):
        """Read the URL of a HTTP POST request and call the appropriate function
        to process the API call.
        
        .. seealso:: :py:meth:`Handler.do_POST`

        """
        if re.match('^/%s/%s(\\?|/?$)' % (TOKEN_SERVANT, TOKEN_SERVICE), self.path):
            params_str = (self.path[len(TOKEN_SERVANT)+len(TOKEN_SERVICE)+3:]
                          if re.match('^/%s/%s\\?' % (TOKEN_SERVANT, TOKEN_SERVICE), self.path)
                          else '')
            params = Handler.parse_params(params_str)
            try:
                data = self.parse_body()
            except EmptyBodyException as exception:
                return Handler.check_tokenize(params, exception)
            else:
                return Handler.check_tokenize(params, data)
        elif re.match('^/%s/%s(\\?|/?$)' % (WSD_SERVANT, WSD_SERVICE), self.path):
            params_str = (self.path[len(WSD_SERVANT)+len(WSD_SERVICE)+3:]
                          if re.match('^/%s/%s\\?' % (WSD_SERVANT, WSD_SERVICE), self.path)
                          else '')
            params = Handler.parse_params(params_str)
            try:
                data = self.parse_body()
            except EmptyBodyException as exception:
                return Handler.check_disambiguate(params, exception)
            else:
                return Handler.check_disambiguate(params, data)
        else:
            raise NotFoundError('Nonexistent location')

    def do_POST(self):
        """Respond to an HTTP POST request.
        
        Mainly handle server errors globally and finalize the response.
        
        Rather than for updating a resource on the server, POST is used as a
        substitute for GET to fetch content, since GET does not support sending
        the necessary message body from the client side.
        
        .. seealso:: :py:meth:`Handler.handle_POST`
        
        """
        try:
            response = self.handle_POST()
        except Exception as error:
            if isinstance(error, BadRequestError):
                self.send_response(400) # BAD REQUEST
                error_message = str(error)
            elif isinstance(error, NotFoundError):
                self.send_response(404) # NOT FOUND
                error_message = str(error)
            elif isinstance(error, UnsupportedMediaTypeError):
                self.send_reponse(415)  # UNSUPPORTED MEDIA TYPE
                error_message = str(error)
            elif isinstance(error, TypeError) or isinstance(error, ValueError):
                self.send_response(422) # UNPROCESSABLE ENTITY
                error_message = 'Semantically malformed request'
            elif isinstance(error, UnprocessableEntityError):
                self.send_response(422) # UNPROCESSABLE ENTITY
                error_message = str(error)
            elif isinstance(error, NotImplementedError):
                self.send_response(501) # NOT IMPLEMENTED
                error_message = 'Not implemented'
            else:
                self.send_response(500) # INTERNAL SERVER ERROR
                error_message = 'Internal server error'
            self.send_header('Content-Type', 'text/plain')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            # Write the error message to the response body.  For security
            # purposes, internal error messages have been masked.
            if Handler.debug:
                print(traceback.format_exc(), file=sys.stderr)
            self.wfile.write((error_message + '\n\n' + traceback.format_exc()
                              if Handler.debug
                              else error_message).encode('ascii'))
        else:
            self.send_response(200)     # OK
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode('ascii'))

@click.command()
@click.option('--debug/--no-debug', default=Handler.debug)
def main(debug):
    """Start the server."""
    Handler.debug = debug
    if Handler.debug:
        print('RUNNING IN \033[31mDEBUG MODE\033[0m')
    else:
        print('RUNNING IN \033[32mPRODUCTION MODE\033[0m')
    try:
        server = HTTPServer(('localhost', PORT), Handler)
        print('Started server on port %d...' % (PORT,))
        server.serve_forever()
    except KeyboardInterrupt:
        print('User requested shutdown, exiting...')
        server.socket.close()

if __name__ == '__main__':
    main()
