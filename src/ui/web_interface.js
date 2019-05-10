// -*- coding: utf-8 -*-

/**
 * Copyright 2019 Julian Betz
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 * 
 *      http://www.apache.org/licenses/LICENSE-2.0
 * 
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
 * WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */


/**
 * Mark all text on the web page.
 */
(function () {
    var nodeFilter = {
        acceptNode: function(node) {
            var global = (function () {return this;}());
            if (node.nodeType === global.Node.ELEMENT_NODE) {
                // Filter out script, style and hidden elements
                if (node.tagName === 'SCRIPT'
                    || node.tagName === 'STYLE'
                    || node.style.display === 'none') {
                    return global.NodeFilter.FILTER_REJECT;
                }
                // Consider text nodes contained in all other elements
                return global.NodeFilter.FILTER_SKIP;
            }
            // Filter out whitespace-only text nodes
            if (node.nodeValue.trim() === '') {
                return global.NodeFilter.FILTER_REJECT;
            }
            // Accept all other text nodes
            return global.NodeFilter.FILTER_ACCEPT;
        }
    };
    
    function processElementsAndText(nodeFilter, callback) {
        var global = (function () {return this;}()),
            // Iterator for text elements only
            treeWalker = global.document.createTreeWalker(
                global.document.body,
                global.NodeFilter.SHOW_ELEMENT | global.NodeFilter.SHOW_TEXT,
                nodeFilter,
                false),
            nodes = [],
            node = treeWalker.nextNode(),
            i;
        // Store all text nodes in array, as a TreeWalker does not support deletion
        // during iteration
        while (node) {
            nodes.push(node);
            node = treeWalker.nextNode();
        }
        // Process text nodes
        i = nodes.length;
        while (i--) {
            callback(nodes[i]);
        }
        global.console.log(nodes.length);
    }

    function replace(node) {
        var global = (function () {return this;}()),
            text = node.nodeValue,
            head = text.match(/^\s*/),
            tail = text.match(/\s*$/),
            tokens = text.trim().split(/ +/g),
            i,
            max = tokens.length,
            replacement;
        // Insert leading space
        replacement = global.document.createTextNode(head[0]);
        node.parentNode.insertBefore(replacement, node);
        for (i = 0; i < max; i++) {
            // Insert token
            replacement = global.document.createElement('span');
            replacement.appendChild(global.document.createTextNode(tokens[i]));
            replacement.style.backgroundColor = 'yellow';
            node.parentNode.insertBefore(replacement, node);
            if (i + 1 < max) {
                // Insert whitespace
                replacement = global.document.createTextNode(' ');
                node.parentNode.insertBefore(replacement, node);
            }
        }
        // Insert trailing space
        replacement = global.document.createTextNode(tail[0]);
        node.parentNode.insertBefore(replacement, node);
        // Remove original text
        node.parentNode.removeChild(node);
        global.console.log(tokens);
    }
    
    processElementsAndText(nodeFilter, replace);
}());
