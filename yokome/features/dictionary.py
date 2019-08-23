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
from ..data.jmdict_to_db import GLOSS_SEPARATOR
from .tree import TemplateTree


def circled_number(number, bold_circle=True):
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
    def __init__(self, conn, entry_id, restrictions):
        c = conn.cursor()
        self.entry_id = entry_id
        self.headwords = tuple(c.execute('SELECT nonkana, reading FROM lexemes WHERE entry_id = ? ORDER BY sequence_id', (self.entry_id,)))
        if not self.headwords:
            raise ValueError('Unable to find entry with ID %d' % (self.entry_id,))
        # TODO Ensure that there is a suitable index for this query
        same_main_headword_entries = tuple(other_entry_id for (other_entry_id,) in c.execute('SELECT entry_id FROM lexemes WHERE nonkana IS ? AND reading = ? AND sequence_id = 1 ORDER BY entry_id' if self.headwords[0][0] is None else 'SELECT entry_id FROM lexemes WHERE nonkana = ? AND reading = ? AND sequence_id = 1 ORDER BY entry_id', self.headwords[0]))
        self.discriminator = next(j for j, other_entry_id in enumerate(same_main_headword_entries, start=1) if other_entry_id == self.entry_id) if len(same_main_headword_entries) > 1 else None
        self.roles = []
        current_pos_list_id = None
        sense_ids = []
        for (pos_list_id, sense_id) in tuple(c.execute('SELECT pos_list_id, sense_id FROM roles WHERE entry_id = ? ORDER BY sense_id', (self.entry_id,))):
            if (current_pos_list_id is not None
                and current_pos_list_id != pos_list_id):
                self.roles.append(Role(conn, self.entry_id, current_pos_list_id, sense_ids, restrictions))
                sense_ids = []
            current_pos_list_id = pos_list_id
            sense_ids.append(sense_id)
        else:
            if current_pos_list_id is not None:
                self.roles.append(Role(conn, self.entry_id, current_pos_list_id, sense_ids, restrictions))
                

    def __repr__(self):
        return ('<%s(%d) %s【%s】%s>'
                % (self.__class__.__name__,
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
    def lookup(conn, graphic, phonetic, restrictions):
        c = conn.cursor()
        entry_ids = tuple(c.execute('SELECT entry_id FROM lemmas WHERE graphic = ? and phonetic = ?', (graphic, hiragana_to_katakana(phonetic))))
        return tuple(Lexeme(conn, entry_id, restrictions) for (entry_id,) in entry_ids)

class Role():
    def __init__(self, conn, entry_id, pos_list_id, sense_ids, restrictions):
        c = conn.cursor()
        self.entry_id = entry_id
        self.pos_tags = tuple(pos for (pos,) in c.execute('SELECT pos FROM pos_lists WHERE pos_list_id = ? ORDER BY sequence_id', (pos_list_id,)))
        self.restrictions = restrictions
        self.senses = tuple(Sense(conn, self.entry_id, sense_id) for sense_id in sense_ids)

    def normalized_pos_tags(self):
        """Translate the list of POS tags as used in the dictionary to a list of
        POS tags in the representation used internally.

        """
        pos_list = []
        for pos in self.pos_tags:
            pos_list.extend([i for i in re.split('[:;]', pos) if i != ''])
        return pos_list

    def pos_tree(self):
        return TemplateTree.parse(self.normalized_pos_tags(), self.restrictions)

    def __repr__(self):
        return ('<%s(%d, %r, %r)>'
                % (self.__class__.__name__,
                   self.entry_id,
                   self.pos_tags,
                   self.senses))

    def __str__(self):
        return '\n  '.join([str(self.pos_tree())] + [str(sense) for sense in self.senses])


class Sense():
    def __init__(self, conn, entry_id, sense_id):
        c = conn.cursor()
        self.entry_id = entry_id
        self.sense_id = sense_id
        self.glosses = tuple(c.execute('SELECT type, gloss FROM glosses WHERE entry_id = ? AND sense_id = ? ORDER BY sequence_id', (self.entry_id, self.sense_id)))

    def __repr__(self):
        return ('<%s(%d, %d)>'
                % (self.__class__.__name__, self.entry_id, self.sense_id))

    def __str__(self):
        return (circled_number(self.sense_id) + ' '
                + (' ' + GLOSS_SEPARATOR + ' ').join(
                    [gloss for gloss_type, gloss in self.glosses]))
