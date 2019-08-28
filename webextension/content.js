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


(function() {
    var infoBox, tabSet, tabPanels,
        FONT_SIZE = 15,              // Of the info box (px)
        BOX_DISTANCE = 5,            // Info box to the edge of the window (px)
        ARROW_DISTANCE = 3,          // Arrows to the edges of the info box (px)
        HIGHEST_Z_INDEX,
        COLORS = ['#000000', '#ffffff', '#a5a5a5', '#fcba12'],
        nodeFilter = {
            acceptNode: function(node) {
                if (node.nodeType === Node.ELEMENT_NODE) {
                    // Filter out script, style and hidden elements
                    if (node.tagName === 'SCRIPT'
                        || node.tagName === 'STYLE'
                        || node.style.display === 'none') {
                        return NodeFilter.FILTER_REJECT;
                    }
                    // Consider text nodes contained in all other elements
                    return NodeFilter.FILTER_SKIP;
                }
                // Filter out whitespace-only text nodes
                if (node.nodeValue.trim() === '') {
                    return NodeFilter.FILTER_REJECT;
                }
                // Accept all other text nodes
                return NodeFilter.FILTER_ACCEPT;
            }
        },
        TIMEOUT = 350,                  // (ms)
        tokenizerTimeoutStart,
        disambiguationTimeoutStart,
        currentRectangles,
        TRIES = 10,                     // Tries to locate resource via HTTP
        LANGUAGE = 'jpn',
        POS_SEPARATOR = '; ',
        GLOSS_SEPARATOR = ' ▪ ';
    
    // Run only once
    if (window.yokomeHasRun) {
        return;
    }
    window.yokomeHasRun = true;


    // Fades in for factor > 1
    // Fades out for factor < 1
    function fade(element, factor, step) {
        // Asserts 0 < factor != 1 and element.style.opacity > 0
        var MIN = 0.5,
            opacity = element.style.opacity,
            interval = setInterval(function () {
                opacity *= factor;
                if (factor > 1 && opacity >= 1) {
                    clearInterval(interval);
                    element.style.opacity = 1;
                } else if (factor < 1 &&　opacity <= MIN) {
                    clearInterval(interval);
                    element.style.opacity = MIN;
                } else {
                    element.style.opacity = opacity;
                }
            }, step);
    }


    function fadeInAndOut(element, factor, step, wait) {
        // Asserts factor > 1.0
        var opacity = element.style.opacity,
            interval = setInterval(function () {
                opacity *= factor;
                if (opacity >= 1) {
                    clearInterval(interval);
                    element.style.opacity = 1;
                    setTimeout(function () {
                        fade(element, 1.0 / factor, step);
                    }, wait);
                } else {
                    element.style.opacity = opacity;
                }
            }, step);
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
        var arrowNode = document.createElement('div');
        arrowNode.appendChild(document.createTextNode(
                top ? (left ? '◤' : '◥') : (left ? '◣' : '◢')));
        // // XXX Check whether properties are overridden
        // arrowNode.top = top;
        // arrowNode.left = left;
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


    function resetTokenizerTimeoutStart() {
        tokenizerTimeoutStart = Date.now();
    }


    function resetDisambiguationTimeoutStart() {
        disambiguationTimeoutStart = Date.now();
    }


    function getCursorPosition(event) {
        return [event.clientX, event.clientY];
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


    function getIndex(node) {
        var idx = -1;
        while (node !== null) {
            idx += 1;
            node = node.previousSibling;
        }
        return idx;
    }


    function post(url, data, node, callback, args) {
        // TODO Do not retry on a HTTP 400 response
        var tries = TRIES,
            request = new XMLHttpRequest();
        data = JSON.stringify(data);
        request.open('POST', url, true);
        request.onreadystatechange = function () {
            if (this.readyState === 4) {
                if (this.status === 200) {
                    callback(node, JSON.parse(this.responseText), args);
                }
                else if (tries > 0) {
                    var new_request = new XMLHttpRequest();
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


    function switchToTab(node) {
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

    
    function initiateTabSwitching(event) {
        var node = event.target;
        while (node.onclick !== initiateTabSwitching) {
            node = node.parentElement;
        }
        switchToTab(node);
    }


    function refreshTabs(node, lexemes, args) {
        var i, j, k, l, progressBar, score, intensity, // entries,
            subnode, subsubnode, subsubsubnode, ruby, reading, max_score;
        node.wilps_lexemes = lexemes;
        lexemes = lexemes.lexemes;
        // TODO Rather use dojox.gfx.Surface to clear all objects
        while (tabSet.hasChildNodes()) {
            tabSet.removeChild(tabSet.lastChild);
        }
        while (tabPanels.hasChildNodes()) {
            tabPanels.removeChild(tabPanels.lastChild);
        }
        for (i = 0; i < lexemes.length; i++) {
            // Create tab button
            node = document.createElement('div');
            subnode = document.createElement('span');
            ruby = document.createElement('ruby');
            ruby.appendChild(document.createTextNode(lexemes[i].headwords[0][0] === null ? lexemes[i].headwords[0][1] : lexemes[i].headwords[0][0]));
            reading = document.createElement('rt');
            reading.appendChild(document.createTextNode(lexemes[i].headwords[0][1]));
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
            node.onclick = initiateTabSwitching;
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
            node = document.createElement('div');
            for (j = 0; j < lexemes[i].roles.length; j++) {
                subnode = document.createElement('div');
                // progressBar = document.createElement('progress');
                // progressBar.setAttribute('value', lexemes.length - i);
                // progressBar.setAttribute('max', lexemes.length + 1);
                // progressBar.style.height = '2px';
                // subnode.appendChild(progressBar);

                subsubnode = document.createElement('div');
                for (k = 0; k < lexemes[i].roles[j].poss.length; k++) {
                    subsubnode.appendChild(document.createTextNode(lexemes[i].roles[j].poss[k] + (k < lexemes[i].roles[j].poss.length - 1 ? POS_SEPARATOR : '')));
                }
                subsubnode.style.width = '100%';
                subnode.appendChild(subsubnode);

                for (k = 0; k < lexemes[i].roles[j].connotations.length; k++) {
                    subsubnode = document.createElement('div');
                    subsubnode.appendChild(document.createTextNode('[' + lexemes[i].roles[j].connotations[k].sense_id.toString() + '] '));
                    for (l = 0; l < lexemes[i].roles[j].connotations[k].glosses.length; l++) {
                        if (lexemes[i].roles[j].connotations[k].glosses[l][0] !== null) {
                            subsubsubnode = document.createElement('i');
                            subsubsubnode.appendChild(document.createTextNode(lexemes[i].roles[j].connotations[k].glosses[l][0]));
                            subsubnode.appendChild(subsubsubnode);
                        }
                        subsubnode.appendChild(document.createTextNode(lexemes[i].roles[j].connotations[k].glosses[l][1] + (l < lexemes[i].roles[j].connotations[k].glosses.length - 1 ? GLOSS_SEPARATOR : '')));
                    }
                    subsubnode.style.width = '100%';
                    score = lexemes[i].roles[j].connotations[k].score / max_score;
                    subsubnode.style.color = 'hsl(43, ' + Math.round(100 * score) + '%, ' + Math.round(50 * score) + '%)';
                    subnode.appendChild(subsubnode);

                    // subsubnode = document.createElement('div');
                    // subsubnode.appendChild(document.createTextNode(entries[i % 3][j][2]));
                    // subsubnode.style.width = '100%';
                    // subnode.appendChild(subsubnode);
                }

                node.appendChild(subnode);
            }
            tabPanels.appendChild(node);
        }
        // Create settings tab button
        node = document.createElement('div');
        node.appendChild(document.createTextNode('About'));
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
        node.onclick = initiateTabSwitching;
        tabSet.appendChild(node);
        // Create tab panel
        node = document.createElement('div');
        // node.appendChild(document.createTextNode(tabTexts[i]));
        // node.appendChild(document.createElement('br'));
        // node.appendChild(document.createTextNode('Difficulty: '));
        // progressBar = document.createElement('input');
        // progressBar.setAttribute('type', 'range');
        // progressBar.setAttribute('min', 0);
        // progressBar.setAttribute('max', 100);
        // progressBar.setAttribute('value', 20);
        // node.appendChild(progressBar);

        node.innerHTML = '<p><b>Yokome 1.0</b><br />'
            + '\u00a9 Copyright 2019, Julian Betz.<br />'
            + 'Licensed under the Apache License, Version 2.0. '
            + 'Find the <a href="https://github.com/julianbetz/yokome">'
            + 'source code</a> on GitHub.</p>'
            + '<p>The Japanese version makes use of the following data:'
            + '<ul>'
            + '<li><a href="http://www.edrdg.org/jmdict/j_jmdict.html">'
            + 'JMdict</a>: Published by the <a href="http://www.edrdg.org/">'
            + 'Electronic Dictionary Research and Development Group</a> under '
            + 'the <a href="http://www.edrdg.org/edrdg/licence.html">'
            + 'Creative Commons Attribution-ShareAlike Licence (V3.0)</a></li>'
            + '<li>JEITA Public Morphologically Tagged Corpus (in ChaSen '
            + 'format): Created and distributed by <a href="http://lilyx.net/">'
            + 'Masato Hagiwara</a> with data originating from '
            + '<a href="http://www.aozora.gr.jp/">Aozora Bunko</a> and '
            + '<a href="http://www.genpaku.org/">Project Sugita Genpaku</a>'
            + '</li>'
            + '</ul>'
            + '</p>';
        
        tabPanels.appendChild(node);
        if (tabSet.childNodes.length > 0) { // XXX Remove, should always be the case if statistics are used
            switchToTab(tabSet.childNodes[0]);
            // fadeInAndOut(infoBox, 1.05, 50, 3000);
        }
    }


    function maybeRefreshTabs(node) {
        if (Date.now() >= disambiguationTimeoutStart + TIMEOUT) {
            if ('wilps_lemmas' in node) {
                console.log(node);
                if ('wilps_lexemes' in node) { // Use cached data
                    refreshTabs(node, node.wilps_lexemes, null, null);
                } else {
                    post('http://localhost:5003/wsd/disambiguate',
                         {'language': LANGUAGE,
                          'i': node.wilps_i,
                          'tokens': node.wilps_sentence},
                         node,
                         refreshTabs,
                         []);
                }
            }
        }
    }


    function disambiguateTargetToken(event) {
        var nodes, node, charNode, i, j, max_j, rectangle, rectangles,
            found = false,
            cursor = getCursorPosition(event);
        // Only search for the word hovered over if the cursor left the old one
        if (currentRectangles === undefined
            || !anyContains(currentRectangles, cursor)) {
            // Search for the word hovered over
            nodes = event.target.childNodes;
            i = nodes.length;
            // XXX Use binary search instead for efficiency for long texts
            while (i--) {
                node = nodes[i];
                rectangles = [];
                if (node.nodeType === Node.TEXT_NODE) {
                    max_j = node.nodeValue.length;
                    for (j = 0; j < max_j; j++) {
                        // Create temporary span element to measure out text
                        // node
                        charNode = document.createElement('span');
                        charNode.appendChild(document.createTextNode(node.nodeValue[j]));
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
                        resetDisambiguationTimeoutStart();
                        setTimeout(function () {maybeRefreshTabs(node);}, TIMEOUT);
                        return;
                    }
                }
            }
        }
    }


    function tokenize(node, response, args) {
        var event = args[0], head = args[1], tail = args[2], i, j, k, max_i, max_j, max_k, lemma, sentence, replacement, span, ruby, rt;
        if (response.language === LANGUAGE) {
            max_i = response.sentences.length;
            // Insert leading space
            replacement = document.createTextNode(head);
            node.parentNode.insertBefore(replacement, node);
            for (i = 0; i < max_i; i++) {
                sentence = response.sentences[i];
                max_j = sentence.length;
                for (j = 0; j < max_j; j++) {
                    // Insert token
                    replacement = document.createTextNode(sentence[j][0].surface_form.graphic);
                    node.parentNode.insertBefore(replacement, node);
                    replacement.wilps_lemmas = [];
                    replacement.wilps_sentence = sentence;
                    replacement.wilps_i = j;
                    max_k = sentence[j].length;
                    for (k = 0; k < max_k; k++) {
                        lemma = sentence[j][k].lemma;
                        if (lemma !== null) {
                            span = document.createElement('span');
                            ruby = document.createElement('ruby');
                            ruby.appendChild(document.createTextNode(lemma.graphic));
                            rt = document.createElement('rt');
                            rt.appendChild(document.createTextNode(lemma.phonetic));
                            ruby.appendChild(rt);
                            span.appendChild(ruby);
                            replacement.wilps_lemmas.push(span);
                        }
                    }
                }
            }
            // Insert trailing space
            replacement = document.createTextNode(tail);
            node.parentNode.insertBefore(replacement, node);
            // Remove original text
            node.parentNode.onmousemove = disambiguateTargetToken;
            node.parentNode.onmouseleave = resetDisambiguationTimeoutStart;
            node.parentNode.removeChild(node);
            disambiguateTargetToken(event);
        }
    }


    function maybeTokenize(event, node) {
        if (Date.now() >= tokenizerTimeoutStart + TIMEOUT) {
            console.log(node);
            node.parentNode.onmouseenter = resetTokenizerTimeoutStart;
            node.parentNode.onmouseleave = null;
            var text = node.nodeValue,
                head = text.match(/^\s*/),
                tail = text.match(/\s*$/);
            post('http://localhost:5003/tokenizer/tokenize',
                 {'language': LANGUAGE, 'text': text},
                 node, tokenize, [event, head, tail]);
        }
    }


    function initialize(nodeFilter) {
        // Iterator for text elements only
        var treeWalker = document.createTreeWalker(
                document.body,
                NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT,
                nodeFilter,
                false),
            nodes = [],
            node = treeWalker.nextNode(),
            i;
        // Store all text nodes in array, as a TreeWalker does not support
        // deletion during iteration
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
                setTimeout(
                    function () {
                        var j;
                        for (j = 0; j < event.target.childNodes.length; j++) {
                            if (event.target.childNodes[j].nodeType === Node.TEXT_NODE) {
                                maybeTokenize(event, event.target.childNodes[j]);
                            }
                        }
                    },
                    TIMEOUT);
            };
            node.onmouseleave = resetTokenizerTimeoutStart;
        }
    }


    function createInfoBox() {
        var canvas = document.createElement('div'),
            tabs = document.createElement('div'),
            node;

        infoBox = document.createElement('div');
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
        infoBox.style.zIndex = (HIGHEST_Z_INDEX >= Number.MAX_VALUE - 1
                                ? Number.MAX_VALUE
                                : HIGHEST_Z_INDEX + 1);
        infoBox.style.fontSize = FONT_SIZE + 'px';
        infoBox.style.lineHeight = '1em';
        infoBox.style.opacity = 0.5; // 0.02;
        infoBox.style.filter = 'saturate(0%)';
        infoBox.onmouseenter = function (event) {
            event.target.style.opacity = 1.0;
            event.target.style.filter = 'saturate(100%)';
        };
        infoBox.onmouseleave = function (event) {
            event.target.style.opacity = 0.5;
            event.target.style.filter = 'saturate(0%)';
        };
        document.body.appendChild(infoBox);
        
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

        tabSet = document.createElement('div'),
        tabSet.style.display = 'flex';
        tabSet.style.width = '100%';
        tabSet.style.flexWrap = 'wrap';
        tabs.appendChild(tabSet);

        tabPanels = document.createElement('div'),
        tabPanels.style.textAlign = 'justify';
        tabs.appendChild(tabPanels);

        createArrowNode(canvas, true, true);
        createArrowNode(canvas, true, false);
        createArrowNode(canvas, false, true);
        createArrowNode(canvas, false, false);

        // fadeInAndOut(infoBox, 1.05, 50, 3000);

        // XXX For long pages, only process text nodes visible on the current
        // viewport (i.e. on semi-demand)
        initialize(nodeFilter);
    }
    
    
    function removeInfoBox() {
        if (infoBox !== undefined) {
            infoBox.remove();
            infoBox = undefined;
        }
    }


    function getHighestZIndex() {
        var treeWalker = document.createTreeWalker(
            document.body,
            NodeFilter.SHOW_ELEMENT,
            null,
            false),
            node,
            current,
            max = 0;
        for (node = treeWalker.nextNode(); node; node = treeWalker.nextNode()) {
            current = Number(document.defaultView.getComputedStyle(node, null)
                             .getPropertyValue('z-index'));
            max = current > max ? current : max;
        }
        return max;
    }


    HIGHEST_Z_INDEX = getHighestZIndex();
    browser.runtime.onMessage.addListener(function (message) {
        if (message.command === "activate") {
            createInfoBox();
        } else if (message.command === "deactivate") {
            removeInfoBox();
        }        
    });
}());
