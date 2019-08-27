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


const TITLE_ACTIVATE = "Activate Yokome"
const TITLE_DEACTIVATE = "Deactivate Yokome"
const TITLE_INACTIVE = "Yokome: Only Works on HTTP Pages"
const APPLICABLE_PROTOCOLS = ["http:", "https:"]


function toggleYokome(tab) {
    function toggle(action) {
        console.log(action);
        if (action === TITLE_ACTIVATE) {
            browser.tabs.executeScript({file: "/content.js"}).then(function () {
                browser.pageAction.setTitle({tabId: tab.id, title: TITLE_DEACTIVATE});
                browser.tabs.sendMessage(tab.id, {command: "activate"});
            });
        } else if (action === TITLE_DEACTIVATE) {
            browser.pageAction.setTitle({tabId: tab.id, title: TITLE_ACTIVATE})
            browser.tabs.sendMessage(tab.id, {command: "deactivate"});
        }
    }
    var getAction = browser.pageAction.getTitle({tabId: tab.id});
    getAction.then(toggle);
}


function initializePageAction(tab) {
    if (APPLICABLE_PROTOCOLS.includes(new URL(tab.url).protocol)) {
        // browser.pageAction.setIcon({tabId: tab.id, path: ""});
        browser.pageAction.setTitle({tabId: tab.id, title: TITLE_ACTIVATE});
        browser.pageAction.show(tab.id);
    } else {
        browser.pageAction.setTitle({tabId: tab.id, title: TITLE_INACTIVE});
    }
}


// Initialize Yokome for all tabs on first load
var getAllTabs = browser.tabs.query({});
getAllTabs.then((tabs) => {
    for (let tab of tabs) {
        initializePageAction(tab);
    }
});

// Reset Yokome for a tab on that tab's update
browser.tabs.onUpdated.addListener((id, changeInfo, tab) => {
    initializePageAction(tab);
});

// Toggle Yokome on page action click
browser.pageAction.onClicked.addListener(toggleYokome);
