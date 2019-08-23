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
import json
import sqlite3 as sql
from elasticsearch import Elasticsearch, RequestError

if __name__ == '__main__':
    sys.path.append(os.path.abspath(os.path.dirname(os.path.abspath(__file__))
                                    + '/../..'))
    from yokome.features.dictionary import Lexeme
else:
    from ..features.dictionary import Lexeme


INDEX_NAME = 'jpn_inverse_dictionary'
SETUP_FILE = os.path.abspath(os.path.dirname(os.path.abspath(__file__))
                             + '/../../data/crafted'
                             + '/jpn_inverse_dictionary_setup.json')
DICTIONARY_FILE = os.path.abspath(os.path.dirname(os.path.abspath(__file__))
                                  + '/../../data/processed/data.db')
RESTRICTIONS_FILE = os.path.abspath(os.path.dirname(os.path.abspath(__file__))
                                    + '/../../data/crafted'
                                    + '/jpn_pos_restrictions.json')


if __name__ == '__main__':
    es = Elasticsearch(['localhost:9200'])

    if es.indices.exists(INDEX_NAME):
        print('Deleting index %s' % (INDEX_NAME,), end=': ')
        print(es.indices.delete(index=INDEX_NAME))
    try:
        print('Creating index %s' % (INDEX_NAME,), end=': ')
        with open(SETUP_FILE, 'r') as f:
            setup = f.read()
        print(es.indices.create(index=INDEX_NAME, body=setup))
    except RequestError as e:
        print(e.error)
        sys.exit(1)

    with open(RESTRICTIONS_FILE, 'r') as f:
        restrictions = json.load(f)

    with sql.connect(DICTIONARY_FILE) as conn:
        c = conn.cursor()
        entry_ids = tuple(i for (i,)
                          in c.execute('SELECT DISTINCT entry_id FROM roles'))
        for i, entry_id in enumerate(entry_ids):
            print('%6d/%6d' % (i + 1, len(entry_ids)))
            lexeme = Lexeme(conn, entry_id, restrictions)
            lemmas = [{'graphic': graphic, 'phonetic': phonetic}
                      for graphic, phonetic in c.execute(
                              '''SELECT graphic, phonetic
                                 FROM lemmas
                                 WHERE entry_id = ?''',
                              (entry_id,))]
            for role in lexeme.roles:
                normalized_pos_tags = role.normalized_pos_tags()
                for sense in role.senses:
                    es.create(index=INDEX_NAME,
                              doc_type='_doc',
                              id='jpn:%d:%d' % (entry_id, sense.sense_id),
                              body={'language': 'jpn',
                                    'entry_id': entry_id,
                                    'sense_id': sense.sense_id,
                                    'lemmas': lemmas,
                                    'pos': normalized_pos_tags,
                                    'glosses': [gloss
                                                for _, gloss in sense.glosses]})
