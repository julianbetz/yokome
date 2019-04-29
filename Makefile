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

.PHONY: help
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

## Make virtual environments meet requirements
virtualenvs: virtualenvs/py3/bin/activate
	@touch virtualenvs
