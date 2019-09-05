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


# XXX Maybe these ranges can be used for language detection vs. Chinese:
#     Bopomofo: (0x3100, 0x312f)
#     Bopomofo extended: (0x31a0, 0x31bf)


"""This package makes extensive use of symbol streams.  To understand how this
data structure is defined, see :mod:`.symbol_stream`.

"""


import os
import asyncio
import re
import json
from subprocess import Popen, PIPE
from nltk.corpus.reader.chasen import ChasenCorpusReader

from .symbol_stream import in_ranges, to_text, expand
from ..util.concurrency import SubprocessLock
from ..util.persistence import list_as_tuple_hook


def longest_common_prefix_len(a, b):
    """Determine the length of the longest common prefix of two strings.

    :param str a: The first string.

    :param str b: The second string.

    :return: The length of the longest common prefix of both strings.

    """
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            return i
    return i + 1


_JUMAN_TRANSLATOR_FILE = os.path.abspath(
    os.path.dirname(os.path.abspath(__file__))
    + '/../../data/crafted/juman_pos_translator.json')
with open(_JUMAN_TRANSLATOR_FILE, 'r') as f:
    JUMAN_TRANSLATOR = json.load(f, object_hook=list_as_tuple_hook)
def _flatten_dict(d):
    for value in d.values():
        if isinstance(value, dict):
            for v in _flatten_dict(value):
                yield v
        else:
            yield value
JUMAN_UNDETERMINABLE_POS = set(_flatten_dict(JUMAN_TRANSLATOR['未定義語']))

# TODO Missing: Vertical forms
BRACKET_DICT = {ord('「'): ord('」'),
                ord('『'): ord('』'),
                ord('（'): ord('）'),
                ord('［'): ord('］'),
                ord('〚'): ord('〛'),
                ord('｛'): ord('｝'),
                ord('【'): ord('】'),
                ord('〖'): ord('〗'),
                ord('〔'): ord('〕'),
                ord('〘'): ord('〙'),
                ord('〈'): ord('〉'),
                ord('《'): ord('》'),
                ord('('): ord(')'),
                ord('['): ord(']'),
                ord('{'): ord('}'),
                ord('︗'): ord('︘'),
                ord('︵'): ord('︶'),
                ord('︷'): ord('︸'),
                ord('︹'): ord('︺'),
                ord('︻'): ord('︼'),
                ord('︽'): ord('︾'),
                ord('︿'): ord('﹀'),
                ord('﹁'): ord('﹂'),
                ord('﹃'): ord('﹄'),
                ord('﹇'): ord('﹈')}
OPENING_BRACKETS = set(BRACKET_DICT.keys())
CLOSING_BRACKETS = set(BRACKET_DICT.values())
OPENING_QUOTATION = {ord('「'), ord('『'), ord('﹁'), ord('﹃')}
CLOSING_QUOTATION = {ord('」'), ord('』'), ord('﹂'), ord('﹄')}
assert OPENING_QUOTATION <= OPENING_BRACKETS
assert CLOSING_QUOTATION <= CLOSING_BRACKETS

# TODO Missing: Vertical forms
SENTENCE_END_PUNCTUATION = {ord('。'), ord('？'), ord('！'),
                            ord('.'), ord('?'), ord('!')}
assert SENTENCE_END_PUNCTUATION.isdisjoint(OPENING_BRACKETS | CLOSING_BRACKETS)

WHITESPACE = {ord('　'), ord(' '), ord('\t'), ord('\n')}
assert WHITESPACE.isdisjoint(OPENING_BRACKETS
                             | CLOSING_BRACKETS
                             | SENTENCE_END_PUNCTUATION)

DIGIT = set(tuple(s for s in range(0x0030, 0x0039 + 1))
            + tuple(s for s in range(0xff10, 0xff19 + 1)))
DIGIT_PUNCTUATION = {ord('.'), ord(','), ord('．'), ord('，')}
assert DIGIT.isdisjoint(WHITESPACE
                        | SENTENCE_END_PUNCTUATION
                        | CLOSING_QUOTATION)
assert DIGIT_PUNCTUATION.isdisjoint(WHITESPACE
                                    | OPENING_BRACKETS
                                    | CLOSING_BRACKETS)

# Ligatures
HIRAGANA_DIGRAPH = 0x309f
KATAKANA_DIGRAPH = 0x30ff
# Voice marks
COMBINING_KANA_VOICED_SOUND_MARK = 0x3099
COMBINING_KANA_SEMI_VOICED_SOUND_MARK = 0x309a
KANA_VOICED_SOUND_MARK = 0x309b
KANA_SEMI_VOICED_SOUND_MARK = 0x309c
# Iteration/repetition marks
HIRAGANA_ITERATION_MARK = 0x309d
HIRAGANA_VOICED_ITERATION_MARK = 0x309e
KATAKANA_ITERATION_MARK = 0x30fd
KATAKANA_VOICED_ITERATION_MARK = 0x30fe
REPEAT_MARK = 0x3031
VOICED_REPEAT_MARK = 0x3032
UPPER_REPEAT_MARK = 0x3033
UPPER_VOICED_REPEAT_MARK = 0x3034
LOWER_REPEAT_MARK = 0x3035
LARGE_REPEAT_MARK = (UPPER_REPEAT_MARK, LOWER_REPEAT_MARK)
LARGE_VOICED_REPEAT_MARK = (UPPER_VOICED_REPEAT_MARK, LOWER_REPEAT_MARK)
LARGE_REPEAT_MARK_MISSPELLING = (0xff0f, 0xff3c)
LARGE_VOICED_REPEAT_MARK_MISSPELLING = (0xff0f, 0x2033, 0xff3c)
IDEOGRAPHIC_ITERATION_MARK = 0x3005
VERTICAL_IDEOGRAPHIC_ITERATION_MARK = 0x303b
ITERATION_MARKS = {HIRAGANA_ITERATION_MARK, HIRAGANA_VOICED_ITERATION_MARK,
                   KATAKANA_ITERATION_MARK, KATAKANA_VOICED_ITERATION_MARK,
                   IDEOGRAPHIC_ITERATION_MARK,
                   VERTICAL_IDEOGRAPHIC_ITERATION_MARK}
# Character ranges
HIRAGANA_RANGES = ((0x3041, 0x3096),
                   (HIRAGANA_DIGRAPH, HIRAGANA_DIGRAPH))
KATAKANA_RANGES = ((0x30a1, 0x30fa),
                   (KATAKANA_DIGRAPH, KATAKANA_DIGRAPH),
                   (0x31f0, 0x31ff))
KANA_VOICING_RANGES = ((COMBINING_KANA_VOICED_SOUND_MARK,
                        KANA_SEMI_VOICED_SOUND_MARK),)
