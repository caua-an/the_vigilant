const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

async function check(name) {
  let requested, rules, redirected;
  const listener = {addListener() {}};
  const api = {
    runtime: {onInstalled: listener, onStartup: listener, getURL: path => `extension://${path}`},
    alarms: {create() {}, onAlarm: listener},
    declarativeNetRequest: {
      async getSessionRules() { return []; },
      async updateSessionRules(update) { rules = update.addRules; },
    },
    tabs: {
      async query() { return [{id: 1, url: 'https://www.youtube.com/watch?v=1'}]; },
      async update(id, update) { redirected = [id, update.url]; },
    },
  };
  if (name === 'firefox') api.runtime.getBrowserInfo = async () => ({});
  const context = {
    chrome: api, navigator: name === 'brave' ? {brave: {isBrave: async () => true}} : {},
    fetch: async url => { requested = url; return {ok: true, json: async () => ({domains: ['youtube.com']})}; },
    AbortSignal, URL, console, setInterval() {},
  };
  if (name === 'firefox') context.browser = api;
  vm.runInNewContext(fs.readFileSync('extension/background.js', 'utf8'), context);
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(requested, `http://127.0.0.1:47653/state?browser=${name}`);
  assert.equal(rules[0].condition.requestDomains[0], 'youtube.com');
  assert.equal(redirected[1], 'extension://blocked.html');
}

Promise.all(['brave', 'chrome', 'firefox'].map(check)).then(() => console.log('Extensão: Brave, Chrome/Chromium e Firefox simulados OK')).catch(error => { console.error(error); process.exitCode = 1; });
