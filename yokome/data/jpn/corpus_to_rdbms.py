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
from fractions import Fraction
from collections import defaultdict
import time
import asyncio
import json
import sqlite3 as sql


_PROJECT_ROOT = os.path.abspath(os.path.dirname(os.path.abspath(__file__))
                                + '/../../..')
if _PROJECT_ROOT not in sys.path:
    sys.path.append(_PROJECT_ROOT)
from yokome.data.jpn.corpus import validate_file, dev_files
from yokome.features.symbol_stream import to_symbol_stream, to_text, expand, ascii_fold
from yokome.features.jpn import chasen_loader, segmenter, strip, is_content_sentence, tokenize_stream_async, fullwidth_fold, combining_voice_mark_fold, iteration_fold, repetition_contraction
from yokome.util.concurrency import MemoryLock
from yokome.util.progress import ProgressBar


def cycle_colors():
    foreground = 1
    background = 0
    while True:
        yield '\033[3%d;4%dm' % (foreground, background)
        foreground += (3 if foreground == 6 and background == 7 else
                       2 if foreground + 1 == background
                       else 1)
        background = (background + foreground // 8) % 8
        foreground %= 8


COLOR_CYCLE = cycle_colors()


async def store_sentence(conn, f, i, symbol_stream, lemmas, graphics, phonetics, graphic_cs, phonetic_cs, color):
    symbol_stream = tuple(fullwidth_fold(ascii_fold(iteration_fold(
        repetition_contraction(combining_voice_mark_fold(symbol_stream))))))
    has_content = is_content_sentence(symbol_stream)
    if has_content:
        tokens = [candidates async for candidates in tokenize_stream_async(symbol_stream)]
        # first_token = True
        for candidates in tokens:
            contribution = Fraction(1, len(candidates))
            for candidate in candidates:
                lemmas[(candidate['lemma']['graphic'], candidate['lemma']['phonetic'])] += contribution
                graphics[candidate['lemma']['graphic']] += contribution
                phonetics[candidate['lemma']['phonetic']] += contribution
                for c in candidate['lemma']['graphic']:
                    graphic_cs[c] += contribution
                for c in candidate['lemma']['phonetic']:
                    phonetic_cs[c] += contribution
            # total_tokens += 1
            # if first_token:
            #     print('%4d: %s' % (i, color), end='')
            #     first_token = False
            # print(candidates[0]['surface_form']['graphic'], end='')
        has_content = len(tokens) > 0
        if has_content:
            conn.cursor().execute('INSERT INTO sentences VALUES ("jpn", ?, ?, ?)',
                                  (f, i, json.dumps(tokens)))
        # print('\033[0m')
    if not has_content:
        conn.cursor().execute('INSERT INTO sentences VALUES ("jpn", ?, ?, ?)',
                              (f, i, json.dumps(to_text(expand(symbol_stream)))))
    # As all tokens of a sentence are provided in a blocking fashion, only this
    # sentence was inserted into the database and we can commit
    conn.commit()


def next_n(generator, n):
    output = ()
    try:
        for _ in range(n):
            output += (next(generator),)
    except StopIteration:
        pass
    return output


BATCH_SIZE = 64


async def store_file(conn, f, lemmas, graphics, phonetics, graphic_cs, phonetic_cs, progress):
    ok = validate_file(f)
    if not ok:
        progress.print_next((f, ok))
        return
    async with MemoryLock(4, BATCH_SIZE * 2 ** 20):
        
        color = next(COLOR_CYCLE)

        progress.print_current((f, ok))
        sentences = enumerate(strip(segmenter(chasen_loader(f), True)), start=1)
        while True:
            # Prefetch ``BATCH_SIZE`` sentences
            batch = next_n(sentences, BATCH_SIZE)
            await asyncio.gather(*(asyncio.ensure_future(store_sentence(conn, f, i, sentence, lemmas, graphics, phonetics, graphic_cs, phonetic_cs, color)) for i, sentence in batch))
            if len(batch) < BATCH_SIZE:
                break
        progress.print_next(None)



async def store_corpus(conn, files, lemmas, graphics, phonetics, graphic_cs, phonetic_cs):
    progress = ProgressBar(len(files),
                           prefix=lambda i, element: '        |' if element is None else '        \033[%s\033[0m %s\n        |' % ('32mACCEPT' if element[1] else '31mREJECT', element[0]),
                           suffix=lambda i, element: '| ')
    progress.print_current(None)
    tasks = [asyncio.ensure_future(store_file(conn, f, lemmas, graphics, phonetics, graphic_cs, phonetic_cs, progress)) for f in files]
    await asyncio.gather(*tasks)


if __name__ == '__main__':
    start = time.time()
    database_file = _PROJECT_ROOT + '/data/processed/data.db'
    if os.path.exists(database_file):
        if os.path.isfile(database_file):
            print('Rebuilding JPN part of sentence database...')
        else:
            raise ValueError('%r is not a file' % (database_file,))
    else:
        print('Creating sentence database...')
        os.makedirs(os.path.dirname(database_file), exist_ok=True)
    lemmas = defaultdict(lambda: Fraction(0, 1))
    graphics = defaultdict(lambda: Fraction(0, 1))
    phonetics = defaultdict(lambda: Fraction(0, 1))
    graphic_cs = defaultdict(lambda: Fraction(0, 1))
    phonetic_cs = defaultdict(lambda: Fraction(0, 1))
    # total_tokens = 0
    with sql.connect(database_file) as conn:
        c = conn.cursor()
        c.execute('PRAGMA encoding="UTF-8"')
        c.execute('PRAGMA foreign_keys=ON')
        print('    Preparing sentence table...')
        c.execute('''CREATE TABLE IF NOT EXISTS sentences (
            language TEXT NOT NULL,
            file TEXT NOT NULL,
            sequence_id INTEGER NOT NULL,
            sentence TEXT NOT NULL,
            PRIMARY KEY (language, file, sequence_id))''')
        c.execute('DELETE FROM sentences WHERE language = "jpn"')
        c.execute('''CREATE TABLE IF NOT EXISTS statistics (
            language TEXT NOT NULL,
            form TEXT NOT NULL,
            graphic TEXT,
            phonetic TEXT,
            count REAL NOT NULL,
            cumulative_count REAL NOT NULL,
            rank INTEGER NOT NULL,
            PRIMARY KEY (language, form, rank))''')
        c.execute('''CREATE UNIQUE INDEX IF NOT EXISTS statistics_lemma_idx
            ON statistics (language, form, graphic, phonetic)''')
        c.execute('''CREATE INDEX IF NOT EXISTS statistics_phonetic_idx
            ON statistics (language, form, phonetic)''')
        c.execute('''CREATE INDEX IF NOT EXISTS statistics_count_idx
            ON statistics (language, form, count)''')
        c.execute('''CREATE INDEX IF NOT EXISTS statistics_cumulative_count_idx
            ON statistics (language, form, cumulative_count)''')
        c.execute('DELETE FROM statistics WHERE language = "jpn"')
        conn.commit()
        print('    Analyzing documents:')
        asyncio.get_event_loop().run_until_complete(store_corpus(conn, dev_files(), lemmas, graphics, phonetics, graphic_cs, phonetic_cs))
        print('    Saving statistics...')
        cumulative_count = Fraction(0, 1)
        for rank, (lemma, count) in enumerate(sorted(lemmas.items(), key=lambda x: x[1], reverse=True), start=1):
            cumulative_count += count
            c.execute('INSERT INTO statistics VALUES ("jpn", "lemma", ?, ?, ?, ?, ?)',
                      (lemma[0], lemma[1], float(count), float(cumulative_count), rank))
        cumulative_count = Fraction(0, 1)
        for rank, (graphic, count) in enumerate(sorted(graphics.items(), key=lambda x: x[1], reverse=True), start=1):
            cumulative_count += count
            c.execute('INSERT INTO statistics VALUES ("jpn", "lemma:graphic", ?, NULL, ?, ?, ?)',
                      (graphic, float(count), float(cumulative_count), rank))
        cumulative_count = Fraction(0, 1)
        for rank, (phonetic, count) in enumerate(sorted(phonetics.items(), key=lambda x: x[1], reverse=True), start=1):
            cumulative_count += count
            c.execute('INSERT INTO statistics VALUES ("jpn", "lemma:phonetic", NULL, ?, ?, ?, ?)',
                      (phonetic, float(count), float(cumulative_count), rank))
        cumulative_count = Fraction(0, 1)
        for rank, (graphic_c, count) in enumerate(sorted(graphic_cs.items(), key=lambda x: x[1], reverse=True), start=1):
            cumulative_count += count
            c.execute('INSERT INTO statistics VALUES ("jpn", "lemma:graphic:character", ?, NULL, ?, ?, ?)',
                      (graphic_c, float(count), float(cumulative_count), rank))
        cumulative_count = Fraction(0, 1)
        for rank, (phonetic_c, count) in enumerate(sorted(phonetic_cs.items(), key=lambda x: x[1], reverse=True), start=1):
            cumulative_count += count
            c.execute('INSERT INTO statistics VALUES ("jpn", "lemma:phonetic:character", NULL, ?, ?, ?, ?)',
                      (phonetic_c, float(count), float(cumulative_count), rank))
        # print('    Total tokens: %d' % (total_tokens,))
        conn.commit()
        print('    Optimizing database...')
        c.execute('REINDEX')
        c.execute('ANALYZE')
        conn.commit()
        c.execute('VACUUM')
        conn.commit()
    print('    \033[1;32mDONE\033[0m (%ds)' % (time.time() - start,))
