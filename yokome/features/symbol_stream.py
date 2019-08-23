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


import re
from copy import deepcopy
from numpy.random import RandomState
from typing import Iterator


# XXX Greek: 0x018d, 0x0194, 0x0196, 0x019b, 0x019f, 0x01a9, 0x01aa, 0x01b1, 0x0245
# XXX Other symbols: 0x0184 - 0x0185, 0x01a7 - 0x01a8, 0x01bb, 0x01bc - 0x01bd, 0x01be, 0x0241 - 0x0242
# XXX Bitcoin: 0x0243


# _ASCII_FOLD_BIG_A_RANGES = ((0x00c0, 0x00c5),)
# _ASCII_FOLD_BIG_E_RANGES = ((0x00c8, 0x00cb),)
# _ASCII_FOLD_BIG_I_RANGES = ((0x00cc, 0x00cf),)
# _ASCII_FOLD_BIG_O_RANGES = ((0x00d2, 0x00d6),
#                             (0x00d8, 0x00d8),
#                             (0x0186, 0x0186))
# _ASCII_FOLD_BIG_U_RANGES = ((0x00d9, 0x00dc),)
# _ASCII_FOLD_SMALL_A_RANGES = ((0x00e0, 0x00e5),)
# _ASCII_FOLD_SMALL_E_RANGES = ((0x00e8, 0x00eb), (0x01dd, 0x01dd))
# _ASCII_FOLD_SMALL_I_RANGES = ((0x00ec, 0x00ef),)
# _ASCII_FOLD_SMALL_O_RANGES = ((0x00f2, 0x00f6), (0x00f8, 0x00f8))
# _ASCII_FOLD_SMALL_U_RANGES = ((0x00f9, 0x00fc),)
# _ASCII_FOLD_EXTENDED_A_RANGES = ((0x0100, 0x0105),
#                                  (0x01cd, 0x01ce),
#                                  (0x01de, 0x01e1),
#                                  (0x01fa, 0x01fb),
#                                  (0x0200, 0x0203),
#                                  (0x0226, 0x0227),
#                                  (0x023a, 0x023a))
# _ASCII_FOLD_EXTENDED_B_RANGES = ((0x0182, 0x0183),)
# _ASCII_FOLD_EXTENDED_C_RANGES = ((0x0106, 0x010d),
#                                  (0x0187, 0x0188),
#                                  (0x023b, 0x023c))
# _ASCII_FOLD_EXTENDED_D_RANGES = ((0x010e, 0x0111), (0x018b, 0x018c))
# _ASCII_FOLD_EXTENDED_E_RANGES = ((0x0112, 0x011b),
#                                  (0x018e, 0x0190),
#                                  (0x0204, 0x0207),
#                                  (0x0228, 0x0229),
#                                  (0x0246, 0x0247))
# _ASCII_FOLD_EXTENDED_F_RANGES = ((0x0191, 0x0192),)
# _ASCII_FOLD_EXTENDED_G_RANGES = ((0x011c, 0x0123),
#                                  (0x0193, 0x0193),
#                                  (0x01e4, 0x01e7),
#                                  (0x01f4, 0x01f5))
# _ASCII_FOLD_EXTENDED_H_RANGES = ((0x0124, 0x0127), (0x021e, 0x021f))
# _ASCII_FOLD_EXTENDED_I_RANGES = ((0x0128, 0x0131),
#                                  (0x0197, 0x0197),
#                                  (0x01cf, 0x01d0),
#                                  (0x0208, 0x020b))
# _ASCII_FOLD_EXTENDED_J_RANGES = ((0x0134, 0x0135), (0x0248, 0x0249))
# _ASCII_FOLD_EXTENDED_K_RANGES = ((0x0198, 0x0199), (0x01e8, 0x01e9))
# _ASCII_FOLD_EXTENDED_L_RANGES = ((0x0139, 0x0142), (0x023d, 0x023d))
# _ASCII_FOLD_EXTENDED_N_RANGES = ((0x0143, 0x0148),
#                                  (0x014a, 0x014b),
#                                  (0x019d, 0x019e),
#                                  (0x01f8, 0x01f9),
#                                  (0x0220, 0x0220))
# _ASCII_FOLD_EXTENDED_O_RANGES = ((0x014c, 0x0151),
#                                  (0x01a0, 0x01a1),
#                                  (0x01d1, 0x01d2),
#                                  (0x01ea, 0x01ed),
#                                  (0x01fe, 0x01ff),
#                                  (0x020c, 0x020f),
#                                  (0x022a, 0x0231))
# _ASCII_FOLD_EXTENDED_P_RANGES = ((0x01a4, 0x01a5),)
# _ASCII_FOLD_EXTENDED_Q_RANGES = ((0x024a, 0x024b),)
# _ASCII_FOLD_EXTENDED_R_RANGES = ((0x0154, 0x0159),
#                                  (0x0210, 0x0213),
#                                  (0x024c, 0x024d))
# _ASCII_FOLD_EXTENDED_S_RANGES = ((0x015a, 0x0161), (0x0218, 0x0219))
# _ASCII_FOLD_EXTENDED_T_RANGES = ((0x0162, 0x0167),
#                                  (0x01ac, 0x01ae),
#                                  (0x021a, 0x021b),
#                                  (0x023e, 0x023e))
# _ASCII_FOLD_EXTENDED_U_RANGES = ((0x0168, 0x0173),
#                                  (0x01af, 0x01b0),
#                                  (0x01d3, 0x01dc),
#                                  (0x0214, 0x0217),
#                                  (0x0244, 0x0244))
# _ASCII_FOLD_EXTENDED_Y_RANGES = ((0x0176, 0x0178),
#                                  (0x01b3, 0x01b4),
#                                  (0x021c, 0x021d),
#                                  (0x0232, 0x0233),
#                                  (0x024e, 0x024f))
# _ASCII_FOLD_EXTENDED_Z_RANGES = ((0x0179, 0x017e),
#                                  (0x01b5, 0x01b6),
#                                  (0x01b7, 0x01b7),
#                                  (0x01b8, 0x01b9),
#                                  (0x01ee, 0x01ef),
#                                  (0x0224, 0x0225))
# _ASCII_FOLD_EXTENDED_AE_RANGES = ((0x00c6, 0x00c6),
#                                   (0x01e2, 0x01e3),
#                                   (0x01fc, 0x01fd))