KANA_PUNCTUATION_RANGES = ((0x30a0, 0x30a0), (0x30fb, 0x30fc))
IDEOGRAPHIC_RANGES = ((0x2e80, 0x2ef3), # CJK radicals supplement
                      (0x2f00, 0x2fd5), # Kanxi radicals
                      (0x3400, 0x4dbf), # CJK unified ideographs extension A
                      (0x4e00, 0x9fff), # CJK unified ideographs
                      (0xf900, 0xfaff), # CJK compatibility ideographs
                      (0x20000, 0x2a6df), # CJK unified ideographs extension B
                      (0x2a700, 0x2b73f), # CJK unified ideographs extension C
                      (0x2b740, 0x2b81f), # CJK unified ideographs extension D
                      (0x2b820, 0x2ceaf), # CJK unified ideographs extension E
                      (0x2ceb0, 0x2ebef), # CJK unified ideographs extension F
                      (0x2f800, 0x2fa1f)) # CJK compatibility ideographs supplement
VOICABLE = {0x3046,
            0x304b, 0x304d, 0x304f, 0x3051, 0x3053,
            0x3055, 0x3057, 0x3059, 0x305b, 0x305d,
            0x305f, 0x3061, 0x3064, 0x3066, 0x3068,
            0x306f, 0x3072, 0x3075, 0x3078, 0x307b,
            0x309d,
            0x30a6,
            0x30ab, 0x30ad, 0x30af, 0x30b1, 0x30b3,
            0x30b5, 0x30b7, 0x30b9, 0x30bb, 0x30bd,
            0x30bf, 0x30c1, 0x30c4, 0x30c6, 0x30c8,
            0x30cf, 0x30d2, 0x30d5, 0x30d8, 0x30db,
            0x30ef, 0x30f0, 0x30f1, 0x30f2,
            0x30fd,}
SEMI_VOICABLE = {0x306f, 0x3072, 0x3075, 0x3078, 0x307b,
                 0x30cf, 0x30d2, 0x30d5, 0x30d8, 0x30db}
GLIDE_CHARS = {0x3041, 0x3043, 0x3045, 0x3047, 0x3049,
               0x3083, 0x3085, 0x3087, 0x308e,
               0x30a1, 0x30a3, 0x30a5, 0x30a7, 0x30a9,
               0x30e3, 0x30e5, 0x30e7, 0x30ee}
GEMINATION_CHARS = {0x3063, 0x30c3}
KANA_SMALL = (GLIDE_CHARS
              | GEMINATION_CHARS
              | {0x3095, 0x3096, 0x30f5, 0x30f6}
              | {s for s in range(0x31f0, 0x31ff + 1)})
ARCHAIC_CHARS = {0x3090, 0x3091, 0x30f0, 0x30f1}

_FULLWIDTH_FOLD_DICT = {
    # Space
    0x0020: 0x3000,
    # Latin characters
    0x0041: 0xff21,
    0x0042: 0xff22,
    0x0043: 0xff23,
    0x0044: 0xff24,
    0x0045: 0xff25,
    0x0046: 0xff26,
    0x0047: 0xff27,
    0x0048: 0xff28,
    0x0049: 0xff29,
    0x004a: 0xff2a,
    0x004b: 0xff2b,
    0x004c: 0xff2c,
    0x004d: 0xff2d,
    0x004e: 0xff2e,
    0x004f: 0xff2f,
    0x0050: 0xff30,
    0x0051: 0xff31,
    0x0052: 0xff32,
    0x0053: 0xff33,
    0x0054: 0xff34,
    0x0055: 0xff35,
    0x0056: 0xff36,
    0x0057: 0xff37,
    0x0058: 0xff38,
    0x0059: 0xff39,
    0x005a: 0xff3a,
    0x0061: 0xff41,
    0x0062: 0xff42,
    0x0063: 0xff43,
    0x0064: 0xff44,
    0x0065: 0xff45,
    0x0066: 0xff46,
    0x0067: 0xff47,
    0x0068: 0xff48,
    0x0069: 0xff49,
    0x006a: 0xff4a,
    0x006b: 0xff4b,
    0x006c: 0xff4c,
    0x006d: 0xff4d,
    0x006e: 0xff4e,
    0x006f: 0xff4f,
    0x0070: 0xff50,
    0x0071: 0xff51,
    0x0072: 0xff52,
    0x0073: 0xff53,
    0x0074: 0xff54,
    0x0075: 0xff55,
    0x0076: 0xff56,
    0x0077: 0xff57,
    0x0078: 0xff58,
    0x0079: 0xff59,
    0x007a: 0xff5a,
    # Halfwidth forms
    0xff61: 0x3002,
    0xff62: 0x300c,
    0xff63: 0x300d,
    0xff64: 0x3001,
    0xff65: 0x30fb,
    0xff66: 0x30f2,
    0xff67: 0x30a1,
    0xff68: 0x30a3,
    0xff69: 0x30a5,
    0xff6a: 0x30a7,
    0xff6b: 0x30a9,
    0xff6c: 0x30e3,
    0xff6d: 0x30e5,
    0xff6e: 0x30e7,
    0xff6f: 0x30c3,
    0xff70: 0x30fc,
    0xff71: 0x30a2,
    0xff72: 0x30a4,
    0xff73: 0x30a6,
    0xff74: 0x30a8,
    0xff75: 0x30aa,
    0xff76: 0x30ab,
    0xff77: 0x30ad,
    0xff78: 0x30af,
    0xff79: 0x30b1,
    0xff7a: 0x30b3,
    0xff7b: 0x30b5,
    0xff7c: 0x30b7,
    0xff7d: 0x30b9,
    0xff7e: 0x30bb,
    0xff7f: 0x30bd,
    0xff80: 0x30bf,
    0xff81: 0x30c1,
    0xff82: 0x30c4,
    0xff83: 0x30c6,
    0xff84: 0x30c8,
    0xff85: 0x30aa,
    0xff86: 0x30ab,
    0xff87: 0x30ac,
    0xff88: 0x30ad,
    0xff89: 0x30ae,
    0xff8a: 0x30cf,
    0xff8b: 0x30d2,
    0xff8c: 0x30d5,
    0xff8d: 0x30d8,
    0xff8e: 0x30db,
    0xff8f: 0x30ee,
    0xff90: 0x30ef,
    0xff91: 0x30f0,
    0xff92: 0x30f1,
    0xff93: 0x30f2,
    0xff94: 0x30e4,
    0xff95: 0x30e6,
    0xff96: 0x30e8,
    0xff97: 0x30e9,
    0xff98: 0x30ea,
    0xff99: 0x30eb,
    0xff9a: 0x30ec,
    0xff9b: 0x30ed,
    0xff9c: 0x30ef,
    0xff9d: 0x30f3,
    0xff9e: 0x3099,
    0xff9f: 0x309a}

