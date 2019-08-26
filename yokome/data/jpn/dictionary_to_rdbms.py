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


# TODO Use in package, not as module
"""Transfer entries from a JMdict XML file to an SQLite database."""

import sys
import os
import click
from pathlib2 import Path
from xml.etree import ElementTree
# TODO Use a different SQLite wrapper to allow for atomic transactions
import sqlite3 as sql

_PROJECT_ROOT = os.path.abspath(os.path.dirname(os.path.abspath(__file__))
                                + '/../../..')
if _PROJECT_ROOT not in sys.path:
    sys.path.append(_PROJECT_ROOT)
from yokome.features.dictionary import GLOSS_SEPARATOR
from yokome.features.jpn import is_reading, hiragana_to_katakana


UK = 'word usually written using kana alone'
"""JMdict entity marking a word that is usually written using kana only.

Triggers the insertion of a kana-only row into the lemma table of the resulting
database.  For entries in JMdict that do not contain this entity in a <misc/>
tag, a kana-only row is only inserted if there is no <k_ele/> tag in the entry.
"""

# TODO Add unused, but missing tags (see http://www.edrdg.org/jmdictdb/cgi-bin/edhelp.py?svc=jmdict&sid=#kw_pos)
POS = {
    # Nouns
    "noun (common) (futsuumeishi)": 'noun',
    "pronoun": 'pronoun',
    "proper noun": 'proper noun',
    "adverbial noun (fukushitekimeishi)": 'adverb:adverbial noun;noun:adverbial noun',
    "noun (temporal) (jisoumeishi)": 'adverb:temporal noun;noun:temporal noun',
    "noun, used as a prefix": 'prefix;noun',
    "noun, used as a suffix": 'suffix;noun',
    "noun or participle which takes the aux. verb suru": 'suru verb',
    # Adjectivals
    "adjective (keiyoushi)": 'i-adjective',
    "adjective (keiyoushi) - yoi/ii class": 'yoi/ii class',
    "adjectival nouns or quasi-adjectives (keiyodoshi)": 'na-adjective',
    "nouns which may take the genitive case particle `no'": 'no-adjective',
    "`taru' adjective": 'taru-adjective',
    "`kari' adjective (archaic)": 'kari-adjective', # Not found in the data
    "`ku' adjective (archaic)": 'ku-adjective',
    "`shiku' adjective (archaic)": 'shiku-adjective',
    "archaic/formal form of na-adjective": 'nari-adjective',
    "pre-noun adjectival (rentaishi)": 'pre-noun adjectival',
    "noun or verb acting prenominally": 'prenominal',
    # Adverbs
    "adverb (fukushi)": 'adverb',
    "adverb taking the `to' particle": 'quotable',
    # Affixes
    "prefix": 'prefix',
    "suffix": 'suffix',
    # Verbs
    "Ichidan verb": 'verb:monograde::ra column:regular:',
    "Ichidan verb - kureru special class": 'verb:monograde::ra column:kureru special class:',
    "Ichidan verb - zuru verb (alternative form of -jiru verbs)": 'verb:monograde:::-zuru ending:',
    "Godan verb with `u' ending": 'verb:quintigrade::a column:regular:',
    "Godan verb with `u' ending (special class)": "verb:quintigrade::a column:-'u special class:",
    "Godan verb with `ku' ending": 'verb:quintigrade::ka column:regular:',
    "Godan verb with `gu' ending": 'verb:quintigrade::ga column:regular:',
    "Godan verb with `su' ending": 'verb:quintigrade::sa column:regular:',
    "Godan verb with `tsu' ending": 'verb:quintigrade::ta column:regular:',
    "Godan verb with `nu' ending": 'verb:quintigrade::na column:regular:',
    "Godan verb with `bu' ending": 'verb:quintigrade::ba column:regular:',
    "Godan verb with `mu' ending": 'verb:quintigrade::ma column:regular:',
    "Godan verb with `ru' ending": 'verb:quintigrade::ra column:regular:',
    "Godan verb with `ru' ending (irregular verb)": 'verb:quintigrade::ra column:-ru irregular:',
    "Godan verb - -aru special class": 'verb:quintigrade::ra column:-aru special class:',
    "Godan verb - Iku/Yuku special class": 'verb:quintigrade::ka column:iku/yuku special class:',
    "Godan verb - Uru old class verb (old form of Eru)": 'verb:quintigrade::ra column:uru special class:', # Not found in the data
    "Yodan verb with `ku' ending (archaic)": 'verb:quadrigrade::ka column:regular:',
    "Yodan verb with `gu' ending (archaic)": 'verb:quadrigrade::ga column:regular:',
    "Yodan verb with `su' ending (archaic)": 'verb:quadrigrade::sa column:regular:',
    "Yodan verb with `tsu' ending (archaic)": 'verb:quadrigrade::ta column:regular:',
    "Yodan verb with `nu' ending (archaic)": 'verb:quadrigrade::na column:regular:', # Not found in the data
    "Yodan verb with `hu/fu' ending (archaic)": 'verb:quadrigrade::ha column:regular:',
    "Yodan verb with `bu' ending (archaic)": 'verb:quadrigrade::ba column:regular:',
    "Yodan verb with `mu' ending (archaic)": 'verb:quadrigrade::ma column:regular:',
    "Yodan verb with `ru' ending (archaic)": 'verb:quadrigrade::ra column:regular:',
    "Nidan verb (upper class) with `ku' ending (archaic)": 'verb:bigrade:upper class:ka column:regular:',
    "Nidan verb (upper class) with `gu' ending (archaic)": 'verb:bigrade:upper class:ga column:regular:',
    "Nidan verb (upper class) with `tsu' ending (archaic)": 'verb:bigrade:upper class:ta column:regular:',
    "Nidan verb (upper class) with `dzu' ending (archaic)": 'verb:bigrade:upper class:da column:regular:', # Not found in the data
    "Nidan verb (upper class) with `hu/fu' ending (archaic)": 'verb:bigrade:upper class:ha column:regular:',
    "Nidan verb (upper class) with `bu' ending (archaic)": 'verb:bigrade:upper class:ba column:regular:',
    "Nidan verb (upper class) with `mu' ending (archaic)": 'verb:bigrade:upper class:na column:regular:', # Not found in the data
    "Nidan verb (upper class) with `yu' ending (archaic)": 'verb:bigrade:upper class:ya column:regular:',
    "Nidan verb (upper class) with `ru' ending (archaic)": 'verb:bigrade:upper class:ra column:regular:',
    "Nidan verb with 'u' ending (archaic)": 'verb:bigrade:lower class:a column:regular:',
    "Nidan verb (lower class) with `ku' ending (archaic)": 'verb:bigrade:lower class:ka column:regular:',
    "Nidan verb (lower class) with `gu' ending (archaic)": 'verb:bigrade:lower class:ga column:regular:',
    "Nidan verb (lower class) with `su' ending (archaic)": 'verb:bigrade:lower class:sa column:regular:',
    "Nidan verb (lower class) with `zu' ending (archaic)": 'verb:bigrade:lower class:za column:regular:',
    "Nidan verb (lower class) with `tsu' ending (archaic)": 'verb:bigrade:lower class:ta column:regular:',
    "Nidan verb (lower class) with `dzu' ending (archaic)": 'verb:bigrade:lower class:da column:regular:',
    "Nidan verb (lower class) with `nu' ending (archaic)": 'verb:bigrade:lower class:na column:regular:',
    "Nidan verb (lower class) with `hu/fu' ending (archaic)": 'verb:bigrade:lower class:ha column:regular:',
    "Nidan verb (lower class) with `bu' ending (archaic)": 'verb:bigrade:lower class:ba column:regular:', # Not found in the data
    "Nidan verb (lower class) with `mu' ending (archaic)": 'verb:bigrade:lower class:ma column:regular:',
    "Nidan verb (lower class) with `yu' ending (archaic)": 'verb:bigrade:lower class:ya column:regular:',
    "Nidan verb (lower class) with `ru' ending (archaic)": 'verb:bigrade:lower class:ra column:regular:',
    "Nidan verb (lower class) with `u' ending and `we' conjugation (archaic)": 'verb:bigrade:lower class:wa column:regular:',
    "Kuru verb - special class": 'verb:k-irregular::::',
    "suru verb - included": 'verb:s-irregular:::suru class:suru ending', # Suru itself and its derivatives
    "suru verb - special class": 'verb:s-irregular:::suru class:-suru ending', # Verbs with the suffix -suru that are conjugated like suru
    "su verb - precursor to the modern suru": 'verb:s-irregular:::su class:',
    "irregular nu verb": 'verb:n-irregular::::',
    "irregular ru verb, plain form ends with -ri": 'verb:r-irregular::::',
    "irregular verb": 'verb:irregular::::', # Not found in the data
    "verb unspecified": 'verb:::::',        # Not found in the data
    # Verb transitivity
    "transitive verb": 'transitive',
    "intransitive verb": 'intransitive',
    # Auxiliaries
    "auxiliary": 'auxiliary',
    "auxiliary verb": 'auxiliary;verb',
    "auxiliary adjective": 'auxiliary;adjective',
    # Function words
    "particle": 'particle',
    "conjunction": 'conjunction',
    "copula": 'copula',
    # Quantification
    "numeric": 'numeral',
    "counter": 'suffix:counter',
    # Other semantic units
    "interjection (kandoushi)": 'interjection',
    "expressions (phrases, clauses, etc.)": 'multiword',
    "unclassified": ''}