ASCII_LETTER_RANGES = ((0x0041, 0x005a), (0x0061, 0x007a))


def to_symbol_stream(text):
    for c in text:
        yield (ord(c),)


def to_text(symbol_stream):
    return ''.join(chr(s) for s, *_ in symbol_stream if s is not None)


def expand(symbol_stream):
    for symbol in symbol_stream:
        s, *expansion = symbol
        if expansion:
            for out in expand(expansion):
                yield out
        elif s is not None:
            yield symbol


def in_ranges(char, ranges):
    """Determines whether the given character is in one of the ranges."""
    return any(start <= char and char <= stop for start, stop in ranges)


class BracketingError(Exception):
    """

    ``bracketing_structure`` is a symbol stream.

    """
    def __init__(self, bracketing_structure, *args, **kwargs):
        self.value = tuple(bracketing_structure)
        super().__init__(*args, **kwargs)


def validate_brackets(symbol_stream, brackets) -> Iterator:
    """Validate the stream's bracketing structure.

    Yield the symbols from the symbol stream verbatim while checking for
    unbalanced and mismatched brackets.  Raise ``BracketingError`` after
    yielding every symbol in an invalid input.

    :param symbol_stream: A stream over symbols.
    :param brackets: A dictionary where the keys are the chars for the opening
        brackets and their values are the corresponding closing brackets.

    :return: A stream over the same symbols as the input.

    :raises BracketingError: If brackets in the symbol stream are unbalanced or
        mismatched

    """
    opening_brackets = set(brackets.keys())
    closing_brackets = set(brackets.values())
    bracket_stack = []
    bracketing_structure = []
    mismatched_brackets = False
    unbalanced_brackets = False
    for symbol in symbol_stream:
        s = symbol[0]
        if s in opening_brackets:
            bracket_stack.append(s)
            bracketing_structure.append(deepcopy(symbol))
        elif s in closing_brackets:
            if not bracket_stack:
                unbalanced_brackets = True
            elif brackets[bracket_stack.pop()] != s:
                mismatched_brackets = True
            bracketing_structure.append(deepcopy(symbol))
        yield symbol
    # Run through the whole symbol stram to be able to yield all symbols and to
    # report the complete bracketing structure
    if unbalanced_brackets or bracket_stack:
        raise BracketingError(bracketing_structure, 'Unbalanced brackets')
    # Report mismatched brackets only when unbalanced brackets have not been
    # reported, as missing opening brackets can lead to the detection of
    # mismatches in an otherwise valid structure
    if mismatched_brackets:
        raise BracketingError(bracketing_structure, 'Mismatched brackets')
    return tuple(bracketing_structure)