# Letters, numbers
WORD_RANGES = (
    # Basic latin: digits
    (0x0030, 0x0039), 
    # Superscripts and subscripts
    (0x2070, 0x2070), (0x2074, 0x207e), (0x2080, 0x208e),
    # Number forms
    (0x2150, 0x217f), (0x2189, 0x2189),
    # CJK radicals supplement
    (0x2e80, 0x2ef3),
    # Kangxi radicals
    (0x2f00, 0x2fd5),
    # (Kanbun?)
    (0x2fe0, 0x2fef),
    # CJK symbols and punctuation: digits
    (0x3021, 0x3029), (0x3038, 0x303a),
    # Hiragana
    (0x3041, 0x3096), (0x3099, 0x309f),
    # Katakana
    (0x30a0, 0x30ff),
    # Kanbun
    (0x3190, 0x319f),
    # CJK strokes
    (0x31c0, 0x31e3),
    # Katakana phonetic extensions
    (0x31f0, 0x31ff),
    # CJK unified ideographs extension A
    (0x3400, 0x4dbf),
    # CJK unified ideographs
    (0x4e00, 0x9fff),
    # CJK compatibility ideographs
    (0xf900, 0xfaff),
    # Halfwidth and fullwidth forms: halfwidth katakana
    (0xff10, 0xff19), (0xff66, 0xff9f),
    # Kana supplement
    (0x1b000, 0x1b0ff),
    # Kana extended-A
    (0x1b100, 0x1b12f),
    # CJK unified ideographs extension B
    (0x20000, 0x2a6df),
    # CJK unified ideographs extension C
    (0x2a700, 0x2b73f),
    # CJK unified ideographs extension D
    (0x2b740, 0x2b81f),
    # CJK unified ideographs extension E
    (0x2b820, 0x2ceaf),
    # CJK unified ideographs extension F
    (0x2ceb0, 0x2ebef),
    # CJK compatibility ideographs supplement
    (0x2f800, 0x2fa1f))

# Whitespace, punctuation, units, currency symbols
SUPPLEMENTAL_RANGES = (
    # Control characters: '\t', '\n', '\r'
    (0x0009, 0x0009), (0x000a, 0x000a), (0x000d, 0x000d),
    # Basic latin: punct., currency
    (0x0020, 0x002f), (0x003a, 0x0040), (0x005b, 0x0060), (0x007b, 0x007e),
    # Latin-1 supplement: punct., currency
    (0x00a0, 0x00a7), (0x00a9, 0x00a9), (0x00ab, 0x00ae), (0x00b0, 0x00b3),
    (0x00b5, 0x00b7), (0x00b9, 0x00b9), (0x00bb, 0x00bf), (0x00d7, 0x00d7),
    (0x00f7, 0x00f7),
    # General punctuation
    (0x2000, 0x2064),
    (0x2066, 0x206f),
    # Currency symbols
    (0x20a0, 0x20cf),
    # Letterlike symbols: unit
    (0x2103, 0x2103), (0x2109, 0x2109), (0x2117, 0x2117), (0x2120, 0x2122),
    (0x213b, 0x213b),
    # Supplemental punctuation
    (0x2e00, 0x2e4e),
    # # Ideographic description characters
    # (0x2ff0, 0x2fff),
    # CJK symbols and punctuation: punctuation
    (0x3000, 0x3020), (0x3030, 0x3037), (0x303b, 0x303f),
    # Enclosed CJK letters and months: non-Korean
    (0x3220, 0x325f), (0x3280, 0x32fe),
    # CJK compatibility
    (0x3300, 0x33ff),
    # Vertical forms
    (0xfe10, 0xfe19),
    # CJK compatibility forms
    (0xfe30, 0xfe4f),
    # Small form variants
    (0xfe50, 0xfe52), (0xfe54, 0xfe66), (0xfe68, 0xfe6b),
    # Halfwidth and fullwidth forms: punctuation, currency
    (0xff01, 0xff0f), (0xff1a, 0xff20), (0xff3b, 0xff40), (0xff5b, 0xff65),
    (0xffe0, 0xffe6), (0xffe8, 0xffe8))

# Arrows, bullet points, enclosed symbols, pictographs, emoticons
MISC_SYMBOL_RANGES = (
    # Arrows
    (0x2190, 0x21ff),
    # Enclosed alphanumerics
    (0x2460, 0x24ff),
    # Box drawing
    (0x2500, 0x257f),
    # Block elements
    (0x2580, 0x259f),
    # Geometric shapes
    (0x25a0, 0x25ff),
    # Miscellaneous symbols
    (0x2600, 0x26ff),
    # Dingbats
    (0x2700, 0x27bf),
    # Supplemental arrows-A
    (0x27f0, 0x27ff),
    # Supplemental arrows-B
    (0x2900, 0x297f),
    # Miscellaneous symbols and arrows
    (0x2b00, 0x2b73), (0x2b76, 0x2b96), (0x2b98, 0x2bc8), (0x2bca, 0x2bfe),
    # Halfwidth and fullwidth forms: arrows, bullet points
    (0xffe9, 0xffee),
    # Enclosed alphanumeric supplement
    (0x1f100, 0x1f10c), (0x1f110, 0x1f16b), (0x1f170, 0x1f1ac),
    (0x1f1e6, 0x1f1ff),
    # Enclosed ideographic supplement: except for Chinese folk religion symbols
    (0x1f200, 0x1f202), (0x1f210, 0x1f23b), (0x1f240, 0x1f248),
    (0x1f250, 0x1f251),
    # Miscellaneous symbols and pictographs
    (0x1f300, 0x1f5ff),
    # Emoticons (Emoji)
    (0x1f600, 0x1f64f),
    # Ornamental dingbats
    (0x1f650, 0x1f67f),
    # Transport and map symbols
    (0x1f680, 0x1f6ff),
    # Geometric shapes extended
    (0x1f780, 0x1f7ff),
    # Supplemental arrows-C
    (0x1f800, 0x1f8ff),
    # Supplemental symbols and pictographs
    (0x1f900, 0x1f9ff))


def voice(char: int) -> int:
    """Return the voiced version of ``char``.

    :param int char: An unvoiced Unicode character to voice.

    :return: The Unicode character that is the voiced version of ``char``.

    """
    if char not in VOICABLE:
        raise ValueError('%r cannot be voiced' % (chr(char),))
    if char == 0x3046 or char == 0x30a6:
        return char + 0x004e
    if 0x30ef <= char and char <= 0x30f2:
        return char + 0x0008
    return char + 0x0001


def unvoice(char: int) -> int:
    """Return the unvoiced version of ``char``.

    :param int char: A voiced Unicode character to unvoice.

    :return: The Unicode character that is the unvoiced version of ``char``.

    """
    if 0x30f7 <= char and char <= 0x30fa:
        return char - 0x0008
    if char == 0x3094 or char == 0x30f4:
        return char - 0x004e
    if char - 0x0001 not in VOICABLE:
        raise ValueError('%r cannot be unvoiced' % (chr(char),))
    return char - 0x0001


VOICED = {voice(s) for s in VOICABLE}


def semivoice(char: int) -> int:
    """Return the semi-voiced version of ``char``.

    :param int char: An unvoiced Unicode character to semi-voice.

    :return: The Unicode character that is the semi-voiced version of ``char``.

    """
    if char not in SEMI_VOICABLE:
        raise ValueError('%r cannot be semi-voiced' % (chr(char),))
    return char + 0x0002


