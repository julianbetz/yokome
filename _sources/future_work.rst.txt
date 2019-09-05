Where to go from here
=====================

Yokome can be extended and improved in a multitude of ways.  Some ideas:

- Extend to more languages
- Improve the language model
- Try out a character-based language model (might work well with Chinese and
  Japanese, since characters are semantically very rich in those languages)
- Provide personalized example sentences based on a user language proficiency
  estimation
- Provide images alongside the glosses
- Improve support for sentences spanning multiple HTML elements as well as
  rotated text
- Performance considerations:

  - Block off stopwords
  - Denormalize the dictionary database
  - Make better use of underlying database optimization techniques
    (espc. caching)
  - Precompute tokenized sentences / disambiguation results
    
    - Based on recency (starting from the top of the page)
    - Based on word frequencies in the corpus
    - Based on the estimated proficiency of the learner, expressed as a
      word-frequency range
    - Based on structural elements (headings, links), text size, color, ...

  - Improve mouse pointer localization using a binary search on elements
  - Trade disambiguation accuracy for faster processing: Use windowed inputs to
    the language model instead of a recurrent neural network

- User interface:

  - Add loading indicators
  - Provide better data on entries

    - All headwords
    - More user-friendly presentation of POS tags
    - Restrictions and notes for glosses

  - Make the Yokome infobox's style independent from the webpage it is displayed
    on