# # TODO Only Latin-1 supplement, Latin extended-A and Latin extended-b
# def ascii_fold(symbol_stream):
#     UPPERCASE = 2
#     LOWERCASE = 1
#     alternating_range_result = False
#     def in_alternating_ranges(char, ranges):
#         nonlocal alternating_range_result
#         for start, end in ranges:
#             if start <= char and char <= end:
#                 alternating_range_result = (UPPERCASE if start % 2 == char % 2
#                                             else LOWERCASE)
#                 return alternating_range_result
#         alternating_range_result = False
#         return alternating_range_result
#     for symbol in symbol_stream:
#         s = symbol[0]
#         if s is None:
#             yield symbol
#         elif in_ranges(s, _ASCII_FOLD_BIG_A_RANGES):
#             yield (0x0041, symbol)
#         elif in_ranges(s, _ASCII_FOLD_SMALL_A_RANGES):
#             yield (0x0061, symbol)
#         elif in_ranges(s, _ASCII_FOLD_BIG_E_RANGES):
#             yield (0x0045, symbol)
#         elif in_ranges(s, _ASCII_FOLD_SMALL_E_RANGES):
#             yield (0x0065, symbol)
#         elif in_ranges(s, _ASCII_FOLD_BIG_I_RANGES):
#             yield (0x0049, symbol)
#         elif in_ranges(s, _ASCII_FOLD_SMALL_I_RANGES):
#             yield (0x0069, symbol)
#         elif in_ranges(s, _ASCII_FOLD_BIG_O_RANGES):
#             yield (0x004f, symbol)
#         elif in_ranges(s, _ASCII_FOLD_SMALL_O_RANGES):
#             yield (0x006f, symbol)
#         elif in_ranges(s, _ASCII_FOLD_BIG_U_RANGES):
#             yield (0x0055, symbol)
#         elif in_ranges(s, _ASCII_FOLD_SMALL_U_RANGES):
#             yield (0x0075, symbol)
#         elif in_alternating_ranges(s, _ASCII_FOLD_EXTENDED_A_RANGES):
#             yield ((0x0041, symbol) if alternating_range_result == UPPERCASE
#                    else (0x0061, symbol))
#         elif in_alternating_ranges(s, _ASCII_FOLD_EXTENDED_B_RANGES):
#             yield ((0x0042, symbol) if alternating_range_result == UPPERCASE
#                    else (0x0062, symbol))
#         elif in_alternating_ranges(s, _ASCII_FOLD_EXTENDED_C_RANGES):
#             yield ((0x0043, symbol) if alternating_range_result == UPPERCASE
#                    else (0x0063, symbol))
#         elif in_alternating_ranges(s, _ASCII_FOLD_EXTENDED_D_RANGES):
#             yield ((0x0044, symbol) if alternating_range_result == UPPERCASE
#                    else (0x0064, symbol))
#         elif in_alternating_ranges(s, _ASCII_FOLD_EXTENDED_E_RANGES):
#             yield ((0x0045, symbol) if alternating_range_result == UPPERCASE
#                    else (0x0065, symbol))
#         elif in_alternating_ranges(s, _ASCII_FOLD_EXTENDED_F_RANGES):
#             yield ((0x0046, symbol) if alternating_range_result == UPPERCASE
#                    else (0x0066, symbol))
#         elif in_alternating_ranges(s, _ASCII_FOLD_EXTENDED_G_RANGES):
#             yield ((0x0047, symbol) if alternating_range_result == UPPERCASE
#                    else (0x0067, symbol))
#         elif in_alternating_ranges(s, _ASCII_FOLD_EXTENDED_H_RANGES):
#             yield ((0x0048, symbol) if alternating_range_result == UPPERCASE
#                    else (0x0068, symbol))
#         elif in_alternating_ranges(s, _ASCII_FOLD_EXTENDED_I_RANGES):
#             yield ((0x0049, symbol) if alternating_range_result == UPPERCASE
#                    else (0x0069, symbol))
#         elif in_alternating_ranges(s, _ASCII_FOLD_EXTENDED_J_RANGES):
#             yield ((0x004a, symbol) if alternating_range_result == UPPERCASE
#                    else (0x006a, symbol))
#         elif in_alternating_ranges(s, _ASCII_FOLD_EXTENDED_K_RANGES):
#             yield ((0x004b, symbol) if alternating_range_result == UPPERCASE
#                    else (0x006b, symbol))
#         elif in_alternating_ranges(s, _ASCII_FOLD_EXTENDED_L_RANGES):
#             yield ((0x004c, symbol) if alternating_range_result == UPPERCASE
#                    else (0x006c, symbol))
#         elif in_alternating_ranges(s, _ASCII_FOLD_EXTENDED_N_RANGES):
#             yield ((0x004e, symbol) if alternating_range_result == UPPERCASE
#                    else (0x006e, symbol))
#         elif in_alternating_ranges(s, _ASCII_FOLD_EXTENDED_O_RANGES):
#             yield ((0x004f, symbol) if alternating_range_result == UPPERCASE
#                    else (0x006f, symbol))
#         elif in_alternating_ranges(s, _ASCII_FOLD_EXTENDED_P_RANGES):
#             yield ((0x0050, symbol) if alternating_range_result == UPPERCASE
#                    else (0x0070, symbol))
#         elif in_alternating_ranges(s, _ASCII_FOLD_EXTENDED_Q_RANGES):
#             yield ((0x0051, symbol) if alternating_range_result == UPPERCASE
#                    else (0x0071, symbol))
#         elif in_alternating_ranges(s, _ASCII_FOLD_EXTENDED_R_RANGES):
#             yield ((0x0052, symbol) if alternating_range_result == UPPERCASE
#                    else (0x0072, symbol))
#         elif in_alternating_ranges(s, _ASCII_FOLD_EXTENDED_S_RANGES):
#             yield ((0x0053, symbol) if alternating_range_result == UPPERCASE
#                    else (0x0073, symbol))
#         elif in_alternating_ranges(s, _ASCII_FOLD_EXTENDED_T_RANGES):
#             yield ((0x0054, symbol) if alternating_range_result == UPPERCASE
#                    else (0x0074, symbol))
#         elif in_alternating_ranges(s, _ASCII_FOLD_EXTENDED_U_RANGES):
#             yield ((0x0055, symbol) if alternating_range_result == UPPERCASE
#                    else (0x0075, symbol))
#         elif in_alternating_ranges(s, _ASCII_FOLD_EXTENDED_Y_RANGES):
#             yield ((0x0059, symbol) if alternating_range_result == UPPERCASE
#                    else (0x0079, symbol))
#         elif in_alternating_ranges(s, _ASCII_FOLD_EXTENDED_Z_RANGES):
#             yield ((0x005a, symbol) if alternating_range_result == UPPERCASE
#                    else (0x007a, symbol))
#         elif in_alternating_ranges(s, _ASCII_FOLD_EXTENDED_AE_RANGES):
#             if alternating_range_result == UPPERCASE: # -> 'AE'
#                 yield (0x0041, symbol)
#                 yield (0x0045, (None,))
#             else:                       # -> 'ae'
#                 yield (0x0061, symbol)
#                 yield (0x0065, (None,))
#         elif s == 0x0181:               # 'Ɓ' -> 'B'
#             yield (0x0042, symbol)
#         elif s == 0x0180:               # 'ƀ' -> 'b'
#             yield (0x0062, symbol)
#         elif s == 0x00c7:               # 'Ç' -> 'C'
#             yield (0x0043, symbol)
#         elif s == 0x00e7:               # 'ç' -> 'c'
#             yield (0x0063, symbol)
#         elif s == 0x00d0 or s == 0x0189 or s == 0x018a: # -> 'D'
#             yield (0x0044, symbol)
#         elif s == 0x00f0 or s == 0x0221: # -> 'd'
#             yield (0x0064, symbol)
#         elif s == 0x01f0 or s == 0x0237: # -> 'j'
#             yield (0x006a, symbol)
#         elif s == 0x0136:               # 'Ķ' -> 'K'
#             yield (0x004b, symbol)
#         elif s == 0x0137:               # 'ķ' -> 'k'
#             yield (0x006b, symbol)
#         elif s == 0x019a or s == 0x0234: # -> 'l'
#             yield (0x006c, symbol)
#         elif s == 0x019c:               # 'Ɯ' -> 'M'
#             yield (0x004d, symbol)
#         elif s == 0x00d1:               # 'Ñ' -> 'N'
#             yield (0x004e, symbol)
#         elif s == 0x00f1 or s == 0x0149 or s == 0x0235: # -> 'n'
#             yield (0x006e, symbol)
#         elif s == 0x0138:               # 'ĸ' -> 'q'
#             yield (0x0071, symbol)
#         elif s == 0x017f or s == 0x023f: # -> 's'
#             yield (0x0073, symbol)
#         elif s == 0x01ab or s == 0x0236: # -> 't'
#             yield (0x0074, symbol)
#         elif s == 0x01b2:               # 'Ʋ' -> 'V'
#             yield (0x0056, symbol)
#         elif s == 0x0174 or s == 0x01f7: #  -> 'W'
#             yield (0x0057, symbol)
#         elif s == 0x0175 or s == 0x01bf: # -> 'w'
#             yield (0x0077, symbol)
#         elif s == 0x00dd:               # 'Ý' -> 'Y'
#             yield (0x0059, symbol)
#         elif s == 0x00fd or s == 0x00ff: # -> 'y'
#             yield (0x0079, symbol)
#         elif s == 0x01ba or s == 0x0240: # -> 'z'
#             yield (0x007a, symbol)
#         elif s == 0x00e6:               # 'æ' -> 'ae'
#             yield (0x0061, symbol)
#             yield (0x0065, (None,))
#         elif s == 0x0238:               # 'ȸ' -> 'db'
#             yield (0x0064, symbol)
#             yield (0x0062, (None,))
#         elif s == 0x01c4 or s == 0x01f1: # -> 'DZ'
#             yield (0x0044, symbol)
#             yield (0x005a, (None,))
#         elif s == 0x01c5 or s == 0x01f2: # -> 'Dz'
#             yield (0x0044, symbol)
#             yield (0x007a, (None,))
#         elif s == 0x01c6 or s == 0x01f3: # -> 'dz'
#             yield (0x0064, symbol)
#             yield (0x007a, (None,))
#         elif s == 0x01f6:               # 'Ƕ' -> 'Hv'
#             yield (0x0048, symbol)
#             yield (0x0076, (None,))
#         elif s == 0x0195:               # 'ƕ' -> 'hv'
#             yield (0x0068, symbol)
#             yield (0x0076, (None,))
#         elif s == 0x0132:               # 'Ĳ' -> 'IJ'
#             yield (0x0049, symbol)
#             yield (0x004a, (None,))
#         elif s == 0x0133:               # 'ĳ' -> 'ij'
#             yield (0x0069, symbol)
#             yield (0x006a, (None,))
#         elif s == 0x01c7:               # 'Ǉ' -> 'LJ'
#             yield (0x004c, symbol)
#             yield (0x004a, (None,))
#         elif s == 0x01c8:               # 'ǈ' -> 'Lj'
#             yield (0x004c, symbol)
#             yield (0x006a, (None,))
#         elif s == 0x01c9:               # 'ǉ' -> 'lj'
#             yield (0x006c, symbol)
#             yield (0x006a, (None,))
#         elif s == 0x01ca:               # 'Ǌ' -> 'NJ'
#             yield (0x004e, symbol)
#             yield (0x004a, (None,))
#         elif s == 0x01cb:               # 'ǋ' -> 'Nj'
#             yield (0x004e, symbol)
#             yield (0x006a, (None,))
#         elif s == 0x01cc:               # 'ǌ' -> 'nj'
#             yield (0x006e, symbol)
#             yield (0x006a, (None,))
#         elif s == 0x0152:               # 'Œ' -> 'OE'
#             yield (0x004f, symbol)
#             yield (0x0045, (None,))
#         elif s == 0x0153:               # 'œ' -> 'oe'
#             yield (0x006f, symbol)
#             yield (0x0065, (None,))
#         elif s == 0x01a2:               # 'Ƣ' -> 'OI'
#             yield (0x004f, symbol)
#             yield (0x0049, (None,))
#         elif s == 0x01a3:               # 'ƣ' -> 'oi'
#             yield (0x006f, symbol)
#             yield (0x0069, (None,))
#         elif s == 0x0222:               # 'Ȣ' -> 'OU'
#             yield (0x004f, symbol)
#             yield (0x0055, (None,))
#         elif s == 0x0223:               # 'ȣ' -> 'ou'
#             yield (0x006f, symbol)
#             yield (0x0075, (None,))
#         elif s == 0x0239:               # 'ȹ' -> 'qp'
#             yield (0x0071, symbol)
#             yield (0x0070, (None,))
#         elif s == 0x00df:               # 'ß' -> 'ss'
#             yield (0x0073, symbol)
#             yield (0x0073, (None,))
#         elif s == 0x00de:               # 'Þ' -> 'Th'
#             yield (0x0054, symbol)
#             yield (0x0068, (None,))
#         elif s == 0x00fe:               # 'þ' -> 'Th'
#             yield (0x0074, symbol)
#             yield (0x0068, (None,))
#         elif s == 0x01a6:               # 'Ʀ' -> 'YR'
#             yield (0x0059, symbol)
#             yield (0x0052, (None,))
#         else:
#             yield symbol


