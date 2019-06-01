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


def is_reading(phrase):
    """Determine whether the specified phrase is a reading representation.

    Reading representations contain only characters from the hiragana, hiragana
    phonetic extensions, katakana and katakana phonetic extensions unicode
    blocks, as well as the wave dash (U+301c) and the fullwidth tilde (U+ff5e).
    The unused code points U+3040, U+3097 and U+3091 are excluded.

    Phrases that consist **only** of the wave dash, the fullwidth tilde, or the
    katakana middle dot (U+30fb) are **not** considered readings.  In JMdict,
    they are used as the headlines for descriptive entries for these forms of
    punctuation.

    Args:
        phrase (str): The phrase to test.

    Returns:
        bool: True if the specified phrase is a reading representation, False
            otherwise.
    """
    # TODO Use above ranges instead of explicit hex codes
    return (all((ord(c) >= 0x3041 and ord(c) <= 0x3096) # Hiragana
                or (ord(c) >= 0x3099 and ord(c) <= 0x309f)
                or (ord(c) >= 0x30a0 and ord(c) <= 0x30ff) # Katakana
                or (ord(c) >= 0x31f0 and ord(c) <= 0x31ff)
                or c == '〜'             # Wave dash
                or c == '～'             # Fullwidth tilde
                for c in list(phrase))
            and not phrase == '・'
            and not phrase == '〜'
            and not phrase == '～')


def hiragana_to_katakana(phrase):
    """Convert hiragana to katakana.

    Do not handle the use of prolonged sound marks.
    """
    return ''.join(
        [chr(i + 0x60
             if (i >= 0x3041 and i <= 0x3096) or i == 0x309d or i == 0x309e
             else i)
         for i in [ord(c) for c in list(phrase)]])
