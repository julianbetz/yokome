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
import sqlite3 as sql

from .jpn import hiragana_to_katakana
from .tree import TemplateTree


GLOSS_SEPARATOR = '▪'
"""A character that separates different glosses for the same sense.

Asserted not to occur in the text of any gloss.

"""


def circled_number(number, bold_circle=True):
    """Provide a Unicode representation of the specified number.

    :param int number: The positive number to convert to a string.

    :param bool bold_circle: If ``True``, return a white number on a black
        circle; return a black number on a white circle otherwise.

    :return: A string that is the specified number enclosed in a circle.  For
        integers that have no such representation in Unicode, return the number
        enclosed in parentheses.

    """
    if number <= 0:
        raise ValueError()
    elif number < 10:
        return chr((0x2775 if bold_circle else 0x245f) + number)
    elif number < 21 and not bold_circle:
        return chr(0x245f + number)
    elif number == 10 and bold_circle:
        return chr(0x277f)
    elif number < 21 and bold_circle:
        return chr(0x24e0 + number)
    elif bold_circle:
        return '[%s]' % (number,) # raise ValueError()
    elif number < 30:
        return chr(0x323c + number)
    elif number == 30:
        return chr(0x325a)
    elif number < 36:
        return chr(0x323c + number)
    elif number < 51:
        return chr(0x328d + number)
    else:
        return '(%s)' % (number,) # raise ValueError()


class Lexeme():
    """A lexeme (i.e. an entry) in the dictionary.

    An entry in this context means a base meaning that may be denoted by either
    element of a set of highly similar pairs of graphic and phonetic variants.
    The base meaning may be further refined to one of several connotations of
    this lexeme, see :class:`Sense`.

    The same lexeme may appear in different grammatical positions, and different
    connotations of the same lexeme might be restricted to multiple, different
    grammatical usages, see :class:`Role`.

    Furthermore, there might be restrictions as to which graphic and phonetic
    variants may appear together, as well as which of those variants may appear
    with which connotations.

    On construction, all relevant data is loaded from the database.

    :param conn: The database connection for the dictionary.

    :param str language_code: ISO 639-3 language code of the language of
        interest.

    :param int entry_id: The ID of the dictionary entry.

    :param dict restrictions: A dictionary describing the restrictions imposed
        on the possible structural ways in which the POS tags may interrelate.
        Necessary in order to provide POS tag trees.

    """

    def __init__(self, conn, language_code, entry_id, restrictions):
        c = conn.cursor()
        self.language_code = language_code
        self.entry_id = entry_id
        self.headwords = tuple(c.execute('SELECT nonkana, reading FROM lexemes WHERE language = ? AND entry_id = ? ORDER BY sequence_id', (self.language_code, self.entry_id)))
        if not self.headwords:
            raise ValueError('Unable to find entry with ID %d for language %r' % (self.entry_id, self.language_code))
        # TODO Ensure that there is a suitable index for this query
        same_main_headword_entries = tuple(other_entry_id for (other_entry_id,) in c.execute('SELECT entry_id FROM lexemes WHERE language = ? AND nonkana IS ? AND reading = ? AND sequence_id = 1 ORDER BY entry_id' if self.headwords[0][0] is None else 'SELECT entry_id FROM lexemes WHERE language = ? AND nonkana = ? AND reading = ? AND sequence_id = 1 ORDER BY entry_id', (self.language_code, *self.headwords[0])))
        self.discriminator = next(j for j, other_entry_id in enumerate(same_main_headword_entries, start=1) if other_entry_id == self.entry_id) if len(same_main_headword_entries) > 1 else None
        self.roles = []
        current_pos_list_id = None
        sense_ids = []
        for (pos_list_id, sense_id) in tuple(c.execute('SELECT pos_list_id, sense_id FROM roles WHERE language = ? AND entry_id = ? ORDER BY sense_id', (self.language_code, self.entry_id,))):
            if (current_pos_list_id is not None
                and current_pos_list_id != pos_list_id):
                self.roles.append(Role(conn, self.language_code, self.entry_id, current_pos_list_id, sense_ids, restrictions))
                sense_ids = []
            current_pos_list_id = pos_list_id
            sense_ids.append(sense_id)
        else:
            if current_pos_list_id is not None:
                self.roles.append(Role(conn, self.language_code, self.entry_id, current_pos_list_id, sense_ids, restrictions))
                

    def __repr__(self):
        return ('<%s(%r, %d) %s【%s】%s>'
                % (self.__class__.__name__,
                   self.language_code,
                   self.entry_id,
                   self.headwords[0][0],
                   self.headwords[0][1],
                   '' if self.discriminator is None
                   else circled_number(self.discriminator, False)))


    def __str__(self):
        out = '\033[35m%s【%s】\033[0m' % self.headwords[0]
        if self.discriminator is not None:
            out += circled_number(self.discriminator, False)
        out += '\n' + '-' * 8 + '\n'
        for nonkana, reading in self.headwords[1:]:
            out += '%s【%s】\n' % (nonkana, reading)
        out += '\n'.join(str(role) for role in self.roles)
        return out


    @staticmethod
    def lookup(conn, language_code, graphic, phonetic, restrictions):
        """Look up all lexemes that may be represented by the specified
        combination of a graphic and a phonetic variant.

        :param str language_code: ISO 639-3 language code of the language of
            interest.

        :param str graphic: The graphic variant.

        :param str phonetic: The phonetic variant.

        :param dict restrictions: A dictionary describing the restrictions
            imposed on the possible structural ways in which the POS tags may
            interrelate.  Necessary in order to provide POS tag trees.

        :return: A tuple of lexemes that contain the specified combination of a
            graphic variant and a phonetic variant in their list of headwords.

        """
        c = conn.cursor()
        entry_ids = tuple(c.execute('SELECT entry_id FROM lemmas WHERE language = ? AND graphic = ? and phonetic = ?', (language_code, graphic, hiragana_to_katakana(phonetic))))
        return tuple(Lexeme(conn, language_code, entry_id, restrictions) for (entry_id,) in entry_ids)