# XXX Add folding for combining diacritics, combining half marks

def _ascii_fold_sources():
    # Latin-1 supplement
    yield from range(0x00c0, 0x00d6 + 1)
    yield from range(0x00d8, 0x00f6 + 1)
    yield from range(0x00f8, 0x00ff + 1)
    # Latin extended-A
    yield from range(0x0100, 0x017f + 1)
    # Latin extended-B
    yield from range(0x0180, 0x0183 + 1)
    yield from range(0x0186, 0x018c + 1)
    yield from range(0x018e, 0x0193 + 1)
    yield 0x0195
    yield from range(0x0197, 0x019a + 1)
    yield from range(0x019c, 0x019e + 1)
    yield from range(0x01a0, 0x01a6 + 1)
    yield from range(0x01ab, 0x01b0 + 1)
    yield from range(0x01b2, 0x01ba + 1)
    yield 0x01bf
    yield from range(0x01c4, 0x0240 + 1)
    yield 0x0244
    yield from range(0x0246, 0x024f + 1)
    # XXX Add IPA extensions
    # Latin extended additional
    yield from range(0x1e00, 0x1e9e + 1)
    yield from range(0x1ea0, 0x1eff + 1)
    # XXX Add phonetic extensions
    # XXX Add greek extended
    # XXX Add superscripts and subscripts
    # Latin extended-C
    yield from range(0x2c60, 0x2c6c + 1)
    yield from range(0x2c6e, 0x2c6f + 1)
    yield from range(0x2c71, 0x2c76 + 1)
    yield from range(0x2c78, 0x2c7f + 1)
    # XXX Add latin extended-C, latin extended-D, alphabetic presentation forms
    # and mathematical alphanumeric symbols

