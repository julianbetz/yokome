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
from subprocess import Popen, PIPE
from urllib.parse import unquote_plus
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import sqlite3 as sql

if __name__ == '__main__':
    sys.path.append(os.path.abspath(os.path.dirname(os.path.abspath(__file__))
                                    + '/../..'))
    from src.data.jpn import hiragana_to_katakana
else:
    from ..data.jpn import hiragana_to_katakana

# Server settings

PORT = 5003
"""int: Server port to start on."""

SERVANT = 'tokenizer'
"""str: Tokenizer API location."""

SERVICE = 'tokenize'
"""str: Tokenization API location for tokenizer API."""


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

DATABASE_FILE = os.path.abspath(os.path.expanduser(
    os.path.dirname(os.path.abspath(__file__)) + '/../../data/processed/JMdict.db'))
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

def longest_common_prefix_len(a, b):
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            return i
    return i + 1

def to_dict(token):
    """Turn an array of JUMAN++-style token annotations into a dictionary."""
    assert ((token[0] == ' ') == ('代表表記: / ' in token[11])
            and (token[0] == ' ') == (token[11] == '代表表記: / ')
            and '  ' not in token[11])
    surface_graphic = token[0]
    surface_phonetic = token[1]
    uninflected_graphic = token[2]
    # Heuristic: Assume that morphological changes are only applied to the ends
    # of words
    lcp = longest_common_prefix_len(surface_graphic, uninflected_graphic)
    lcs = len(surface_graphic) - lcp
    uninflected_phonetic = (surface_phonetic[:len(surface_phonetic) - lcs]
                            + uninflected_graphic[lcp:])
    pos_broad = token[3]
    pos_fine = token[5]                 # May contain '*' (i.e. null) value
    inflection_type = token[7]          # May contain '*' (i.e. null) value
    try:
        pos = JUMAN_TRANSLATOR[pos_broad][pos_fine][inflection_type]
    except KeyError:
        pos = []
        # TODO Use logger instead
        print('\033[33mWARN\033[0m POS tags %r %r %r not found'
              % (pos_broad, pos_fine, inflection_type))
    if '代表表記:' not in token[11]:
        # For unknown lemmas use the uninflected representations (may fail to
        # map different graphical variants to the same lexeme)
        lemma = {'graphic': uninflected_graphic,
                 'phonetic': uninflected_phonetic}
    elif token[0] == ' ':
        lemma = {'graphic': ' ', 'phonetic': ' '}
    else:
        lemma = re.search('代表表記:([^ ]*)', token[11]).group(1).split('/')
        # '/' is not subject to morphological changes, so there is always an odd
        # number of slashes in the above matched string
        lemma = {'graphic': '/'.join(lemma[:len(lemma) // 2]),
                 'phonetic': '/'.join(lemma[len(lemma) // 2:])}
    # Remove copula part of na-adjectives and no-adjectives
    # TODO Monitor whether this may lead to unexpected results
    if inflection_type in {'ナ形容詞', 'ナ形容詞特殊', 'ナノ形容詞'}: # TODO Check whether this exactly conforms to the inflections used by JUMAN++
        if uninflected_graphic[-1] == 'だ':
            uninflected_graphic = uninflected_graphic[:-1]
            uninflected_phonetic = uninflected_phonetic[:-1]
        if lemma['graphic'][-1] == 'だ':
            lemma['graphic'] = lemma['graphic'][:-1]
            lemma['phonetic'] = lemma['phonetic'][:-1]
        # XXX Create new tokens for copula
    # TODO Remove "v" from lemma form of nominalized verbs and turn phonetic
    # representation into katakana for better interoperability with JMdict
    return {
        # Inflected form as it was found in the text, along with its reading
        'surface_form': {'graphic': surface_graphic,
                         'phonetic': surface_phonetic},
        # Uninflected form for both graphic representation and reading, may
        # be different from the lemma for different graphic variants of the
        # same lexeme
        'base_form': {'graphic': uninflected_graphic,
                      'phonetic': uninflected_phonetic},
        # Canonical form for both graphic reprepresentation and reading,
        # intended to be unique for all variants of a lexeme
        'lemma': lemma,
        'pos': pos,
        'inflection': [] if token[9] == '*' else [token[9]],
        # XXX Use a regex that captures a note directly, without relying on
        #     the assertion above
        # XXX Analyze the notes' substructure
        'notes': ([] if token[11] == ''
                  else [token[11]] if token[0] == ' '
                  # XXX Not covered by the assertions: Space could occur
                  #     within one note
                  else token[11].split(' '))}

def match_reading(splits):
    """Match graphic and phonetic word representations and lemma.
    
    Discern the notations '\ ' for space and '\' for backslash (with ' ' as
    field separator) in JUMAN++ output.

    Args: 
        splits (list<str>): section for word token (graphic), word token
            (phonetic), and lemma, split on ' ' from a joint string
            representation with ' ' as separator.  The input may contain more
            than three elements.
    """
    # Space and backslash do not take part in morphological variations, thus all
    # three annotations contain the same number of splits
    assert len(splits) % 3 == 0
    i = len(splits) // 3
    # After discriminating word token (graphic), word token (phonetic) and
    # lemma, all sequences of '\ ' necessarily denote spaces, not backslashes
    return [re.sub('\\\\ ', ' ', ' '.join(splits[j*i:(j+1)*i]))
            for j in range(3)]

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

    def tokenize(expression, language=None):
        """Tokenize the specified expression for the specified language.
        
        Attempt to detect the language of the expression if no language is
        provided.  For Japanese, apply the JUMAN++ morphological analyzer
        (Morita et al. 2015).
        """
        if language is None:
            language = detect_language(expression)
        if language == JAPANESE:
            # Call JUMAN++ Japanese morphological analyzer
            process = Popen(['jumanpp'], stdin=PIPE, stdout=PIPE, stderr=PIPE)
            output, error = process.communicate(input=expression.encode())
            # TODO Detect process failure
            # TODO Handle error messages
            
            # Parse tokenizer output format
            # 
            # The output is one-token-per-line, with space-separated
            # annotations.  There are twelve annotations for regular tokens and
            # twelve annotations and an additional '@ ' at the beginning of
            # lines to mark the beginning of alternatives for a preceding
            # regular token.
            # 
            # Start processing from the end, since there are ambiguities for the
            # first three annotation types: Spaces are denoted as '\ ', while
            # backslashes are denoted by '\' only, resulting in conflicting
            # interpretations for '\ ' as "space", and "backslash" + "end of
            # annotation", respectively.
            #
            # Furthermore, '"' is not escaped or enclosed in single quotation
            # marks, while the last annotation, if existent, is always enclosed
            # in double quotation marks.  Thus, manual line splitting is
            # necessary, and cannot be done via shlex.
            #
            # The remaining annotation types seem to be a fixed set of keywords,
            # with odd and even annotations encoding the same information, once
            # in string form and once as a numerical ID.
            output = [line for line in output.decode().split('\n')
                      if line != 'EOS' and line != '']
            assert all([line.endswith(' NIL')
                        or re.match('^"[^"]*" ', line[::-1]) is not None
                        for line in output])
            output = [re.fullmatch('^(.*) ("[^"]*"|NIL)$', line).groups()
                      for line in output]
            output = [[rest.split(' '), ('' if notes == 'NIL' else notes[1:-1])]
                      for rest, notes in output]
            assert all(len(rest) >= 11 for rest, _ in output)
            output = [((['@'] + match_reading(rest[1:-8]))
                       if (rest[0] == '@'
                           # '@' itself has only one morphological variant
                           and (rest[-9] != '@' or len(rest[:-8]) > 3))
                       else match_reading(rest[:-8]))
                      + rest[-8:] + [notes]
                      for rest, notes in output]
            # If passing all asserts up to this point in this function and in
            # match_reading, the output is now an array version of the output
            # format of JUMAN++, so as to fulfill the following condition:
            # 
            #     ``assert all([len(line) == 12 or
            #                   (line[0] == '@' and len(line) == 13)
            #                   for line in output])``
            tokens = []
            for line in output:
                if len(line) <= 12:
                    tokens.append([to_dict(line)])
                else:
                    assert len(tokens) > 0
                    tokens[-1].append(to_dict(line[1:]))
            response = {'language': language, 'tokens': tokens}
        else:
            response = {'language': language}
        return response

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
        
        See also:
            Handler.do_POST
        """
        if re.match('^/%s/%s(\\?|/?$)' % (SERVANT, SERVICE), self.path):
            params_str = (self.path[len(SERVANT)+len(SERVICE)+3:]
                          if re.match('^/%s/%s\\?' % (SERVANT, SERVICE), self.path)
                          else '')
            params = Handler.parse_params(params_str)
            try:
                data = self.parse_body()
            except EmptyBodyException as exception:
                return Handler.check_tokenize(params, exception)
            else:
                return Handler.check_tokenize(params, data)
        else:
            raise NotFoundError('Nonexistent location')

    def do_POST(self):
        """Respond to an HTTP POST request.
        
        Mainly handle server errors globally and finalize the response.
        
        Rather than for updating a resource on the server, POST is used as a
        substitute for GET to fetch content, since GET does not support sending
        the necessary message body from the client side.
        
        See also:
            Handler.handle_POST
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
