#!/bin/bash
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


until curl --silent -X GET "http://localhost:9200/_cat/health?h=status" | grep -q "^\(green\|yellow\)\$"; do
    echo 'Waiting for Elasticsearch...'
    sleep 1
done
echo 'Elasticsearch running'
curl -X PUT -H 'content-type: application/json' "http://localhost:9200/_snapshot/inverse_dictionary" -d '{"type": "fs", "settings": {"location": "/init/inverse_dictionary", "compress": true, "readonly": true}}'
curl -X POST "http://localhost:9200/_snapshot/inverse_dictionary/snapshot/_restore?wait_for_completion=true"
rm -r /init/inverse_dictionary