_ASCII_FOLD_TRANSLATIONS = (
    # Latin-1 supplement
    'A  A  A  A  A  A  AE C  E  E  E  E  I  I  I  I  '
    'D  N  O  O  O  O  O     O  U  U  U  U  Y  Th ss '
    'a  a  a  a  a  a  ae c  e  e  e  e  i  i  i  i  '
    'd  n  o  o  o  o  o     o  u  u  u  u  y  th y  '
    # Latin extended-A
    'A  a  A  a  A  a  C  c  C  c  C  c  C  c  D  d  '
    'D  d  E  e  E  e  E  e  E  e  E  e  G  g  G  g  '
    'G  g  G  g  H  h  H  h  I  i  I  i  I  i  I  i  '
    'I  i  IJ ij J  j  K  k  q  L  l  L  l  L  l  L  '
    'l  L  l  N  n  N  n  N  n  n  Ng ng O  o  O  o  '
    'O  o  OE oe R  r  R  r  R  r  S  s  S  s  S  s  '
    'S  s  T  t  T  t  T  t  U  u  U  u  U  u  U  u  '
    'U  u  U  u  W  w  Y  y  Y  Z  z  Z  z  Z  z  s  '
    # Latin extended-B
    'b  B  B  b        O  C  c  D  D  D  d     E  e  '
    'E  F  f  G     hv    I  K  k  l     M  N  n     '
    'O  o  OI oi P  p  YR             t  T  t  T  U  '
    'u     V  Y  y  Z  z  Z  Z  z  z              w  '
    '            DZ Dz dz LJ Lj lj NJ Nj nj A  a  I  '
    'i  O  o  U  u  U  u  U  u  U  u  U  u  e  A  a  '
    'A  a  AE ae G  g  G  g  K  k  O  o  O  o  Z  z  '
    'j  DZ Dz dz G  g  Hv W  N  n  A  a  AE ae O  o  '
    'A  a  A  a  E  e  E  e  I  i  I  i  O  o  O  o  '
    'R  r  R  r  U  u  U  u  S  s  T  t  Y  y  H  h  '
    'N  d  OU ou Z  z  A  a  E  e  O  o  O  o  O  o  '
    'O  o  Y  y  l  n  t  j  db qp A  C  c  L  T  s  '
    'z           U     E  e  J  j  Q  q  R  r  Y  y  '
    # Latin extended additional
    'A  a  B  b  B  b  B  b  C  c  D  d  D  d  D  d  '
    'D  d  D  d  E  e  E  e  E  e  E  e  E  e  F  f  '
    'G  g  H  h  H  h  H  h  H  h  H  h  I  i  I  i  '
    'K  k  K  k  K  k  L  l  L  l  L  l  L  l  M  m  '
    'M  m  M  m  N  n  N  n  N  n  N  n  O  o  O  o  '
    'O  o  O  o  P  p  P  p  R  r  R  r  R  r  R  r  '
    'S  s  S  s  S  s  S  s  S  s  T  t  T  t  T  t  '
    'T  t  U  u  U  u  U  u  U  u  U  u  V  v  V  v  '
    'W  w  W  w  W  w  W  w  W  w  X  x  X  x  Y  y  '
    'Z  z  Z  z  Z  z  h  t  w  y  a  s  s  s  SS    '
    'A  a  A  a  A  a  A  a  A  a  A  a  A  a  A  a  '
    'A  a  A  a  A  a  A  a  E  e  E  e  E  e  E  e  '
    'E  e  E  e  E  e  E  e  I  i  I  i  O  o  O  o  '
    'O  o  O  o  O  o  O  o  O  o  O  o  O  o  O  o  '
    'O  o  O  o  U  u  U  u  U  u  U  u  U  u  U  u  '
    'U  u  Y  y  Y  y  Y  y  Y  y  Ll ll V  v  Y  y  '
    # Latin extended-C
    'L  l  L  P  R  a  t  H  h  K  k  Z  z     M  A  '
    '   v  W  w  v  H  h     e  r  o  E  j  V  S  Z  ')