def unsemivoice(char: int) -> int:
    """Return the unvoiced version of ``char``.

    :param int char: A semi-voiced Unicode character to unvoice.

    :return: The Unicode character that is the unvoiced version of ``char``.

    """
    if char - 0x0002 not in SEMI_VOICABLE:
        raise ValueError('%r cannot be unsemi-voiced' % (chr(char),))
    return char - 0x0002


SEMI_VOICED = {semivoice(s) for s in SEMI_VOICABLE}


def is_reading(phrase: str) -> bool:
    """Determine whether the specified phrase is a reading representation.

    Reading representations contain only characters from the hiragana, hiragana
    phonetic extensions, katakana and katakana phonetic extensions unicode
    blocks, as well as the wave dash (U+301c) and the fullwidth tilde (U+ff5e).
    The unused code points U+3040, U+3097 and U+3091 are excluded.

    Phrases that consist **only** of the wave dash, the fullwidth tilde, or the
    katakana middle dot (U+30fb) are **not** considered readings.  In JMdict,
    they are used as the headlines for descriptive entries for these forms of
    punctuation.

    :param str phrase: The phrase to test.

    :return: ``True`` if the specified phrase is a reading representation,
        ``False`` otherwise.

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


def hiragana_to_katakana(phrase: str) -> str:
    """Convert hiragana to katakana.

    Do not handle the use of prolonged sound marks.

    :param str phrase: The phrase in which to replace all hiragana characters by
        katakana characters.

    """
    # TODO Use above ranges instead of explicit hex codes
    return ''.join(
        [chr(i + 0x60
             if (i >= 0x3041 and i <= 0x3096) or i == 0x309d or i == 0x309e
             else i)
         for i in [ord(c) for c in list(phrase)]])


# Does not check whether non-glide chars are valid
# Does not check how many glide chars are added
def to_morae(symbol_stream):
    """Group morae in a symbol stream.

    A mora is a subunit of a syllable that may consist of multiple characters.
    For Japanese, it is the logical unit of counting sounds of speech.  A
    Japanese syllable typically consists of one mora or two morae where the
    second mora prolongs the first.  A Japanese mora consists of a regular kana
    letter or a kana letter and an ensuing glide sound, e.g. "ち", "ゆ" or "ちゅ
    " (but not "ちゅう").

    :param symbol_stream: A stream over symbols.

    :return: A list of morae, each consisting of its symbols.

    """
    morae = []
    for symbol in symbol_stream:
        s, *original = symbol
        if s in GLIDE_CHARS and morae:
            morae[-1].append(symbol)
        else:
            morae.append([symbol])
    return morae


def _iteration_fold_once(iteration_symbols, other_symbols):
    morae = to_morae(other_symbols)
    if len(iteration_symbols) <= len(morae):
        iteration = []
        for i, iteration_symbol in enumerate(iteration_symbols):
            it_s, *original = iteration_symbol
            recurring_mora = (
                [(morae[-len(iteration_symbols) + i][0][0], iteration_symbol)]
                + [(mora_symbol[0], (None,))
                   for mora_symbol in morae[-len(iteration_symbols) + i][1:]])
            if (((it_s == HIRAGANA_ITERATION_MARK
                  or it_s == HIRAGANA_VOICED_ITERATION_MARK)
                 and not in_ranges(recurring_mora[0][0], HIRAGANA_RANGES))
                or ((it_s == KATAKANA_ITERATION_MARK
                     or it_s == KATAKANA_VOICED_ITERATION_MARK)
                    and not in_ranges(recurring_mora[0][0], KATAKANA_RANGES))
                or recurring_mora[0][0] in KANA_SMALL
                or recurring_mora[0][0] in SEMI_VOICED
                or ((it_s == VERTICAL_IDEOGRAPHIC_ITERATION_MARK
                     or it_s == IDEOGRAPHIC_ITERATION_MARK)
                    and (len(recurring_mora) > 1
                         or not in_ranges(recurring_mora[0][0],
                                          IDEOGRAPHIC_RANGES)))
                or recurring_mora[0][0] == HIRAGANA_DIGRAPH
                or recurring_mora[0][0] == KATAKANA_DIGRAPH):
                break
            if (it_s == HIRAGANA_ITERATION_MARK
                or it_s == KATAKANA_ITERATION_MARK):
                try:
                    recurring_mora[0] = (unvoice(recurring_mora[0][0]), iteration_symbol)
                except ValueError:
                    pass
            elif (it_s == HIRAGANA_VOICED_ITERATION_MARK
                  or it_s == KATAKANA_VOICED_ITERATION_MARK):
                try:
                    recurring_mora[0] = (voice(recurring_mora[0][0]), iteration_symbol)
                except ValueError:
                    if recurring_mora[0][0] not in VOICED:
                        break
            iteration.append(recurring_mora)
        else:
            for mora in morae + iteration:
                for out in mora:
                    yield out
            return
    # Fallback: yield input verbatim
    for out in other_symbols + iteration_symbols:
        yield out


def iteration_fold(symbol_stream):
    """Normalize words with iteration marks.

    Replace each kana/kanji iteration mark with the characters it stands for.

    :param symbol_stream: A stream over symbols.

    :return: A symbol stream like the input symbol stream, with iteration
        characters replaced by the characters that they stand for.

    """
    iteration_symbols = []
    other_symbols = []
    for symbol in symbol_stream:
        s, *original = symbol
        if s in ITERATION_MARKS:
            iteration_symbols.append(symbol)
        else:
            if iteration_symbols:
                for out in _iteration_fold_once(iteration_symbols,
                                                other_symbols):
                    yield out
                iteration_symbols = []
                other_symbols = []
            other_symbols.append(symbol)
    for out in _iteration_fold_once(iteration_symbols, other_symbols):
        yield out


# TODO
#
# XXX Add support for voiced repetition mark misspelings using voiced sound mark
# and combining voiced sound mark
def repetition_contraction(symbol_stream):
    """Contract representations of repetition symbols in the input stream.

    :param symbol_stream: A stream over symbols.

    :return: A symbol stream like the input symbol stream, with repetition
        symbols contracted to one symbol only.

    """
    repetition_symbols = ()
    for symbol in symbol_stream:
        s, *original = symbol
        if s == UPPER_REPEAT_MARK or s == UPPER_VOICED_REPEAT_MARK:
            for out in repetition_symbols:
                yield out
            repetition_symbols = (symbol,)
            continue
        elif s == LOWER_REPEAT_MARK:
            if len(repetition_symbols) == 1:
                if repetition_symbols[0][0] == UPPER_REPEAT_MARK:
                    yield (REPEAT_MARK, repetition_symbols[0], symbol)
                    repetition_symbols = ()
                    continue
                if repetition_symbols[0][0] == UPPER_VOICED_REPEAT_MARK:
                    yield (VOICED_REPEAT_MARK, repetition_symbols[0], symbol)
                    repetition_symbols = ()
                    continue
        elif s == 0xff0f:
            for out in repetition_symbols:
                yield out
            repetition_symbols = (symbol,)
            continue
        elif s == 0x2033:
            if len(repetition_symbols) == 1 and repetition_symbols[0][0] == 0xff0f:
                repetition_symbols += (symbol,)
                continue
        elif s == 0xff3c:
            if len(repetition_symbols) == 1 and repetition_symbols[0][0] == 0xff0f:
                yield (REPEAT_MARK, repetition_symbols[0], symbol)
                repetition_symbols = ()
                continue
            if len(repetition_symbols) == 2:
                yield (VOICED_REPEAT_MARK, repetition_symbols[0], repetition_symbols[1], symbol)
                repetition_symbols = ()
                continue
        if repetition_symbols:
            # Fallback: yield input verbatim
            for out in repetition_symbols:
                yield out
            repetition_symbols = ()
        yield symbol
    for out in repetition_symbols:
        yield out


def _mid_split(phrase):
    if phrase == '':
        return '', ''
    if len(phrase) % 2 == 1:
        return None
    first_repetition = phrase[:len(phrase) // 2]
    second_repetition = phrase[len(phrase) // 2:]
    first_char = ord(first_repetition[0])
    if second_repetition == first_repetition:
        return first_repetition, second_repetition
    if (first_char in VOICABLE
        and second_repetition
        == chr(voice(first_char)) + first_repetition[1:]):
        return first_repetition, second_repetition
    return None
        

# # FIXME
# def _validate_repeat_marks(last_token_alternatives, repeat_marks):
#     first_char = ord(last_token_alternatives[0]['surface_form']['graphic'][0])
#     return ((all(repeat_mark[0]['surface_form']['graphic'] == chr(REPEAT_MARK) for repeat_mark in repeat_marks)
#              and in_ranges(first_char, HIRAGANA_RANGES + KATAKANA_RANGES + IDEOGRAPHIC_RANGES))
#             or (all(repeat_mark[0]['surface_form']['graphic'] == chr(VOICED_REPEAT_MARK) for repeat_mark in repeat_marks)
#                 and ((first_char in VOICABLE and len(repeat_marks) < 2) or first_char in VOICED or in_ranges(first_char, IDEOGRAPHIC_RANGES)))
#             or (all(repeat_mark[0]['surface_form']['graphic'] == chr(REPEAT_MARK) if i % 2 == 0 else repeat_mark[0]['surface_form']['graphic'] == chr(VOICED_REPEAT_MARK) for i, repeat_mark in enumerate(repeat_marks, start=1))
#                 and (first_char in VOICABLE or first_char in VOICED or in_ranges(first_char, IDEOGRAPHIC_RANGES)))
#             or (all(repeat_mark[0]['surface_form']['graphic'] == chr(REPEAT_MARK) if i % 2 == 1 else repeat_mark[0]['surface_form']['graphic'] == chr(VOICED_REPEAT_MARK) for i, repeat_mark in enumerate(repeat_marks, start=1))
#                 and first_char in VOICED or in_ranges(first_char, IDEOGRAPHIC_RANGES)))


# # FIXME
# def _repetition_fold_once(text_pre, last_token_alternatives, repeat_marks, text_post, tokenizer):
#     if last_token_alternatives is None:
#         for repeat_mark in repeat_marks:
#             yield repeat_mark
#         return
#     if not repeat_marks:
#         yield last_token_alternatives
#         return
#     if not _validate_repeat_marks(last_token_alternatives, repeat_marks):
#         # Fallback
#         yield last_token_alternatives
#         for repeat_mark in repeat_marks:
#             yield repeat_mark
#         return        
#     folded_token_alternatives = []
#     first_repetition = last_token_alternatives[0]['surface_form']['graphic']
#     first_char = ord(first_repetition[0])
#     if repeat_marks[0][0]['surface_form']['graphic'] == chr(VOICED_REPEAT_MARK):
#         if first_char in VOICABLE:
#             second_repetition = chr(voice(first_char)) + last_token_alternatives[0]['surface_form']['graphic'][1:]
#         else:
#             second_repetition = first_repetition
#     else:
#         second_repetition = first_repetition
#     tokens = [token_alternatives for token_alternatives in tokenizer(text_pre + '\t' + first_repetition + second_repetition + '\t' + text_post, True)]
#     # JUMAN++ returns exactly one list of token alternatives for the part
#     # surrounded with tabs when called with partially annotated text. Find this
#     # token list
#     l = 0
#     for token_alternatives in tokens:
#         if l >= len(text_pre):
#             break
#         l += len(token_alternatives[0]['surface_form']['graphic'])
#     token_alternatives = tuple((token, _mid_split(token['surface_form']['phonetic'])) for token in token_alternatives if token['pos'] not in JUMAN_UNDETERMINABLE_POS)
#     token_alternatives = tuple((token, mid_split) for token, mid_split in token_alternatives if mid_split is not None)
#     for token, mid_split in token_alternatives:
#         token['surface_form']['graphic'] = first_repetition
#         for repeat_mark in repeat_marks:
#             token['surface_form']['graphic'] += repeat_mark[0]['surface_form']['graphic']
#         token['surface_form']['phonetic'] *= (len(repeat_marks) + 1) // 2
#         if len(repeat_marks) % 2 == 0:
#             token['surface_form']['phonetic'] += mid_split[0]
#     if token_alternatives:
#         yield tuple(token for token, _ in token_alternatives)
#     else:
#         yield last_token_alternatives
#         for repeat_mark in repeat_marks:
#             yield repeat_mark


# # FIXME
# def repetition_fold(char_stream, tokenizer):
#     text = to_text(s for s, *original in repetition_contraction((c,) for c in char_stream))
#     if chr(REPEAT_MARK) in text or chr(VOICED_REPEAT_MARK) in text:
#         last_token_alternatives = None
#         last_offset = 0
#         repeat_marks = []
#         assert '\t' not in text             # Would break JUMAN++ tokenization of
#                                             # partially annotated text
#         for token_alternatives in tokenizer(text):
#             assert len(token_alternatives) > 0 and all(len(token_alternative['surface_form']['graphic']) == len(token_alternatives[0]['surface_form']['graphic']) for token_alternative in token_alternatives)
#             # print(token_alternatives)
#             if (len(token_alternatives) == 1
#                 and (token_alternatives[0]['surface_form']['graphic']
#                      == chr(REPEAT_MARK)
#                      or token_alternatives[0]['surface_form']['graphic']
#                      == chr(VOICED_REPEAT_MARK))):
#                 repeat_marks.append(token_alternatives)
#             else:
#                 segment_len = ((0 if last_token_alternatives is None
#                                 else len(last_token_alternatives[0]['surface_form']['graphic']))
#                                + sum(len(repeat_mark[0]['surface_form']['graphic'])
#                                      for repeat_mark in repeat_marks))
#                 for o in _repetition_fold_once(text[:last_offset], last_token_alternatives, repeat_marks, text[last_offset+segment_len:], tokenizer):
#                     yield o
#                 last_token_alternatives = token_alternatives
#                 last_offset += segment_len
#                 repeat_marks = []
#         segment_len = ((0 if last_token_alternatives is None
#                         else len(last_token_alternatives[0]['surface_form']['graphic']))
#                        + sum(len(repeat_mark[0]['surface_form']['graphic'])
#                              for repeat_mark in repeat_marks))
#         for o in _repetition_fold_once(text[:last_offset], last_token_alternatives, repeat_marks, text[last_offset+segment_len:], tokenizer):
#             yield o
#     else:
#         for token_alternatives in tokenizer(text):
#             yield token_alternatives
        

# def segmenter(symbol_stream):
#     """Accept a stream of symbols and yield symbol streams for each sentence.

