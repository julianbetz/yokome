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

RUN apt-get update && apt-get install -y --no-install-recommends curl xz-utils gcc g++ libboost-all-dev make # libpq-dev

RUN mkdir lib && curl -o lib/jumanpp-1.02.tar.xz 'http://lotus.kuee.kyoto-u.ac.jp/nl-resource/jumanpp/jumanpp-1.02.tar.xz'
RUN cd lib && tar -xJf jumanpp-1.02.tar.xz && rm jumanpp-1.02.tar.xz \
        && cd jumanpp-1.02 && ./configure && make && make install

COPY requirements/py3.txt /init/requirements.txt
RUN pip install -r /init/requirements.txt && pip uninstall -y tensorflow-gpu \
        && pip install tensorflow==1.13.1

COPY data/processed/data.db data/processed/data.db
COPY data/crafted/juman_pos_translator.json data/crafted/juman_pos_translator.json
COPY data/crafted/jpn_pos_restrictions.json data/crafted/jpn_pos_restrictions.json
COPY hyperparameter_optimization/xvld/best_hyperparams.json hyperparameter_optimization/xvld/best_hyperparams.json
COPY models/trn models/trn
COPY yokome yokome
COPY README.rst README.rst
COPY LICENSE LICENSE

EXPOSE 5003
CMD ["python", "yokome/deployment/server.py", "--no-debug", "--insecure"]
