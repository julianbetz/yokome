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


import json


def list_as_tuple_hook(x):
    return {key: tuple(value)
            if isinstance(value, list)
            else value
            for key, value in x.items()}


def quote(value):
    """Quote a value unambigously w.r.t. its data type.

    The result can be used during import into a relational database.

    :param value: The value to transform.

    :return: ``'null'`` if ``value`` is ``None``, ``'true'`` if it is ``True``,
        ``'false' if it is ``False``.  For numeric values, the result is the
        corresponding string representation.  Infinite values are represented by
        ``'inf'`` and ``'-inf'``, respectively;  not-a-number is represented by
        ``'nan'``.  For strings, the result is the string itself, surrounded by
        ``'"'``, and with the characters ``'"'``, ``'\\'``, ``'\\b'``,
        ``'\\t'``, ``'\\n'``, ``'\\v'``, ``'\\f'`` and ``'\\r'`` escaped using
        ``'\\'``.
    
    :raises TypeError: If ``value`` is neither ``None`` nor of type ``bool``,
            ``int``, ``float`` or ``str``.

    """
    if value is None:
        return 'null'
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, int) or isinstance(value, float):
        return str(value)
    if isinstance(value, str):
        # Use double quotation marks around all strings (and only around
        # strings), so that strings can be identified by them, and the special
        # values ``null``, ``false``, ``true``, ``inf``, ``-inf`` and ``nan``
        # can be identified by the absence of quotations marks.
        return ('"' + value.replace('\\', '\\\\').replace('"', '\\"').replace('\b', '\\b').replace('\t', '\\t').replace('\n', '\\n').replace('\v', '\\v').replace('\f', '\\f').replace('\r', '\\r') + '"')
    raise TypeError('Unable to quote value of type %r'
                    % (type(value).__name__,))


def write_quoted(file, row):
    """Write a row of quoted CSV values to a file.

    The values in ``row`` are quoted so that their data type can be detected
    unambiguously (see :py:func:`yokome.util.persistence.quote` for a detailed
    explanation).  Furthermore, they are separated by the character ``','``.
    Lines are separated with ``'\\n'``.

    :param file: The file to write to.  It has to be open.
    :param row: An iterable of data values.

    """
    file.write(','.join(map(quote, row)) + '\n')