#     Assert balanced bracketing.
    
#     """
#     NON_CONTENT_CHARS = (WHITESPACE | SENTENCE_END_PUNCTUATION
#                          | OPENING_BRACKETS | CLOSING_BRACKETS)
#     bracketing_level = 0
#     end_of_quotation = False
#     end_of_sentence = False
#     end_of_paragraph = False
#     output = []
#     for symbol in symbol_stream:
#         s = symbol[0]
#         if s in WHITESPACE:
#             # In-sentence spaces are removed from the JEITA corpus, so we can
#             # interpret whitespace outside of bracketed groups as paragraph
#             # breaks and remove this whitespace from sentence ends/beginnings.
#             if bracketing_level <= 0:
#                 end_of_paragraph = True
#             else:
#                 output.append(symbol)
#         elif bracketing_level <= 0 and s in SENTENCE_END_PUNCTUATION:
#             if end_of_paragraph:
#                 if not all(o in NON_CONTENT_CHARS for o, *_ in output):
#                     yield (out for out in output)
#                 output = []
#             end_of_sentence = True
#             end_of_paragraph = False
#             output.append(symbol)
#         else:
#             if (end_of_paragraph
#                 or end_of_sentence
#                 or (end_of_quotation and s in OPENING_QUOTATION)):
#                 if not all(o in NON_CONTENT_CHARS for o, *_ in output):
#                     yield (out for out in output)
#                 output = []
#             end_of_quotation = False
#             end_of_sentence = False
#             end_of_paragraph = False
#             output.append(symbol)
#             if s in OPENING_BRACKETS:
#                 bracketing_level += 1
#             elif s in CLOSING_BRACKETS:
#                 bracketing_level -= 1
#                 if bracketing_level <= 0 and s in CLOSING_QUOTATION:
#                     end_of_quotation = True
#     if not all(o in NON_CONTENT_CHARS for o, *_ in output):
#         yield (out for out in output)


