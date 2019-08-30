.. Yokome documentation master file


.. role:: bash(code)
   :language: bash


Yokome
******

.. toctree::
   :hidden:

   python/yokome
   webextension

Yokome is a web-based reading support system.  Hovering over a webpage you are
currently viewing, it looks up the words you read, giving you an idea which of
the multiple word senses is most likely in the given context.

Right now, Yokome is restricted to Japanese text, but it was designed with
multilinguality in mind.

This system was developed as a master project in the context of Web Interfaces
for Language Processing Systems in summer semester 2019 at the University of
Hamburg.  It consists of two parts: A backend written in python and a frontend
packaged as a Firefox WebExtension.

Learn how to use Yokome below or read the developer documentation for the
:doc:`backend <python/yokome>` or the :doc:`WebExtension <webextension>`.


Requirements
============

The startup procedure below has been tested on Ubuntu 18.04.3 LTS.  The
explanations assume that the following programs are available on your system:

- git
- docker
- tar
- zip
- bzip2

Yokome will most certainly not work on Windows < 6.0 (Vista).


How to start Yokome
=====================

From a terminal, download the project files:

.. code-block:: bash

   git clone https://github.com/julianbetz/yokome.git

Start the background service:

.. code-block:: bash

   cd yokome
   docker-compose up

This will start the service on port 5003 on localhost.  The plugin will expect
that the service runs on this port.

The web extension is known to work with Firefox Developer Edition 70.0b1
(64-bit).  You can get this version from
`<https://download-installer.cdn.mozilla.net/pub/devedition/releases/70.0b1/>`_.
Extract the archive, open the resulting directory and start Firefox.

The extension is unsigned, so you have to give Firefox permission to run it.
There are two ways to do so:

- Install the extension persistently:

  - Go to `<about:config>`_.  A warning will appear.
  - Click ``I accept the risk!`` and set the variable
    ``xpinstall.signatures.required`` to ``false``.
  - Package the web extension from source: From the root of the project
    directory, run :bash:`make plugin`.
  - Locate the file ``bin/yokome.xpi`` and drag and drop it into Firefox's
    address bar.
  - Yokome requires access to the docker service and to the browser tabs.  In
    the popup that appears, click ``Add`` to grant those permissions.
  - In the next popup, you can choose whether you want Yokome to also run in
    private windows.

- Alternatively, you can activate the extension for the current session only:

  - Go to `<about:debugging#/runtime/this-firefox>`_.
  - Click ``Load Temporary Add-on...`` and locate the file
    ``yokome/deployment/plugin/manifest.json`` (relative to the git repository
    you downloaded).


How to Use Yokome
=================

Open a page of your choice with target-language content.  Yokome works on both
HTTP and HTTPS web pages.

.. figure:: .static/address_bar.png
   :scale: 50%
   :alt: symbol in address bar
   :align: center

In the address bar, to its right side, you will find a symobol that looks like a
circle.  Click that symbol to activate Yokome on the current page.  After you
activated Yokome, a box will start to hover over the left lower corner of the
page.  This is where dictionary results will be displayed.  The box is
transparent as long as you do not interact with it.  This is so that you can see
what is displayed behind it on the web page.  To see what is shown on the box,
move the cursor over it.

.. figure:: .static/tabs.png
   :scale: 50%
   :alt: multi-colored tabs
   :align: center

To look up a word, simply hover your mouse over it.  After some time, the
results appear in the box.  If there are multiple dictionary entries that apply
to the word you looked up, they show as tabs at the top of the box.  The first
one is selected and its entries are shown below.  Click on any of the other tabs
to show their information.

The tabs are colored based on how likely their entries represent the word in the
text.  The more intense the yellow coloring, the more likely the entry applies.

.. figure:: .static/connotations.png
   :scale: 50%
   :alt: multi-colored connotations
   :align: center

In the space below the tabs, the different connotations of the selected entry
appear.  Again, the more intense the yellow coloring gets, the more likely is
this connotation the one meant in the text.

In the ``About`` tab you can find more information on Yokome.

If you feel that Yokome disturbs your interaction with the page, you can move it
to any of the other corners by clicking on one of the triangles around the box.

If you want to deactivate Yokome on the current page, you can click the symbol
in the address bar again.


About the name
==============

From the Japanese dictionary JMdict:

- | **横目【よこめ】** (*yokome*):
  | **noun:** sidelong glance

Yokome tries to be as non-invasive as possible by reacting on mere mouse
hovering, leaving the original text as-is and hovering above the page in a
corner of your choice, so as to not obstruct your reading.

Instead of pulling out a physical dictionary, or doing the highlight-copy-paste
combo, it allows you to find the meaning of a word merely by resting the mouse
pointer over the word you are interested in.

Yokome's goal is to make dictionary lookups as simple as possible, so that
finding a word requires only a sidelong glance.


Licensing
=========

Yokome is licensed under the `Apache License, Version 2.0
<http://www.apache.org/licenses/LICENSE-2.0>`_.

The following data is required for the Japanese version to work:

- `JMdict <http://www.edrdg.org/jmdict/j_jmdict.html>`_

  - Published by the `Electronic Dictionary Research and Development Group
    <http://www.edrdg.org/>`_ under the `Creative Commons Attribution-ShareAlike
    Licence (V3.0) <http://www.edrdg.org/edrdg/licence.html>`_
  - A copy of the 2019-05-15 version can be found at
    `<https://github.com/julianbetz/yokome-jpn-dictionary.git>`_.

- The JEITA Public Morphologically Tagged Corpus (in ChaSen format)

  - Created and distributed by `Masato Hagiwara <http://lilyx.net/>`_
  - The data originates from `Aozora Bunko <http://www.aozora.gr.jp/>`_ and
    `Project Sugita Genpaku <http://www.genpaku.org/>`_
  - A copy can be found at
    `<https://github.com/julianbetz/yokome-jpn-corpus.git>`_, containing
    copyright information for the individual files.

The required data can be downloaded using the command :bash:`make data`
(requires git, tar, bzip2 and gzip).

Furthermore, the Japanese version makes use of the Japanese morphological
analyzer `JUMAN++ <http://nlp.ist.i.kyoto-u.ac.jp/EN/index.php?JUMAN%2B%2B>`_
(Morita, Kawahara, Kurohashi 2015).  JUMAN++ is distributed under the `Apache
License, Version 2.0 <http://www.apache.org/licenses/LICENSE-2.0>`_.  You can
obtain it via download by issuing :bash:`make lib/jumanpp-1.02.tar.xz`.
