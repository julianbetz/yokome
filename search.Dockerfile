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


FROM docker.elastic.co/elasticsearch/elasticsearch:6.5.4

RUN echo 'path.repo: ["/import"]' >> /usr/share/elasticsearch/config/elasticsearch.yml
COPY yokome/deployment/start.sh /init/start.sh
COPY data/processed/inverse_dictionary /import
RUN chown -R elasticsearch:elasticsearch /init
RUN su elasticsearch -c "elasticsearch -p /init/epid" & /bin/bash /init/start.sh; kill $(cat /init/epid) && tail --pid="$(cat /init/epid)" -f /dev/null

COPY README.rst /init/README.rst
COPY LICENSE /init/LICENSE