def is_content_sentence(symbol_stream):
    """Detect whether the symbol stream contains content symbols.

    :param symbol_stream: A stream over symbols.

    :return: ``True`` if the symbol stream contains content symbols, else
        ``False``.

    """
    return any(symbol[0] is not None and in_ranges(symbol[0], WORD_RANGES)
               for symbol in symbol_stream)


def content_sentences(symbol_streams):
    """Filter out non-content symbol streams.

    :param symbol_streams: An iterable over symbol streams.

    :return: An iterable over all symbol streams that contain content symbols.

    """
    for sentence in symbol_streams:
        sentence = tuple(sentence)
        if is_content_sentence(sentence):
            yield (symbol for symbol in sentence)


def strip(symbol_streams):
    """Remove leading and trailing whitespace from a symbol stream.

    The definition of whitespace is language-dependent and refers to Japanese
    conventions here.

    As is generally the case with symbol streams, all removed whitespace can be
    restored using :func:`.symbol_stream.expand`.

    :param symbol_stream: A stream over symbols.

    :return: A symbol stream like the input symbol stream, with whitespace
        replaced by ``None``-symbols.

    """
    for sentence in symbol_streams:
        sentence = list(sentence)
        for r in (range(len(sentence)), range(-1, -len(sentence) - 1, -1)):
            for i in r:
                if sentence[i][0] is None:
                    pass
                elif sentence[i][0] in WHITESPACE:
                    sentence[i] = (None, sentence[i])
                else:
                    break
        yield (symbol for symbol in sentence)


def segmenter(symbol_stream, whitespace_marks_end_of_paragraph=False):
    """Accept a stream of symbols and yield symbol streams for each sentence.

    This function works most reliably with balanced bracketing.

    :param symbol_stream: A stream over symbols.

    :param bool whitespace_marks_end_of_paragraph: Whether whitespace marks the
        end of a paragraph in the symbol stream.

    :return: An iterable over symbol streams, each corresponding to a sentence.

    """
    bracketing_level = 0
    end_of_quotation = False
    middle_of_numeral = False
    end_of_sentence = False
    end_of_paragraph = False
    output = []
    for symbol in symbol_stream:
        s = symbol[0]
        if (whitespace_marks_end_of_paragraph
            and bracketing_level <= 0
            and s in WHITESPACE):
            # In-sentence spaces are removed from the JEITA corpus, so we can
            # interpret whitespace outside of bracketed groups as paragraph
            # breaks and remove this whitespace from sentence ends/beginnings.
            if not end_of_paragraph and output:
                yield (out for out in output)
                output = []
            output.append(symbol)
            middle_of_numeral = False
            end_of_paragraph = True
        elif (bracketing_level <= 0
              and output and output[-1][0] in DIGIT
              and s in DIGIT_PUNCTUATION
              and not middle_of_numeral):
            output.append(symbol)
            middle_of_numeral = True
        elif bracketing_level <= 0 and s in SENTENCE_END_PUNCTUATION:
            if end_of_paragraph and output:
                yield (out for out in output)
                output = []
            output.append(symbol)
            middle_of_numeral = False
            end_of_sentence = True
            end_of_paragraph = False
        else:
            if ((end_of_paragraph
                 or end_of_sentence
                 or (middle_of_numeral
                     and output[-1][0] in SENTENCE_END_PUNCTUATION
                     and s not in DIGIT)
                 or (end_of_quotation and s in OPENING_QUOTATION))
                and output):
                yield (out for out in output)
                output = []
            output.append(symbol)
            end_of_quotation = (not whitespace_marks_end_of_paragraph
                                and s in WHITESPACE
                                and end_of_quotation)
            middle_of_numeral = False
            end_of_sentence = False
            end_of_paragraph = False
            if s in OPENING_BRACKETS:
                bracketing_level += 1
            elif s in CLOSING_BRACKETS:
                bracketing_level = max(0, bracketing_level - 1)
                if bracketing_level <= 0 and s in CLOSING_QUOTATION:
                    end_of_quotation = True
    if output:
        yield (out for out in output)


def match_reading(splits):
    """Match graphic and phonetic word representations and lemma.
    
    Discern the notations '\ ' for space and '\' for backslash (with ' ' as
    field separator) in JUMAN++ output.

    :param list[str] splits: The sections for word token (graphic), word token
        (phonetic), and lemma, split on ' ' from a joint string representation
        with ' ' as separator.  The input may contain more than three elements.

    :return: A triple consisting of the graphic word token, the phonetic word
        token, and the lemma.

    """
    # Space and backslash do not take part in morphological variations, thus all
    # three annotations contain the same number of splits
    assert len(splits) % 3 == 0
    i = len(splits) // 3
    # After discriminating word token (graphic), word token (phonetic) and
    # lemma, all sequences of '\ ' necessarily denote spaces, not backslashes
    return [re.sub('\\\\ ', ' ', ' '.join(splits[j*i:(j+1)*i]))
            for j in range(3)]