class Role():
    """A role in the dictionary.

    A role in this context means a collection of connotations of a lexeme that
    have the same grammatical functions in text.

    In addition to the connotations, a role has a part-of-speech (POS) list.
    POS tags in this list may have mutually hierarchical, nonconflicting, and
    even exclusive relations.

    A dictionary entry may contain multiple roles ``A`` and ``B`` with the same
    POS lists if the entry's connotations are sorted by frequency of use, and a
    third role ``C`` with a different POS list has connotations with a lower
    frequency than those of ``A`` and with a higher frequency than those of
    ``B``.

    On construction, all relevant data is loaded from the database.

    :param conn: The database connection for the dictionary.

    :param str language_code: ISO 639-3 language code of the language of
        interest.

    :param int entry_id: The ID of the dictionary entry to which this role
        belongs.

    :param int pos_list_id: The ID of the list of POS tags for this role.

    :param sense_id: An iterable of integer IDs of the connotations of this
        role.

    :param dict restrictions: A dictionary describing the restrictions imposed
        on the possible structural ways in which the POS tags may interrelate.
        Necessary in order to provide POS tag trees.

    """

    def __init__(self, conn, language_code, entry_id, pos_list_id, sense_ids, restrictions):
        c = conn.cursor()
        self.language_code = language_code
        self.entry_id = entry_id
        self.pos_tags = tuple(pos for (pos,) in c.execute('SELECT pos FROM pos_lists WHERE language = ? AND pos_list_id = ? ORDER BY sequence_id', (self.language_code, pos_list_id)))
        self.restrictions = restrictions
        self.senses = tuple(Sense(conn, self.language_code, self.entry_id, sense_id) for sense_id in sense_ids)


    def normalized_pos_tags(self):
        """Translate the list of POS tags as used in the dictionary to a list of
        POS tags in the representation used internally.

        :return: The list of POS tags associated with this role, in their
            internal representation.

        """
        pos_list = []
        for pos in self.pos_tags:
            pos_list.extend([i for i in re.split('[:;]', pos) if i != ''])
        return pos_list


    def pos_tree(self) -> TemplateTree:
        """From the POS tags of this role, build a tree structure.

        The restrictions of this role are used on tree creation.

        :return: A template tree that represents the list of POS tags associated
            with this role in a hierarchical fashion.

        """
        return TemplateTree.parse(self.normalized_pos_tags(), self.restrictions)


    def __repr__(self):
        return ('<%s(%r, %d, %r, %r)>'
                % (self.__class__.__name__,
                   self.language_code,
                   self.entry_id,
                   self.pos_tags,
                   self.senses))


    def __str__(self):
        return '\n  '.join([str(self.pos_tree())] + [str(sense) for sense in self.senses])


# TODO Rename to 'Connotation'
class Sense():
    """A connotation in the dictionary.

    A connotation in this context means an abstract word meaning that is limited
    to a specific lexeme.  Multiple lexemes may appear in text conveying the
    same meaning, and multiple meanings may be denoted by the same lexeme, but
    each combination of lexeme and sense is a unique connotation.

    A connotation may be described by multiple glosses, each of which can be a
    direct translation, a description or similar.

    On construction, all relevant data is loaded from the database.

    :param conn: The database connection for the dictionary.

    :param str language_code: ISO 639-3 language code of the language of
        interest.

    :param int entry_id: The ID of the dictionary entry to which this
        connotation belongs.

    :param int sense_id: The ID of this connotation w.r.t. the entry with ID
        ``entry_id``.

    """
    
    def __init__(self, conn, language_code, entry_id, sense_id):
        c = conn.cursor()
        self.language_code = language_code
        self.entry_id = entry_id
        self.sense_id = sense_id
        self.glosses = tuple(c.execute('SELECT type, gloss FROM glosses WHERE language = ? AND entry_id = ? AND sense_id = ? ORDER BY sequence_id', (self.language_code, self.entry_id, self.sense_id)))


    def __repr__(self):
        return ('<%s(%r, %d, %d)>'
                % (self.__class__.__name__, self.language_code, self.entry_id, self.sense_id))


    def __str__(self):
        return (circled_number(self.sense_id) + ' '
                + (' ' + GLOSS_SEPARATOR + ' ').join(
                    [gloss for gloss_type, gloss in self.glosses]))