"""Mapping from JMdict POS entities to POS tags."""

USAGE = {
    # Expressing the relationship to the listener / the ones affected
    "honorific or respectful (sonkeigo) language": ('relationship', 'hon.'),
    "humble (kenjougo) language": ('relationship', 'hum.'),
    "polite (teineigo) language": ('relationship', 'pol.'),
    "familiar language": ('relationship', 'fam.'),
    "derogatory": ('relationship', 'derog.'),
    # Expressing the kind of speaker
    "children's language": ('speaker', 'childish'),
    "female term or language": ('speaker', 'f. language'),
    "male term or language": ('speaker', 'm. language'),
    "slang": ('speaker', 'slang'),
    "male slang": ('speaker', 'm. slang'),            # Not found in the data
    "manga slang": ('speaker', 'manga slang'),
    # Frequency of use
    "rare": ('frequency', 'rare'),
    "obsolete term": ('frequency', 'obsolete'),
    "archaism": ('frequency', 'archaic'),
    # Accuracy
    "obscure term": ('accuracy', 'obscure'),
    # Expressing a subliminal/implied meaning
    "poetical term": ('meaning', 'poet.'),
    "jocular, humorous term": ('meaning', 'joc.'),
    "idiomatic expression": ('meaning', 'idiom'),
    "colloquialism": ('meaning', 'coll.'),
    "sensitive": ('meaning', 'sensitive'),
    "vulgar expression or word": ('meaning', 'vulg.'),
    "rude or X-rated term (not displayed in educational software)": ('meaning', 'rude/X-rated'), # Does not appear in the XML file, probably dropped from the data beforehand
    # Extended POS
    "abbreviation": ('POS', 'abbr.'),
    "onomatopoeic or mimetic word": ('POS', 'on./mim.'),
    "proverb": ('POS', 'proverb'),
    "quotation": ('POS', 'quote'),
    # Writing pertaining to a sense
    "exclusively kanji": ('spelling', 'exclusively kanji'), # Not found in the data
    "exclusively kana": ('spelling', 'exclusively kana'),   # Not found in the data
    "word usually written using kanji alone": ('spelling', 'usu. wr. in kanji'), # Not found in the data
    UK: ('spelling', 'usu. wr. in kana'),
    "yojijukugo": ('spelling', 'yojijukugo')}
