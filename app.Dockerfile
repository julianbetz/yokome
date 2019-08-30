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


FROM python:3.6-slim

WORKDIR /app

# Dependencies
COPY lib/jumanpp-1.02.tar.xz lib/jumanpp-1.02.tar.xz
COPY requirements/app.txt requirements.txt
RUN apt-get update && apt-get install -y --no-install-recommends xz-utils gcc g++ make libboost-all-dev \
        && cd lib && tar -xJf jumanpp-1.02.tar.xz \
        && cd jumanpp-1.02 && ./configure && make && make install \
        && cd .. && rm -r jumanpp-1.02 \
        && pip install -r /app/requirements.txt \
        && apt-get remove -y xz-utils gcc g++ make && apt-get autoremove -y

# Data
COPY data/deployment/data.db data/processed/data.db

# POS tag meta data
COPY data/crafted/juman_pos_translator.json data/crafted/jpn_pos_restrictions.json data/crafted/

# Model
COPY hyperparameter_optimization/xvld/best_hyperparams.json hyperparameter_optimization/xvld/best_hyperparams.json
COPY models/trn/best_model models/trn/best_model
COPY models/trn/meta.json models/trn/encoder.pickle models/trn/

# Project source
COPY yokome yokome
COPY README.rst LICENSE ./

EXPOSE 5003
CMD ["python", "yokome/deployment/server.py", "--debug", "--insecure"]