def to_dict(token):
    """Turn an array of JUMAN++-style token annotations into a dictionary.

    :param token: An array version of a line of JUMAN++ output.  It either has
        twelve elements and is the first candidate for a token, or it has
        thirteen elements and is a later candidate for a token.  In the latter
        case the first element is ``'@'``.

    :return: A dictionary describing the token candidate corresponding to the
        input.  It has the following form:

        .. code-block:: python

           {
             'surface_form': {'graphic': ..., 'phonetic': ...},
             'base_form': {'graphic': ..., 'phonetic': ...},
             'lemma': {'graphic': ..., 'phonetic': ...},
             'pos': <list of POS tags>,
             'inflection': <list of POS/inflection tags>
           }
        
        The surface form is the inflected form as it was found in the text,
        along with its reading in katakana.  The base form is the uninflected
        form.  For both graphic representation and reading, it may be different
        from the lemma for different graphic variants of the same lexeme.  The
        lemma is the canonical form for both graphic reprepresentation and
        reading, intended to be unique for all variants of a lexeme.

    """
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
        pos = ()
        # TODO Use logger instead
        print('\033[33mWARN\033[0m POS tags %r %r %r not found'
              % (pos_broad, pos_fine, inflection_type))
    inflection = pos if token[9] == '*' else pos + (token[9],)
    if '代表表記:' not in token[11]:
        # For unknown lemmas use the uninflected representations (may fail to
        # map different graphical variants to the same lexeme)
        lemma = {'graphic': uninflected_graphic,
                 'phonetic': hiragana_to_katakana(uninflected_phonetic)}
    elif token[0] == ' ':
        lemma = {'graphic': ' ', 'phonetic': ' '}
    else:
        lemma = re.search('代表表記:([^ ]*)', token[11]).group(1).split('/')
        # '/' is not subject to morphological changes, so there is always an odd
        # number of slashes in the above matched string
        lemma = {'graphic': '/'.join(lemma[:len(lemma) // 2]),
                 'phonetic': hiragana_to_katakana('/'.join(lemma[len(lemma) // 2:]))}
        # Remove "v" from lemma form of nominalized verbs and add this
        # information to the POS tag list and inflection list
        if lemma['phonetic'].endswith('v'):
            lemma['phonetic'] = lemma['phonetic'][:-1]
            pos += ('verb',)
            inflection += ('verb', '基本連用形')
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
    return {
        # Inflected form as it was found in the text, along with its reading
        'surface_form': {'graphic': surface_graphic,
                         'phonetic': hiragana_to_katakana(surface_phonetic)},
        # Uninflected (and not overly repeated (see ``repetition_fold``)) form
        # For both graphic representation and reading, may be different from the
        # lemma for different graphic variants of the same lexeme
        'base_form': {'graphic': uninflected_graphic,
                      'phonetic': hiragana_to_katakana(uninflected_phonetic)},
        # Canonical form for both graphic reprepresentation and reading,
        # intended to be unique for all variants of a lexeme
        'lemma': lemma,
        'pos': pos,
        'inflection': inflection #,
        # # XXX Use a regex that captures a note directly, without relying on
        # #     the assertion above
        # # XXX Analyze the notes' substructure
        # 'notes': ([] if token[11] == ''
        #           else [token[11]] if token[0] == ' '
        #           # XXX Not covered by the assertions: Space could occur
        #           #     within one note
        #           else token[11].split(' '))
    }


async def tokenize_async(text, partially_annotated=False):
    """Tokenize a text using JUMAN++, in an asynchronous fashion.

    While waiting for the result of tokenization is performed asynchronously,
    the token candidates are yielded in a blocking fashion, i.e. every coroutine
    building on this tokenizer has access to all resulting tokens without
    interference of other coroutines.

    :param str text: The text to tokenize.

    :param bool partially_annotated: Whether the input is partially annotated.

    :return: An iterable over tuples of candidates, each candidate being one of
        the possible tokens for its token position in the iterable.  A candidate
        is a dictionary of the form described in :func:`to_dict`.

    """
    async with SubprocessLock(0.1):
        # Call JUMAN++ Japanese morphological analyzer
        process = await asyncio.create_subprocess_exec(
            *(['jumanpp', '--partial'] if partially_annotated else ['jumanpp']),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE)
        output, error = await process.communicate(input=text.encode())
        # TODO Detect process failure
        # TODO Handle error messages
    for candidates in parse_jumanpp_output(output.decode()):
        yield candidates


def tokenizer(text, partially_annotated=False):
    """Tokenize a text using JUMAN++, in a synchronous fashion.

    :param str text: The text to tokenize.

    :param bool partially_annotated: Whether the input is partially annotated.

    :return: An iterable over tuples of candidates, each candidate being one of
        the possible tokens for its token position in the iterable.  A candidate
        is a dictionary of the form described in :func:`to_dict`.

    """
    # Call JUMAN++ Japanese morphological analyzer
    process = Popen(
        ['jumanpp', '--partial'] if partially_annotated else ['jumanpp'],
        stdin=PIPE,
        stdout=PIPE,
        stderr=PIPE)
    output, error = process.communicate(input=text.encode())
    # TODO Detect process failure
    # TODO Handle error messages
    yield from parse_jumanpp_output(output.decode())


def _empty_affix(symbols, i, partially_annotated):
    affix = ''
    if partially_annotated:
        # Tabs cannot be part of the output. Remove them
        while i < len(symbols) and (symbols[i][0] is None or symbols[i][0] == 0x0009):
            affix += to_text(expand(symbols[i][1:]))
            i += 1
    else:
        while i < len(symbols) and symbols[i][0] is None:
            affix += to_text(expand(symbols[i][1:]))
            i += 1
    return affix, i


def _expand_surface_forms(symbols, i, token_alternatives, prefix, partially_annotated):
    graphic = token_alternatives[0]['surface_form']['graphic']
    expanded_graphic = prefix
    for c in graphic:
        s, *expansion = symbols[i]
        assert s == ord(c)
        if expansion:
            expanded_graphic += to_text(expand(expansion))
        else:
            expanded_graphic += c
        suffix, i = _empty_affix(symbols, i + 1, partially_annotated)
        expanded_graphic += suffix
    for token_alternative in token_alternatives:
        token_alternative['surface_form']['graphic'] = expanded_graphic
    return '', i


# XXX In the case that no token is provided (i.e. all symbols are None or the
# text is partially annotated and all symbols are None or tab), all input is
# lost
def stream_tokenizer(symbol_stream, partially_annotated=False):
    """Tokenize a symbol stream using JUMAN++, in a synchronous fashion.

    :param symbol_stream: The symbol stream to tokenize.

    :param bool partially_annotated: Whether the input is partially annotated.

    :return: An iterable over tuples of candidates, each candidate being one of
        the possible tokens for its token position in the iterable.  A candidate
        is a dictionary of the form described in :func:`to_dict`.

    """
    symbols = tuple(symbol_stream)
    prefix, i = _empty_affix(symbols, 0, partially_annotated)
    for token_alternatives in tokenizer(to_text(symbols), partially_annotated):
        prefix, i = _expand_surface_forms(symbols, i, token_alternatives, prefix, partially_annotated)
        yield token_alternatives


# XXX In the case that no token is provided (i.e. all symbols are None or the
# text is partially annotated and all symbols are None or tab), all input is
# lost
async def tokenize_stream_async(symbol_stream, partially_annotated=False):
    """Tokenize a symbol stream using JUMAN++, in an asynchronous fashion.

    While waiting for the result of tokenization is performed asynchronously,
    the token candidates are yielded in a blocking fashion, i.e. every coroutine
    building on this tokenizer has access to all resulting tokens without
    interference of other coroutines.

    :param symbol_stream: The symbol stream to tokenize.

    :param bool partially_annotated: Whether the input is partially annotated.

    :return: An iterable over tuples of candidates, each candidate being one of
        the possible tokens for its token position in the iterable.  A candidate
        is a dictionary of the form described in :func:`to_dict`.

    """
    symbols = tuple(symbol_stream)
    prefix, i = _empty_affix(symbols, 0, partially_annotated)
    async for token_alternatives in tokenize_async(to_text(symbols), partially_annotated):
        prefix, i = _expand_surface_forms(symbols, i, token_alternatives, prefix, partially_annotated)
        yield token_alternatives


def parse_jumanpp_output(output):
    """Parse JUMAN++ tokenizer output format.
    
    The output is one-token-per-line, with space-separated annotations.  There
    are twelve annotations for regular tokens and twelve annotations and an
    additional '@ ' at the beginning of lines to mark the beginning of
    alternatives for a preceding regular token.
    
    Start processing from the end of the line, since there are ambiguities for
    the first three annotation types: Spaces are denoted as '\ ', while
    backslashes are denoted by '\' only, resulting in conflicting
    interpretations for '\ ' as "space", and "backslash" + "end of annotation",
    respectively.
    
    Furthermore, '"' is not escaped or enclosed in single quotation
    marks, while the last annotation, if existent, is always enclosed
    in double quotation marks.  Thus, manual line splitting is
    necessary, and cannot be done via shlex.
    
    The remaining annotation types are a fixed set of keywords, with odd and
    even annotations encoding the same information, once in string form and
    once as a numerical ID.

    :param str output: The raw output of JUMAN++.

    :return: An iterable over tuples of candidates, each candidate being one of
        the possible tokens for its token position in the iterable.  A candidate
        is a dictionary of the form described in :func:`to_dict`.

    """
    output = tuple(line for line in output.split('\n')
                   if line != 'EOS' and line != '')
    assert all(line.endswith(' NIL')
               or re.match('^"[^"]*" ', line[::-1]) is not None
               for line in output), output
    output = tuple(re.fullmatch('^(.*) ("[^"]*"|NIL)$', line).groups()
                   for line in output)
    # XXX Use a string loader like json.loads for ``notes``, depending on
    # whether characters in ``notes`` are escaped or not
    output = tuple((rest.split(' '), ('' if notes == 'NIL' else notes[1:-1]))
                   for rest, notes in output)
    assert all(len(rest) >= 11 for rest, _ in output)
    # XXX Use tuples instead of lists
    output = tuple(((['@'] + match_reading(rest[1:-8]))
                    if (rest[0] == '@'
                        # '@' itself has only one morphological variant
                        and (rest[-9] != '@' or len(rest[:-8]) > 3))
                    else match_reading(rest[:-8]))
                   + rest[-8:] + [notes]
                   for rest, notes in output)
    # If passing all asserts up to this point in this function and in
    # ``match_reading``, ``output`` is now an array version of the output format
    # of JUMAN++, so as to fulfill the following condition:
    # 
    #     ``assert all(len(line) == 12 or
    #                  (line[0] == '@' and len(line) == 13)
    #                  for line in output)``
    candidates = None
    for line in output:
        if len(line) <= 12:
            if candidates is not None:
                yield tuple(candidates)
            candidates = [to_dict(line)]
        else:
            assert candidates is not None
            candidates.append(to_dict(line[1:]))
    if candidates is not None:
        yield tuple(candidates)


def chasen_loader(filename):
    """Loads a file from the JEITA corpus and yields symbols from it.

    :param str filename: The filename of the document to load.

    :return: A symbol stream that encodes the text from the loaded document.

    """
    reader = ChasenCorpusReader(os.path.abspath(os.path.dirname(
        os.path.abspath(__file__)) + '/../../data/raw/yokome-jpn-corpus'),
                                filename, encoding='utf-8')
    for word in reader.words():
        for c in word:
            yield (ord(c),)


def fullwidth_fold(symbol_stream):
    """Turn the ASCII space, the Latin letters in ASCII, and the halfwidth forms
    into their fullwidth counterparts.

    :param symbol_stream: A stream over symbols.

    :return: A symbol stream like the input symbol stream, with halfwidth
        characters replaced by their fullwidth counterparts.

    """
    for symbol in symbol_stream:
        s = symbol[0]
        if s in _FULLWIDTH_FOLD_DICT:
            yield (_FULLWIDTH_FOLD_DICT[s], symbol)
        else:
            yield symbol


def combining_voice_mark_fold(symbol_stream):
    """Normalize words with combining voice marks.

    :param symbol_stream: A stream over symbols.

    :return: A symbol stream like the input symbol stream, with combining
        voice/semi-voice marks combined with their preceding
        voicable/semi-voicable symbols to form voiced/semi-voiced symbols.
        Voice/semi-voice marks that do not follow a voicable/semi-voicable
        symbol are replaced by KATAKANA-HIRAGANA VOICED SOUND MARK (U+309B) /
        KATAKANA-HIRAGANA SEMI-VOICED SOUND MARK (U+309c).

    """
    last_symbol = None
    for symbol in symbol_stream:
        s = symbol[0]
        if s == COMBINING_KANA_VOICED_SOUND_MARK:
            if last_symbol is None:
                yield (KANA_VOICED_SOUND_MARK, symbol)
            elif last_symbol[0] in VOICABLE:
                yield (voice(last_symbol[0]), last_symbol, symbol)
            else:
                yield last_symbol
                yield (KANA_VOICED_SOUND_MARK, symbol)
            last_symbol = None
        elif s == COMBINING_KANA_SEMI_VOICED_SOUND_MARK:
            if last_symbol is None:
                yield (KANA_SEMI_VOICED_SOUND_MARK, symbol)
            elif last_symbol[0] in SEMI_VOICABLE:
                yield (semivoice(last_symbol[0]), last_symbol, symbol)
            else:
                yield last_symbol
                yield (KANA_SEMI_VOICED_SOUND_MARK, symbol)
            last_symbol = None
        else:
            if last_symbol is not None:
                yield last_symbol
            last_symbol = symbol
    if last_symbol is not None:
        yield last_symbol