"""Mapping from JMdict usage entities to usage types and short descriptions."""

WRITING = {
    # Pertaining to a nonkana form
    "word containing irregular kanji usage": 'irregular kanji usage',
    "word containing out-dated kanji": 'outdated kanji',
    "irregular okurigana usage": 'irregular okurigana usage',
    "ateji (phonetic) reading": 'ateji',
    # Pertaining to a kana form
    "word containing irregular kana usage": 'irregular kana usage',
    "out-dated or obsolete kana usage": 'outdated/obsolete kana usage',
    "old or irregular kana form": 'old/irregular kana form',
    "gikun (meaning as reading) or jukujikun (special kanji reading)": 'gikun/jukujikun'}
"""Mapping from JMdict writing style entities to short descriptions."""

DOMAINS = {
    "mathematics": 'math.',
    "geometry term": 'geom.',
    "engineering term": 'engin.',
    "computer terminology": 'comp.',
    "architecture term": 'archit.',
    "physics terminology": 'phys.',
    "astronomy, etc. term": 'astron.',
    "chemistry term": 'chem.',
    "biology term": 'biol.',
    "botany term": 'bot.',
    "zoology term": 'zool.',
    "medicine, etc. term": 'med.',
    "anatomical term": 'anat.',
    "food term": 'food',
    "geology, etc. term": 'geol.',
    "linguistics terminology": 'ling.',
    "music term": 'music',
    "business term": 'bus.',
    "economics term": 'econ.',
    "finance term": 'fin.',
    "law, etc. term": 'law',
    "military": 'mil.',
    "sports term": 'sports',
    "baseball term": 'baseb.',
    "martial arts term": 'MA',
    "sumo term": 'sumo',
    "shogi term": 'shogi',
    "mahjong term": 'mahj.',
    "Buddhist term": 'Buddh.',
    "Shinto term": 'Shinto'}
