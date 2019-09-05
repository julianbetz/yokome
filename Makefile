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

### Main control of the project.  Determines the computational graph that
### controls how individual pieces of data depend on each other.  Allows
### automatic recomputation of interim/processed data when the respective base
### data changed.
# ==============================================================================


.PHONY: help build yokome.app yokome.search clean
.DEFAULT_GOAL := help


# Self-documentation
# ------------------------------------------------------------------------------

# Prints help messages.
# 
# Document-level documentation blocks are indicated by three hash characters at
# the beginning of lines.  Target documentation strings are indicated by two
# hash characters at the beginning of lines and must comprise only a single line
# right before the target to be documented.  They should be no longer than 60
# characters; the targets themselves should be no longer than 19 characters.
# 
# A document-level documentation block at the end of the file results in no
# vertical spacing between this block and the command list.

## Print this message and exit
help:
	@sed -e '/^###\($$\|[^#]\)/,/^$$\|^[^#]\|^#[^#]\|^##[^#]/!d' $(MAKEFILE_LIST) | sed 's/^\($$\|[^#].*$$\|#[^#].*$$\|##[^#].*$$\)//' | sed 's/^### *//' | sed 's/  / /'
	@grep -E '^##[^#]' -A 1 $(MAKEFILE_LIST) | sed 's/^\([^ #][^ ]*\):\($$\| .*$$\)/\1/' | awk 'BEGIN {RS = "\n--\n"; FS = "\n"}; {sub(/^## */, "", $$1); printf "\033[32m%-19s\033[0m %s\n", $$2, $$1}'


# Virtualenvs
# ------------------------------------------------------------------------------

requirements/py3.txt:
	@touch requirements/py3.txt

virtualenvs/py3:
	@virtualenv virtualenvs/py3 --python=python3
	@touch virtualenvs/py3/bin/activate
	@sleep 1s
	@touch virtualenvs/py3

virtualenvs/py3/bin/activate: virtualenvs/py3 requirements/py3.txt
	@. virtualenvs/py3/bin/activate && pip install -r requirements/py3.txt; deactivate
	@touch virtualenvs/py3/bin/activate

## Make virtual environments meet their requirements
virtualenvs: virtualenvs/py3/bin/activate
	@touch virtualenvs


# Libraries
# ------------------------------------------------------------------------------

# Require 6.5.4 to be able to use it together with current Wikipedia dumps
lib/elasticsearch:
	@curl -L -o lib/elasticsearch-6.5.4.tar.gz 'https://artifacts.elastic.co/downloads/elasticsearch/elasticsearch-6.5.4.tar.gz'
	@cd lib && tar -xzf elasticsearch-6.5.4.tar.gz && rm elasticsearch-6.5.4.tar.gz
	@mv lib/elasticsearch-6.5.4 lib/elasticsearch

lib/jumanpp-1.02.tar.xz:
	@curl -o lib/jumanpp-1.02.tar.xz 'http://lotus.kuee.kyoto-u.ac.jp/nl-resource/jumanpp/jumanpp-1.02.tar.xz'
# 	@cd lib && tar -xJf jumanpp-1.02.tar.xz && rm jumanpp-1.02.tar.xz
# 	@cd lib/jumanpp-1.02 && ./configure && make && sudo make install

## Download necessary files from other projects
lib: lib/elasticsearch lib/jumanpp-1.02.tar.xz


# Data
# ------------------------------------------------------------------------------

data/raw/yokome-jpn-dictionary/JMdict.xml:
	@rm -rf data/raw/yokome-jpn-dictionary # ; rm data/raw/.JMdict.xml.make; :
	@cd data/raw && git clone "https://github.com/julianbetz/yokome-jpn-dictionary.git"
	@cd data/raw/yokome-jpn-dictionary && $(MAKE)

data/raw/yokome-jpn-corpus:
	@rm -rf data/raw/.yokome-jpn-corpus.make
	@cd data/raw && git clone "https://github.com/julianbetz/yokome-jpn-corpus.git" .yokome-jpn-corpus.make
	@cd data/raw/.yokome-jpn-corpus.make && $(MAKE)
	@mv data/raw/.yokome-jpn-corpus.make data/raw/yokome-jpn-corpus

## Download all raw data
data: data/raw/yokome-jpn-dictionary/JMdict.xml data/raw/yokome-jpn-corpus


# Data loading
# ------------------------------------------------------------------------------

data/processed/data.db: data/processed/.jpn.flag
	@touch data/processed/data.db

data/processed/.jpn.flag: data
	@rm -f data/processed/data.db
	@. virtualenvs/py3/bin/activate && python yokome/data/jpn/dictionary_to_rdbms.py data/raw/yokome-jpn-dictionary/JMdict.xml
	@. virtualenvs/py3/bin/activate && python yokome/data/jpn/corpus_to_rdbms.py data/raw/yokome-jpn-corpus
	@touch data/processed/.jpn.flag


# Deployment
# ------------------------------------------------------------------------------

bin/yokome.xpi: $(wildcard webextension/**/*)
	@rm -f bin/yokome.xpi
	@cd webextension && zip -r -FS ../bin/yokome.xpi *

define DROP_SENTENCES
import sqlite3 as sql

with sql.connect('data/deployment/.data.db.make') as conn:
    c = conn.cursor()
    c.execute('DROP TABLE sentences')
    conn.commit()
    c.execute('VACUUM')
    conn.commit()
endef

export DROP_SENTENCES
data/deployment/data.db: data/processed/data.db
	@rm -f data/deployment/.data.db.make
	@cp data/processed/data.db data/deployment/.data.db.make
	@. virtualenvs/py3/bin/activate && python -c "$$DROP_SENTENCES"
	@cd data/deployment && mv .data.db.make data.db

yokome.app: data/deployment/data.db lib/jumanpp-1.02.tar.xz
	@docker build -t julianbetz/yokome.app -f app.Dockerfile .

yokome.search:
	@sudo sysctl -w vm.max_map_count=262144 && docker build --ulimit nproc=65536 --ulimit nofile=65536 -t julianbetz/yokome.search -f search.Dockerfile .

## Package the web extension and build all docker services
build: bin/yokome.xpi yokome.app yokome.search


# Clean
# ------------------------------------------------------------------------------

## Remove all temporary data
clean:
	@rm -rf lib/elasticsearch-6.5.4.tar.gz lib/elasticsearch-6.5.4
	@rm data/raw/.yokome-jpn-corpus.make
	@rm data/deployment/.data.db.make