_ASCII_FOLD_TRANSLATOR = {key: value for key, value
                          in zip(_ascii_fold_sources(),
                                 (tuple(ord(e) for e in translation)
                                  for translation
                                  in re.split(
                                      ' +', _ASCII_FOLD_TRANSLATIONS.strip())))}

def ascii_fold(symbol_stream):
    for symbol in symbol_stream:
        s = symbol[0]
        if s in _ASCII_FOLD_TRANSLATOR:
            yield (_ASCII_FOLD_TRANSLATOR[s][0], symbol)
            for o in _ASCII_FOLD_TRANSLATOR[s][1:]:
                yield (o, (None,))
        else:
            yield symbol

def ascii_case_fold(symbol_stream):
    for symbol in symbol_stream:
        s = symbol[0]
        yield (s + 0x0020, symbol) if s is not None and 0x0041 <= s and s <= 0x005a else symbol


def _enumerate_alternatives(tokens, previous_tokens=[]):
    if len(tokens) > 0:
        token, *tokens = tokens
        for candidate in token:
            yield from _enumerate_alternatives(tokens,
                                               previous_tokens + [candidate])
    else:
        yield (token for token in previous_tokens)


def enumerate_alternatives(sentence) -> Iterator:
    """Generate all sentence alternatives in sequence.

    :param sentence: A sentence, split into tokens.
    :return: An iterable over iterables over tokens, one for each token in the
        original sentence.
    
    """
    yield from _enumerate_alternatives(list(sentence))


def sample_alternatives(sentence, n, seed) -> Iterator:
    """From all sentence alternatives, sample ``n`` instances uniformly.

    :param sentence: A sentence, split into tokens.
    :param n: The number of sample to generate.
    :param seed: Random seed used for the random number generator.  For
        non-seeded behavior, use ``None``.

     :return: An iterable over iterables over tokens, one for each token in the
         original sentence.

    """
    sentence = list(sentence)
    r = RandomState(seed)
    for _ in range(n):
        yield [candidates[r.randint(len(candidates))]
               for candidates in sentence]
