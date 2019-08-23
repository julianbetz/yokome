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
 * Tokenize all text on the web page.
 */
(function () {
    var global = (function () {return this;}()),
        nodeFilter = {
            acceptNode: function(node) {
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
        },
        TRIES = 10,                  // Tries to locate resource via HTTP
        FONT_SIZE = 15,              // Of the info box (px)
        BOX_DISTANCE = 5,            // Info box to the edge of the window (px)
        ARROW_DISTANCE = 3,          // Arrows to the edges of the info box (px)
        COLORS = ['#000000', '#ffffff', '#a5a5a5', '#fcba12'],
        infoBox = global.document.createElement('div'),
        canvas = global.document.createElement('div'),
        tabs = global.document.createElement('div'),
        tabSet = global.document.createElement('div'),
        tabPanels = global.document.createElement('div'),
        node,
        i,
        HIGHEST_Z_INDEX,
        currentRectangles,
        TIMEOUT = 500,                  // (ms)
        currentTimeoutStart,
        tokenizerTimeoutStart,
        POS_SEPARATOR = '; ',
        GLOSS_SEPARATOR = ' ▪ ';

    function getCursorPosition(event) {
        return [event.clientX, event.clientY];
    }

    function getIndex(node) {
        var idx = -1;
        while (node !== null) {
            idx += 1;
            node = node.previousSibling;
        }
        return idx;
    }

    function getHighestZIndex() {
        var treeWalker = global.document.createTreeWalker(
            global.document.body,
            global.NodeFilter.SHOW_ELEMENT,
            null,
            false),
            node,
            current,
            max = 0;
        for (node = treeWalker.nextNode(); node; node = treeWalker.nextNode()) {
            current = global.Number(global.document.defaultView
                                    .getComputedStyle(node, null)
                                    .getPropertyValue('z-index'));
            max = current > max ? current : max;
        }
        return max;
    }

    // Fades in for factor > 1
    // Fades out for factor < 1
    function fade(element, factor, step) {
        // Asserts 0 < factor != 1 and element.style.opacity > 0
        var MIN = 0.5,
            opacity = element.style.opacity,
            interval = global.setInterval(function () {
                opacity *= factor;
                if (factor > 1 && opacity >= 1) {
                    global.clearInterval(interval);
                    element.style.opacity = 1;
                } else if (factor < 1 &&　opacity <= MIN) {
                    global.clearInterval(interval);
                    element.style.opacity = MIN;
                } else {
                    element.style.opacity = opacity;
                }
            }, step);
    }

    function fadeInAndOut(element, factor, step, wait) {
        // Asserts factor > 1.0
        var opacity = element.style.opacity,
            interval = global.setInterval(function () {
                opacity *= factor;
                if (opacity >= 1) {
                    global.clearInterval(interval);
                    element.style.opacity = 1;
                    global.setTimeout(function () {
                        fade(element, 1.0 / factor, step);
                    }, wait);
                } else {
                    element.style.opacity = opacity;
                }
            }, step);
    }

    function activateTabOf(node) {
        var i = tabSet.childNodes.length,
            sibling;
        while (i--) {
            sibling = tabSet.childNodes[i];
            // sibling.style.boxShadow = 'rgba(0,0,0,0.75) 0px 3px 10px -10px';
            // sibling.style.opacity = 0.7;
            sibling.style.border = '1px solid white';
        }
        i = tabPanels.childNodes.length;
        while (i--) {
            tabPanels.childNodes[i].style.display = 'none';
        }
        // node.style.boxShadow = 'rgba(0,0,0,0.75) 0px 6px 10px -10px';
        // node.style.opacity = 1.0;
        node.style.border = '1px solid black';
        tabPanels.childNodes[getIndex(node)].style.display = 'block';
    }        
    
    function activateTab(event) {
        var node = event.target;
        while (node.onclick !== activateTab) {
            node = node.parentElement;
        }
        activateTabOf(node);
    }

    function resetTabs(node, lexemes, head, tail) {
        var i, j, k, l, progressBar, score, intensity, // entries,
            subnode, subsubnode, subsubsubnode, ruby, reading, max_score;
        node.wilps_lexemes = lexemes;
        lexemes = lexemes.lexemes;
        console.log(lexemes);
        // TODO Rather use dojox.gfx.Surface to clear all objects
        while (tabSet.hasChildNodes()) {
            tabSet.removeChild(tabSet.lastChild);
        }
        while (tabPanels.hasChildNodes()) {
            tabPanels.removeChild(tabPanels.lastChild);
        }
        // entries = [[['noun; no-adj.', 'check ▪ plaid ▪ checkered', '', 0.8]], [['noun; suru verb', 'checking ▪ monitoring ▪ looking over', '荷物はチェックされました。', 0.6], ['noun', 'check (banking) ▪ cheque ▪ bill', '旅行する時はいつも現金ではなくチェックにしています。', 0.4]], [['noun', 'check (chess)', '', 0.2]]];
        for (i = 0; i < lexemes.length; i++) {
            // Create tab button
            node = global.document.createElement('div');
            subnode = global.document.createElement('span');
            ruby = global.document.createElement('ruby');
            ruby.appendChild(global.document.createTextNode(lexemes[i].headwords[0][0] === null ? lexemes[i].headwords[0][1] : lexemes[i].headwords[0][0]));
            reading = global.document.createElement('rt');
            reading.appendChild(global.document.createTextNode(lexemes[i].headwords[0][1]));
            ruby.appendChild(reading);
            subnode.appendChild(ruby);
            node.appendChild(subnode);
            node.style.flex = '1 1 auto';
            node.style.minWidth = '15%';
            node.style.margin = '1px';
            node.style.border = '1px solid transparent';
            node.style.borderRadius = '2px';
            node.style.padding = '4px';
            node.style.display = 'flex';
            node.style.alignItems = 'flex-end';
            score = lexemes[i].score / lexemes[0].score; // (lexemes.length - i) / lexemes.length;
            intensity = score < 0.5 ? (score + 0.5) : (score - 0.5);
            // node.style.color = 'hsl(43, ' + Math.round(100 * intensity) + '%, ' + Math.round(100 * (0.12 + 0.57 * intensity)) + '%)';
            // node.style.backgroundColor = 'hsl(43, ' + Math.round(100 * score) + '%, ' + Math.round(100 * (0.12 + 0.38 * score)) + '%)';
            node.style.color = COLORS[0];
            node.style.backgroundColor = 'hsl(43, 100%, ' + Math.round(100 * (0.95 - 0.45 * score)) + '%)';
            node.onclick = activateTab;
            tabSet.appendChild(node);
            // Create tab panel
            max_score = 0;
            for (j = 0; j < lexemes[i].roles.length; j++) {
                for (k = 0; k < lexemes[i].roles[j].connotations.length; k++) {
                    if (max_score < lexemes[i].roles[j].connotations[k].score) {
                        max_score = lexemes[i].roles[j].connotations[k].score;
                    }
                }
            }
            node = global.document.createElement('div');
            for (j = 0; j < lexemes[i].roles.length; j++) {
                subnode = global.document.createElement('div');
                // progressBar = global.document.createElement('progress');
                // progressBar.setAttribute('value', lexemes.length - i);
                // progressBar.setAttribute('max', lexemes.length + 1);
                // progressBar.style.height = '2px';
                // subnode.appendChild(progressBar);

                subsubnode = global.document.createElement('div');
                for (k = 0; k < lexemes[i].roles[j].poss.length; k++) {
                    subsubnode.appendChild(global.document.createTextNode(lexemes[i].roles[j].poss[k] + (k < lexemes[i].roles[j].poss.length - 1 ? POS_SEPARATOR : '')));
                }
                subsubnode.style.width = '100%';
                subnode.appendChild(subsubnode);

                for (k = 0; k < lexemes[i].roles[j].connotations.length; k++) {
                    subsubnode = global.document.createElement('div');
                    subsubnode.appendChild(global.document.createTextNode('[' + lexemes[i].roles[j].connotations[k].sense_id.toString() + '] '));
                    for (l = 0; l < lexemes[i].roles[j].connotations[k].glosses.length; l++) {
                        if (lexemes[i].roles[j].connotations[k].glosses[l][0] !== null) {
                            subsubsubnode = global.document.createElement('i');
                            subsubsubnode.appendChild(global.document.createTextNode(lexemes[i].roles[j].connotations[k].glosses[l][0]));
                            subsubnode.appendChild(subsubsubnode);
                        }
                        subsubnode.appendChild(global.document.createTextNode(lexemes[i].roles[j].connotations[k].glosses[l][1] + (l < lexemes[i].roles[j].connotations[k].glosses.length - 1 ? GLOSS_SEPARATOR : '')));
                    }
                    subsubnode.style.width = '100%';
                    score = lexemes[i].roles[j].connotations[k].score / max_score;
                    subsubnode.style.color = 'hsl(43, ' + Math.round(100 * score) + '%, ' + Math.round(50 * score) + '%)';
                    subnode.appendChild(subsubnode);

                    // subsubnode = global.document.createElement('div');
                    // subsubnode.appendChild(global.document.createTextNode(entries[i % 3][j][2]));
                    // subsubnode.style.width = '100%';
                    // subnode.appendChild(subsubnode);
                }

                node.appendChild(subnode);
            }
            tabPanels.appendChild(node);
        }
        // Create settings tab button
        node = global.document.createElement('div');
        node.appendChild(global.document.createTextNode('About'));
        node.style.flex = '1 1 auto';
        node.style.minWidth = '15%';
        node.style.margin = '1px';
        node.style.border = '1px solid transparent';
        node.style.borderRadius = '2px';
        node.style.padding = '4px';
        node.style.fontStyle = 'italic';
        node.style.display = 'flex';
        node.style.alignItems = 'flex-end';
        node.style.backgroundColor = COLORS[2];
        node.onclick = activateTab;
        tabSet.appendChild(node);
        // Create tab panel
        node = global.document.createElement('div');
        // node.appendChild(global.document.createTextNode(tabTexts[i]));
        // node.appendChild(global.document.createElement('br'));
        // node.appendChild(global.document.createTextNode('Difficulty: '));
        // progressBar = global.document.createElement('input');
        // progressBar.setAttribute('type', 'range');
        // progressBar.setAttribute('min', 0);
        // progressBar.setAttribute('max', 100);
        // progressBar.setAttribute('value', 20);
        // node.appendChild(progressBar);

        node.appendChild(global.document.createTextNode('Yokome'))
        
        tabPanels.appendChild(node);
        if (tabSet.childNodes.length > 0) { // TODO Remove, should always be the case if statistics are used
            activateTabOf(tabSet.childNodes[0]);
            // fadeInAndOut(infoBox, 1.05, 50, 3000);
        }
    }

    function contains(rectangle, point) {
        return (rectangle.left <= point[0] && rectangle.right >= point[0]
                && rectangle.top <= point[1] && rectangle.bottom >= point[1]);
    }

    function anyContains(rectangles, point) {
        var i = rectangles.length;
        while (i--) {
            if (contains(rectangles[i], point)) {
                return true;
            }
        }
        return false;
    }

    function resetTimeoutStart() {
        currentTimeoutStart = global.Date.now();
    }

    // TODO Remove head/tail syntax
    function httpGetAsyncWithData(url, text, node, callback, head, tail) {
        // TODO Do not retry on a HTTP 400 response
        var tries = TRIES,
            request = new global.XMLHttpRequest(),
            data = global.JSON.stringify(text);
        request.open('POST', url, true);
        request.onreadystatechange = function () {
            if (this.readyState === 4) {
                if (this.status === 200) {
                    callback(node, JSON.parse(this.responseText), head, tail);
                }
                else if (tries > 0) {
                    var new_request = new global.XMLHttpRequest();
                    new_request.open('POST', url, true);
                    new_request.onreadystatechange = this.onreadystatechange;
                    new_request.setRequestHeader('Content-Type', 'application/json');
                    tries -= 1;
                    new_request.send(data);
                }
            }
        };
        request.setRequestHeader('Content-Type', 'application/json');
        tries -= 1;
        request.send(data);
    }

    // function printLexemes(node, lexemes, head, tail) {
    //     console.log(lexemes);
    // }

    function resetTabsAfterTimeout(n) {
        if (global.Date.now() >= currentTimeoutStart + TIMEOUT) {
            if ('wilps_lemmas' in n) {
                console.log(n);
                if ('wilps_lexemes' in n) {
                    resetTabs(n, n.wilps_lexemes, null, null);
                } else {
                    httpGetAsyncWithData(
                        'http://localhost:5003/wsd/disambiguate?lang=jpn',
                        {'i': n.wilps_i, 'tokens': n.wilps_sentence},
                        n,
                        resetTabs,
                        null,
                        null);
                }
            }
        }
    }

    function showLemmas(event) {
        var nodes, node, charNode, i, j, max_j, rectangle, rectangles,
            found = false,
            cursor = getCursorPosition(event);
        // Only search for the word hovered over if the cursor left the old one
        if (currentRectangles === undefined
            || !anyContains(currentRectangles, cursor)) {
            // Search for the word hovered over
            nodes = event.target.childNodes;
            i = nodes.length;
            // TODO Use binary search instead for efficiency for long texts
            // FIXME Does not take into account that words can span multiple
            // lines. Therefore, some words "shadow" others.
            while (i--) {
                node = nodes[i];
                rectangles = [];
                if (node.nodeType === global.Node.TEXT_NODE) {
                    max_j = node.nodeValue.length;
                    for (j = 0; j < max_j; j++) {
                        // Create temporary span element to measure out text node
                        charNode = global.document.createElement('span');
                        charNode.appendChild(global.document.createTextNode(node.nodeValue[j]));
                        event.target.insertBefore(charNode, node);
                        // Measure out text node
                        rectangle = charNode.getBoundingClientRect();
                        rectangles.push(rectangle);
                        if (contains(rectangle, cursor)) {
                            found = true;
                        }
                    }
                    // Remove temporary span elements
                    while (j--) {
                        event.target.removeChild(node.previousSibling);
                    }
                    if (found) {
                        // Update rectangle information
                        currentRectangles = rectangles;
                        // Update info box
                        resetTimeoutStart();
                        global.setTimeout(function () {resetTabsAfterTimeout(node);}, TIMEOUT);
                        return;
                    }
                }
            }
        }
    }

    function splitNode(node, response, head, tail) {
        var i, j, k, max_i, max_j, max_k, l, sentence, replacement, span, ruby, rt;
        if (response.language === 'jpn') {
            max_i = response.sentences.length;
            // Insert leading space
            replacement = global.document.createTextNode(head);
            node.parentNode.insertBefore(replacement, node);
            for (i = 0; i < max_i; i++) {
                sentence = response.sentences[i];
                max_j = sentence.length;
                for (j = 0; j < max_j; j++) {
                    // Insert token
                    replacement = global.document.createTextNode(sentence[j][0].surface_form.graphic);
                    node.parentNode.insertBefore(replacement, node);
                    replacement.wilps_lemmas = [];
                    replacement.wilps_sentence = sentence;
                    replacement.wilps_i = j;
                    max_k = sentence[j].length;
                    for (k = 0; k < max_k; k++) {
                        l = sentence[j][k].lemma;
                        if (l !== null) {
                            span = global.document.createElement('span');
                            ruby = global.document.createElement('ruby');
                            ruby.appendChild(global.document.createTextNode(l.graphic));
                            rt = global.document.createElement('rt');
                            rt.appendChild(global.document.createTextNode(l.phonetic));
                            ruby.appendChild(rt);
                            span.appendChild(ruby);
                            replacement.wilps_lemmas.push(span);
                        }
                    }
                }
            }
            // Insert trailing space
            replacement = global.document.createTextNode(tail);
            node.parentNode.insertBefore(replacement, node);
            // Remove original text
            // node.parentNode.style.border = '1px dotted red';
            node.parentNode.onmousemove = showLemmas;
            node.parentNode.onmouseleave = resetTimeoutStart;
            node.parentNode.removeChild(node);
        }
    }

    function resetTokenizerTimeoutStart() {
        tokenizerTimeoutStart = global.Date.now();
    }

    function replace(node) {
        if (global.Date.now() >= tokenizerTimeoutStart + TIMEOUT) {
            console.log(node);
            node.parentNode.onmouseenter = resetTokenizerTimeoutStart;
            node.parentNode.onmouseleave = null;
            var text = node.nodeValue,
                head = text.match(/^\s*/),
                tail = text.match(/\s*$/);
            httpGetAsyncWithData('http://localhost:5003/tokenizer/tokenize?lang=jpn',
                                 text, node, splitNode, head, tail);
        }
    }

    function processElementsAndText(nodeFilter) {
        // Iterator for text elements only
        var treeWalker = global.document.createTreeWalker(
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
            node = nodes[i].parentNode;
            node.onmouseenter = function (event) {
                resetTokenizerTimeoutStart();
                global.setTimeout(
                    function () {
                        var j;
                        for (j = 0; j < event.target.childNodes.length; j++) {
                            if (event.target.childNodes[j].nodeType === global.Node.TEXT_NODE) {
                                replace(event.target.childNodes[j]);
                            }
                        }
                    },
                    TIMEOUT);
            };
            node.onmouseleave = resetTokenizerTimeoutStart;
        }
        // global.console.log(nodes.length);
    }

    function moveBox(event) {
        if (event.target.style.top) {
            infoBox.style.top = BOX_DISTANCE + 'px';
            infoBox.style.bottom = null;
        } else {
            infoBox.style.top = null;
            infoBox.style.bottom = BOX_DISTANCE + 'px';
        }
        if (event.target.style.left) {
            infoBox.style.left = BOX_DISTANCE + 'px';
            infoBox.style.right = null;
        } else {
            infoBox.style.left = null;
            infoBox.style.right = BOX_DISTANCE + 'px';
        }
    }

    function createArrowNode(parent, top, left) {
        var arrowNode = global.document.createElement('div');
        arrowNode.appendChild(
            global.document.createTextNode(
                top ? (left ? '◤' : '◥') : (left ? '◣' : '◢')));
        // XXX Check whether properties are overridden
        arrowNode.top = top;
        arrowNode.left = left;
        arrowNode.style.position = 'absolute';
        if (top) {
            arrowNode.style.top = ARROW_DISTANCE + 'px';
            arrowNode.style.bottom = null;
        } else {
            arrowNode.style.top = null;
            arrowNode.style.bottom = ARROW_DISTANCE + 'px';
        }
        if (left) {
            arrowNode.style.left = ARROW_DISTANCE + 'px';
            arrowNode.style.right = null;
        } else {
            arrowNode.style.left = null;
            arrowNode.style.right = ARROW_DISTANCE + 'px';
        }
        arrowNode.style.width = '1em';
        arrowNode.style.height = '1em';
        arrowNode.style.lineHeight = '0.96em';
        arrowNode.style.color = COLORS[2];
        arrowNode.onclick = moveBox;
        parent.appendChild(arrowNode);
    }

    HIGHEST_Z_INDEX = getHighestZIndex();

    infoBox.style.position = 'fixed';
    infoBox.style.bottom = BOX_DISTANCE + 'px';
    infoBox.style.left = BOX_DISTANCE + 'px';
    infoBox.style.width = '40%';
    infoBox.style.height = '30%';
    infoBox.style.boxSizing = 'content-box';
    // infoBox.style.border = '1px solid ' + COLORS[2];
    infoBox.style.borderRadius = '2px';
    infoBox.style.color = COLORS[0];
    infoBox.style.backgroundColor = COLORS[1];
    infoBox.style.boxShadow = '0px 30px 90px -20px rgba(0,0,0,0.75)';
    infoBox.style.zIndex = (HIGHEST_Z_INDEX >= global.Number.MAX_VALUE - 1
                            ? global.Number.MAX_VALUE
                            : HIGHEST_Z_INDEX + 1);
    infoBox.style.fontSize = FONT_SIZE + 'px';
    infoBox.style.lineHeight = '1em';
    infoBox.style.opacity = 0.5; // 0.02;
    infoBox.onmouseenter = function (event) {
        event.target.style.opacity = 1.0;
    };
    infoBox.onmouseleave = function (event) {
        event.target.style.opacity = 0.5;
    };
    global.document.body.appendChild(infoBox);

    
    canvas.style.position = 'relative';
    canvas.style.height = '100%';
    canvas.style.width = '100%';
    canvas.style.boxSizing = 'border-box';
    canvas.style.padding = ((2 * ARROW_DISTANCE) + 'px '
                            + (2 * ARROW_DISTANCE + FONT_SIZE) + 'px');
    infoBox.appendChild(canvas);

    tabs.style.height = '100%';
    tabs.style.overflowY = 'scroll';
    canvas.appendChild(tabs);

    tabSet.style.display = 'flex';
    tabSet.style.width = '100%';
    tabSet.style.flexWrap = 'wrap';
    tabs.appendChild(tabSet);
    tabPanels.style.textAlign = 'justify';
    tabs.appendChild(tabPanels);

    createArrowNode(canvas, true, true);
    createArrowNode(canvas, true, false);
    createArrowNode(canvas, false, true);
    createArrowNode(canvas, false, false);

    // fadeInAndOut(infoBox, 1.05, 50, 3000);

    // XXX For long pages, only process text nodes visible on the current
    // viewport (i.e. on semi-demand)
    processElementsAndText(nodeFilter);
}());
