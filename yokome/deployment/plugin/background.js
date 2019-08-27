const TITLE_ACTIVATE = "Activate Yokome"
const TITLE_DEACTIVATE = "Deactivate Yokome"
const TITLE_INACTIVE = "Yokome: Only Works on HTTP Pages"
const APPLICABLE_PROTOCOLS = ["http:", "https:"]

// function toggleYokome() {
//     function on(tabs) {
//         browser.tabs.insertCSS({code: 'body {background-color: #3287dc;}'}).then(function () {
//             browser.tabs.sendMessage(tabs[0].id, {
//                 command: 'on'
//             });
//         });
//     }
//     browser.console.log('Yokome on');
// }

// browser.pageAction.onClicked.addListener(function (tab) {
//     console.log(true);
// });

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