"""Mapping from JMdict domain entities to domain abbreviations."""

# XXX Currently not used, dialects are inserted verbatim
DIALECT = {                             # Glottocode IDs (see
                                        # https://glottolog.org/):
    
    # Eastern Japanese
    "Hokkaido-ben": 'hob',              # hokk1249
    "Kantou-ben": 'ktb',                # kant1251
    "Touhoku-ben": 'thb',               # toho1244
    "Tsugaru-ben": 'tsug',              # tsug1237, subdialect of toho1244
    "Nagano-ben": 'nab',                # naga1408

    # Kyūshū
    "Kyuushuu-ben": 'kyu',              # kyus1238

    # Western Japanese
    "Kansai-ben": 'ksb',                # kink1238
    "Kyoto-ben": 'kyb',                 # kyot1238, subdialect of kink1238
    "Osaka-ben": 'osb',                 # osak1237, subdialect of kink1238
    "Tosa-ben": 'tsb',                  # None; aka Kōchi-ben, closest
                                        # neighboring dialect or subdialect:
                                        # Hata-ben (hata1244), closest parent:
                                        # Shikoku-ben (shik1243), a dialect that
                                        # is disjoint to all the other dialects
                                        # listed here
    
    # Ryūkyūan, not a Japanese dialect, but rather a different set of Japonic
    # languages
    "Ryuukyuu-ben": 'rkb'}              # ryuk1243
"""Mapping from JMdict dialect entities to dialect codes."""

GLOSS_TYPES = {
    'expl': 'i.e.',
    'lit': 'lit.',
    'fig': 'fig.'}
"""Mapping from JMdict gloss types to more readable representations."""


