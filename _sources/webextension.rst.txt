Yokome Firefox WebExtension (JavaScript)
========================================

.. js:function:: background.initializePageAction(tab)

   Initialize/reset page action to activate Yokome.

   :param tab: The tab on which to initialize Yokome.


.. js:function:: background.toggleYokome(tab)

   Activate or deactivate Yokome, depending on the current state.

   :param tab: The tab on which to toggle Yokome.


.. js:function:: content..anyContains(rectangles, point)

   Determine whether any rectangle in ``rectangles`` contains ``point``.

   :param rectangles: A sequence of rectangles, each expressed by its four
       attributes ``left``, ``right``, ``top`` and ``bottom``.

   :param point: A pair of two values, the first in horizontal direction and the
       second in vertical direction.

   :returns: ``true`` if any rectangle contains the point, ``false`` otherwise.


.. js:function:: content..contains(rectangle, point)

   Determine whether ``rectangle`` contains ``point``.

   :param rectangle: A rectangle, expressed by its four attributes ``left``,
       ``right``, ``top`` and ``bottom``.

   :param point: A pair of two values, the first in horizontal direction and the
       second in vertical direction.

   :returns: ``true`` if the rectangle contains the point, ``false`` otherwise.


.. js:function:: content..createArrowNode(parent, top, left)

   Create an arrow node on the info box.

   Arrow nodes allow users to move the info box into a corner of their choice.

   :param parent: The parent node for which to create an arrow node as a child.

   :param top: Whether the arrow points to the top.

   :param left: Whether the arrow points to the left.


.. js:function:: content..createInfoBox()

   Create the info box (i.e. the main Yokome interface); place it on the page.


.. js:function:: content..disambiguateTargetToken(event)

   Initiate disambiguation on a token.

   Find the token (a text node) under the mouse pointer and start a timeout for
   disambiguation.

   :param event: The event that determines which token to disambiguate.


.. js:function:: content..getCursorPosition(event)

   Get the mouse position described by the event.

   :param event: A mouse event.

   :returns: A pair of two values, the first in horizontal direction and the
       second in vertical direction, describing the x and y coordinates of the
       mouse position during the event.


.. js:function:: content..getHighestZIndex()

   Determine the highest z-dimension index of any element on the page.

   :returns: The highest z-index.


.. js:function:: content..getIndex(node)

   Get the index of ``node`` (the number of siblings that precede it).

   :param node: The node to determine the index for.

   :returns: The number of siblings that precede ``node``, or ``-1`` if ``node
       === null``.


.. js:function:: content..initialize(nodeFilter)

   Initialize the page for tokenization and disambiguation tasks.

   Arm every relevant element with ``onmouseenter`` events.

   :param nodeFilter: A node filter to detect relevant elements.


.. js:function:: content..initiateTabSwitching(event)

   Display the content of a tab that is a parent element of the target of
   ``event`` or that target itself.

   :param event: An ``onclick`` event that targets a tab of the info box or a
       child thereof.


.. js:function:: content..maybeRefreshTabs(node)

   Disambiguate the text in ``node`` based on its surrounding text if the
   disambiguation timeout was last started on this node.

   Request disambiguation at the server.

   Intended to be called by a timeout event.

   :param event: The original event that lauched the timeout.

   :param node: A text node, inserted by a tokenization process.


.. js:function:: content..maybeTokenize(event, node)

   Tokenize the text in ``node`` if the tokenization timeout was last started on
   this node.

   Request tokenization at the server.

   Intended to be called by a timeout event.

   :param event: The original event that lauched the timeout.

   :param node: A text node.  A child node of ``event.target``.


.. js:function:: content..movebox(event)

   Move the box into the corner indicated by the arrow node that is the target
   of ``event``.

   :param event: An ``onlick`` event.


.. js:function:: content..post(url, data, node, callback, args)

   Make an HTTP POST request.

   :param url: The url to make the request to.

   :param data: The data to send.

   :param node: A node that is the first argument to ``callback``.

   :param callback: A function to be called after a successful response.
       ``callback`` is called with ``node``, the JSON-parsed response text, and
       ``args``.

   :param args: Additional arguments to be passed to ``callback``.


.. js:function:: content..refreshTabs(node, lexemes, args)

   Update the info box to reflect information on the disambiguate node ``node``.

   :param node: A text node, inserted by a tokenization process.

   :param lexemes: A response after word-sense disambiguation, a parsed JSON
       document.

   :param args: Not used.  For compatibility with :js:func:`post` only.


.. js:function:: content..removeInfoBox()

   Remove the info box (i.e. the main Yokome interface) from the page.


.. js:function:: content..resetDisambiguationTimeoutStart()

   Reset the timeout start time for disambiguation.

   There is one such time for each page.  This helps detecting which element
   triggered a disambiguation request last.


.. js:function:: content..resetTokenizerTimeoutStart()

   Reset the timeout start time for tokenization.

   There is one such time for each page.  This helps detecting which element
   triggered a tokenization request last.
   

.. js:function:: content..switchToTab(node)

   Display the content of the tab that is associated with ``node``.

   :param node: A tab of the info box.


.. js:function:: content..tokenize(node, response, args)

   Replace the text of ``node`` with the text received from the tokenizer.

   Initiate disambiguation on the part of the text that is in the area of the
   mouse event that launched the tokenization request.

   :param node: The text node whose text to replace.

   :param response: The response from the tokenizer, parsed JSON document.

   :param args: A list of the form ``[event, head, tail]``, where ``event`` is
       the original event that launched the tokenization action, and ``head``
       and ``tail`` are the leading and trailing whitespaces from the original
       text, respectively.
