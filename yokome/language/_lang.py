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


class Language:
    """Resources of a specific language.
    
    Stores information about the language and provides methods for text analysis
    that are tailored to that language.
    
    """

    _LANGUAGES = dict()


    def __init__(self, code, name, *, loader, tokenizer, extractor, parallel_extractor):
        if code in Language._LANGUAGES:
            raise ValueError('Language code has to be unique')
        self._CODE = code
        self._NAME = name
        self._LOADER = loader
        self._TOKENIZER = tokenizer
        self._EXTRACTOR = extractor
        self._PARALLEL_EXTRACTOR = parallel_extractor
        Language._LANGUAGES[code] = self


    @staticmethod
    def by_code(code):
        """Look up a language by its unique identifier."""
        return Language._LANGUAGES[code]
        

    @property
    def code(self):
        """The unique identifier of this language.

        This is usually the ISO 639-3 language code of this language.

        """
        return self._CODE


    @property
    def load(self):
        """Function to load corpus sentences in this language.

        The order of sentences is randomized (independently of the number of
        samples requested and consistently in between calls requesting the same
        number of samples).

        Does not necessarily load the sentences themselves, but may provide IDs
        if :py:meth:`tokenize`, :py:meth:`extract` and
        :py:meth:`extract_parallel` can handle this format.

        :param int n_samples: The number of sample sentences to load. If
            ``None``, load all samples.

        :return: A tuple of sentences or sentence IDs.

        """
        return self._LOADER


    @property
    def tokenize(self):
        """Function to tokenize a sentence in this language.

        :param sentence: A sentence or sentence ID.

        :return: A tuple of tuples of tokens.  A token is represented as a
            dictionary of the following form:
            
            .. code-block:: python
               
               {
                 'surface_form': {'graphic': ..., 'phonetic': ...},
                 'base_form': {'graphic': ..., 'phonetic': ...},
                 'lemma': {'graphic': ..., 'phonetic': ...},
                 'pos': <list of POS tags as strings>,
                 'inflection': <list of POS/inflection tags>
               }
        
            "Surface form" refers to the graphic variant used in an original
            document and its pronunciation.  "Base form" refers to a lemmatized
            version of the surface form.  "Lemma" a normalized version of the
            base form. (In Japanese, for example, there is a single lemma for
            multiple graphical variants of the base form which mean the same
            thing.)

            The POS and inflection lists are meant to be read by a
            :class:`..features.tree.TemplateTree`.

        """
        return self._TOKENIZER


    @property
    def extract(self):
        """Function to turn an iterable of tokens into language model input.
        
        Differs from :meth:`extract_parallel` only for character-level extracts.
        
        :param tokens: An iterable of tokens (see :meth:`tokenize` for the token
            representation).

        :return: An iterable of token identifiers that is understood by the
            language model.

        """
        return self._EXTRACTOR


    @property
    def extract_parallel(self):
        """Function to turn an iterable of tokens into language model input.

        Differs from :meth:`extract` only for character-level extracts.
        
        :param tokens: An iterable of tokens (see :meth:`tokenize` for the token
            representation).

        :return: An iterable of token identifiers that are understood by the
            language model.

        """
        return self._PARALLEL_EXTRACTOR


    def __repr__(self):
        return '<%s %s>' % (type(self).__name__, self._CODE)


    def __str__(self):
        return self._NAME