# TODO Check whether the katakana middle dot itself is referenced from another
# entry; add corresponding asserts
def parse_reference(reference):
    parts = reference.split('・')
    if len(parts) == 3:
        result = (parts[0], parts[1], int(parts[2]))
    elif len(parts) == 2:
        try:
            if is_reading(parts[0]):
                result = (None, parts[0], int(parts[1]))
            else:
                result = (parts[0], None, int(parts[1]))
        except ValueError:
            result = (parts[0], parts[1], None)
    elif len(parts) == 1:
        if is_reading(parts[0]):
            result = (None, parts[0], None)
        else:
            result = (parts[0], None, None)
    else:
        raise AssertionError('Malformed reference %s' % (reference,))
    return result


@click.command()
@click.argument('jmdict_file',  # The location of the XML file containing JMdict
                type=click.Path(exists=True, file_okay=True, dir_okay=False))
def main(jmdict_file):
    resource_dir = _PROJECT_ROOT + '/data/processed'
    Path(resource_dir).mkdir(exist_ok=True)
    database_file = resource_dir + '/data.db'
    # assert not Path(database_file).exists(), 'Database file already existing'
    if Path(database_file).exists():
        assert Path(database_file).is_file()
        print('Rebuilding dictionary database...')
        os.remove(database_file)
    else:
        print('Creating dictionary database...')
    # database_file = ':memory:'

    NAMESPACES = {'xml': 'http://www.w3.org/XML/1998/namespace'}
    jmdict_file = os.path.abspath(os.path.expanduser(jmdict_file))
    assert Path(jmdict_file).is_file(), 'JMdict file missing'
    root = ElementTree.parse(jmdict_file).getroot()

    # XXX Add progress indicators
    # TODO Check revision of JMdict file and warn when it changed
    # TODO Check whether all types of data are imported for the current revision
    # of the JMdict format
    with sql.connect(database_file) as conn:
        c = conn.cursor()
        c.execute('PRAGMA encoding="UTF-8"')
        # TODO Use foreign keys
        c.execute('PRAGMA foreign_keys=ON')
        print('    Creating tables...')
        # Surface forms for dictionary searches
        # XXX Inconsistent use of the term 'lemmas': use 'base_forms' istead
        # XXX Use 'reading', or at least 'phonemic' instead of 'phonetic'
        c.execute('''CREATE TABLE lemmas (
            language TEXT NOT NULL,
            graphic TEXT NOT NULL,
            phonetic TEXT NOT NULL,
            entry_id INTEGER NOT NULL)''')
        # Graphical variants and readings for display of dictionary entries
        # 
        # (nonkana, reading) pairs are not unique (e.g. (何もの, なにもの) may refer
        # to both 何者 and 何物).  Not even the first (nonkana, reading) pairs of
        # different entries, respectively, are unique.  Word-sense disambiguation
        # for (nonkana, reading) pairs making use of a dictionary lookup to find
        # reference-language senses thus always has to be able to handle multiple
        # lexemes.
        #
        # XXX Mark non-existing graphical variant not by NONE value, but provide
        # the same phonetic variant in both positions
        # 
        # XXX Use different term for 'nonkana'
        c.execute('''CREATE TABLE lexemes (
            language TEXT NOT NULL,
            entry_id INTEGER NOT NULL,
            sequence_id INTEGER NOT NULL,
            nonkana TEXT,
            reading TEXT NOT NULL,
            PRIMARY KEY (language, entry_id, sequence_id))''')
        # Notes on graphical variants and readings
        c.execute('''CREATE TABLE orthography (
            language TEXT NOT NULL,
            entry_id INTEGER NOT NULL,
            variant TEXT NOT NULL,
            note TEXT NOT NULL)''')
        c.execute('''CREATE TABLE roles (
            language TEXT NOT NULL,
            entry_id INTEGER NOT NULL,
            pos_list_id INTEGER NOT NULL,
            sense_id INTEGER NOT NULL,
            PRIMARY KEY (language, entry_id, sense_id))''')
        c.execute('''CREATE TABLE pos_lists (
            language TEXT NOT NULL,
            pos_list_id INTEGER NOT NULL,
            sequence_id INTEGER NOT NULL,
            pos TEXT NOT NULL,
            PRIMARY KEY (language, pos_list_id, sequence_id))''')
        c.execute('''CREATE TABLE glosses(
            language TEXT NOT NULL,
            entry_id INTEGER NOT NULL,
            sense_id INTEGER NOT NULL,
            sequence_id INTEGER NOT NULL,
            type TEXT,
            gloss TEXT NOT NULL,
            PRIMARY KEY (language, entry_id, sense_id, sequence_id),
            FOREIGN KEY (language, entry_id, sense_id) REFERENCES roles)''')
        c.execute('''CREATE TABLE restrictions (
            language TEXT NOT NULL,
            entry_id INTEGER NOT NULL,
            sense_id INTEGER NOT NULL,
            variant TEXT NOT NULL,
            FOREIGN KEY (language, entry_id, sense_id) REFERENCES roles)''')
        # Similar senses and antonyms
        # XXX Directly link using entry IDs
        c.execute('''CREATE TABLE related (
            language TEXT NOT NULL,
            entry_id INTEGER NOT NULL,
            sense_id INTEGER NOT NULL,
            relation TEXT NOT NULL,
            nonkana TEXT,
            reading TEXT,
            sense_id_other INTEGER,
            FOREIGN KEY (language, entry_id, sense_id) REFERENCES roles,
            CHECK (nonkana IS NOT NULL OR reading IS NOT NULL))''')
        # XXX Add check for ISO 639-3 / 639-2 language code on language
        c.execute('''CREATE TABLE source_languages (
            language TEXT NOT NULL,
            entry_id INTEGER NOT NULL,
            sense_id INTEGER NOT NULL,
            source_language TEXT NOT NULL,
            original_expression TEXT,
            wasei INTEGER NOT NULL CHECK (wasei = 0 OR wasei = 1),
            FOREIGN KEY (language, entry_id, sense_id) REFERENCES roles)''') # XXX Use boolean type
        # Domain of use, dialect, sense information, miscellaneous
        c.execute('''CREATE TABLE notes (
            language TEXT NOT NULL,
            entry_id INTEGER NOT NULL,
            sense_id INTEGER NOT NULL,
            note_type TEXT NOT NULL,
            note TEXT NOT NULL,
            FOREIGN KEY (language, entry_id, sense_id) REFERENCES roles)''') # XXX Use IDs for notes to save storage space
        print('    Processing entries...')
        poss_all = dict()
        poss_count = 0
        for i, entry in enumerate(root):
            entry_id = int(entry[0].text)
            ks = []                # Sorted set of non-kana forms to retain ordering
            k_dict = dict()        # Non-kana forms and readings for presentation
            for k_ele in entry.findall('k_ele'):
                assert not is_reading(k_ele[0].text), 'Reading representation %s' % (k_ele[0].text,)
                if k_ele[0].text not in ks:
                    ks.append(k_ele[0].text)
                k_dict[k_ele[0].text] = []
                c.executemany('INSERT INTO orthography VALUES ("jpn", ?, ?, ?)',
                              [(entry_id, k_ele[0].text, WRITING[ke_inf.text])
                               for ke_inf in k_ele.findall('ke_inf')])
            if not list(k_dict.keys()):
                k_dict[None] = []
            for r_ele in entry.findall('r_ele'):
                assert is_reading(r_ele[0].text), 'Non-reading representation %s' % (r_ele[0].text,)
                re_restrs = [k.text for k in r_ele.findall('re_restr')]
                if re_restrs:
                    for re_restr in re_restrs:
                        if r_ele[0].text not in k_dict[re_restr]:
                            k_dict[re_restr].append(r_ele[0].text)
                else:
                    for k in k_dict.keys():
                        if r_ele[0].text not in k_dict[k]:
                            k_dict[k].append(r_ele[0].text)
                c.executemany('INSERT INTO orthography VALUES ("jpn", ?, ?, ?)',
                              [(entry_id, r_ele[0].text, WRITING[re_inf.text])
                               for re_inf in r_ele.findall('re_inf')])
            surface_forms = set() # Surface forms and normalized readings for
                                  # lookup
            if None in k_dict:
                # No non-kana surface forms: Add all kana forms to the surface
                # forms, together with their normalized readings
                for r in k_dict[None]:
                    surface_forms.add((r, hiragana_to_katakana(r)))
            else:
                # Add all non-kana forms to the surface forms, together with
                # their normalized readings
                for k, rs in k_dict.items():
                    for r in rs:
                        surface_forms.add((k, hiragana_to_katakana(r)))
            english_only = True # Check whether English senses always occupy the
                                # first senses
            for j, sense in enumerate(entry.findall('sense'), start=1):
                # Conditionally add kana forms to surface forms
                if UK in [misc.text for misc in sense.findall('misc')]:
                    stagks = [s.text for s in sense.findall('stagk')]
                    stagrs = [s.text for s in sense.findall('stagr')]
                    if not stagks + stagrs:
                        for k, rs in k_dict.items():
                            for r in rs:
                                surface_forms.add((r, hiragana_to_katakana(r)))
                    else:
                        for stagk in stagks:
                            for r in k_dict[stagk]:
                                surface_forms.add((r, hiragana_to_katakana(r)))
                        for stagr in stagrs:
                            surface_forms.add((stagr, hiragana_to_katakana(stagr)))
                # Collect English senses per POS
                poss = tuple(POS[pos.text] for pos in sense.findall('pos'))
                if poss:
                    if poss not in poss_all:
                        poss_count += 1
                        poss_all[poss] = poss_count
                    # Once defined, a list of POS tags is valid for all senses
                    # until redefined
                    current_poss = poss
                glosses = sense.findall('gloss')
                if any(gloss.attrib['{' + NAMESPACES['xml'] + '}lang'] == 'eng'
                       for gloss in glosses):
                    assert all(gloss.attrib['{' + NAMESPACES['xml'] + '}lang'] == 'eng'
                               for gloss in glosses), 'Inconsistent languages in glosses'
                    if not english_only:
                        print('        \033[1;33mWARN\033[0m: Non-English glosses '
                              + 'among first senses for entry %d' % (entry_id,))
                    # XXX If clause not necessary due to the assert above
                    assert all(GLOSS_SEPARATOR not in gloss.text
                               for gloss in glosses
                               if gloss.attrib['{' + NAMESPACES['xml'] + '}lang'] == 'eng'),\
                        'Separator \'%s\' found in gloss' % (GLOSS_SEPARATOR,)
                    c.execute('INSERT INTO roles VALUES ("jpn", ?, ?, ?)',
                              (entry_id, poss_all[current_poss], j))
                    # XXX If clause not necessary due to the assert above
                    c.executemany('INSERT INTO glosses VALUES ("jpn", ?, ?, ?, ?, ?)',
                                  [(entry_id, j, h, *gloss) for h, gloss
                                   in enumerate([(GLOSS_TYPES[gloss.attrib['g_type']] if 'g_type' in gloss.attrib else None, gloss.text) for gloss in glosses
                                                 if gloss.attrib['{' + NAMESPACES['xml'] + '}lang'] == 'eng'], start=1)])
                    c.executemany('INSERT INTO restrictions VALUES ("jpn", ?, ?, ?)',
                                  [(entry_id, j, stag.text) for stag in
                                   sense.findall('stagk') + sense.findall('stagr')])
                    c.executemany('INSERT INTO related VALUES ("jpn", ?, ?, ?, ?, ?, ?)',
                                  [(entry_id, j, rel, *parse_reference(ref))
                                   for rel, ref in
                                   [('cross-reference', x.text)
                                    for x in sense.findall('xref')]
                                   + [('antonym', a.text)
                                      for a in sense.findall('ant')]])
                    c.executemany('INSERT INTO source_languages VALUES ("jpn", ?, ?, ?, ?, ?)',
                                  [(entry_id, j, lsource.attrib['{' + NAMESPACES['xml'] + '}lang'], lsource.text if lsource.text != '' else None, 1 if 'ls_wasei' in lsource.attrib else 0)
                                   for lsource in sense.findall('lsource')])
                    c.executemany('INSERT INTO notes VALUES ("jpn", ?, ?, ?, ?)',
                                  [(entry_id, j, *USAGE[misc.text])
                                   for misc in sense.findall('misc')])
                    # XXX Use Glottocodes or other IDs instead of dial.text
                    c.executemany('INSERT INTO notes VALUES ("jpn", ?, ?, ?, ?)',
                                  [(entry_id, j, 'dialect', dial.text)
                                   for dial in sense.findall('dial')])
                    c.executemany('INSERT INTO notes VALUES ("jpn", ?, ?, ?, ?)',
                                  [(entry_id, j, 'domain', DOMAINS[field.text])
                                   for field in sense.findall('field')])
                    c.executemany('INSERT INTO notes VALUES ("jpn", ?, ?, ?, ?)',
                                  [(entry_id, j, 'remark', s_inf.text)
                                   for s_inf in sense.findall('s_inf')])
                else:
                    english_only = False
            # Send aggregated entry data to database
            j = 0
            for k, rs in ([(key, k_dict[key]) for key in ks]
                          if ks else [[None, k_dict[None]]]):
                for r in rs:
                    j += 1
                    c.execute('INSERT INTO lexemes VALUES ("jpn", ?, ?, ?, ?)',
                              (entry_id, j, k, r))
            c.executemany('INSERT INTO lemmas VALUES ("jpn", ?, ?, ?)',
                          [(surface_form, normalized_form, entry_id)
                           for surface_form, normalized_form in surface_forms])
        print('    Storing global data...')
        for poss, j in poss_all.items():
            c.executemany('INSERT INTO pos_lists VALUES ("jpn", ?, ?, ?)',
                          [(j, h, p) for h, p in enumerate(poss, start=1)])
        print('    Building indices...')
        c.execute('REINDEX')            # Optimize existing indices
        c.execute('''CREATE INDEX lemmas_graphic_phonetic_idx
            ON lemmas (language, graphic, phonetic)''')
        c.execute('''CREATE INDEX lexemes_nonkana_reading_idx
            ON lexemes (language, nonkana, reading)''')
        c.execute('''CREATE INDEX orthography_entry_id_idx
            ON orthography (language, entry_id)''')
        c.execute('''CREATE INDEX roles_find_role_sort_sense_idx
            ON roles (language, entry_id, pos_list_id, sense_id)''')
        c.execute('''CREATE INDEX pos_lists_pos_idx
            ON pos_lists (language, pos)''')
        c.execute('''CREATE INDEX restrictions_entry_id_sense_id_idx
            ON restrictions (language, entry_id, sense_id)''')
        c.execute('''CREATE INDEX related_entry_id_sense_id_idx
            ON related (language, entry_id, sense_id)''')
        c.execute('''CREATE INDEX source_languages_entry_id_sense_id_idx
            ON source_languages (language, entry_id, sense_id)''')
        c.execute('''CREATE INDEX source_languages_language_idx
            ON source_languages (language, source_language)''')
        c.execute('''CREATE INDEX notes_entry_id_sense_id_idx
            ON notes (language, entry_id, sense_id)''')
        c.execute('''CREATE INDEX notes_entry_id_note_idx
            ON notes (language, entry_id, note)''')
        c.execute('''CREATE INDEX notes_note_idx
            ON notes (note)''')
        print('    Optimizing database...')
        c.execute('ANALYZE')      # Calculate statistics for the query optimizer
        conn.commit()
        c.execute('VACUUM')             # Optimize database storage space
        conn.commit()
    print('    \033[1;32mDONE\033[0m')


if __name__ == '__main__':
    main()
