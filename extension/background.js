const endpoint = 'http://127.0.0.1:47653';
let running = false;
const api = globalThis.browser || globalThis.chrome;
const browserName = (async () => {
  if (api.runtime.getBrowserInfo) return 'firefox';
  try {
    if (navigator.brave && await navigator.brave.isBrave()) return 'brave';
  } catch (_) { /* Navegadores Chromium sem API Brave. */ }
  return 'chrome';
})();

async function sync() {
  if (running) return;
  running = true;
  try {
    let domains = [];
    try {
      const response = await fetch(`${endpoint}/state?browser=${await browserName}`, {signal: AbortSignal.timeout(1500), cache: 'no-store'});
      if (response.ok) domains = (await response.json()).domains;
    } catch (_) { /* Sem aplicativo, não manter bloqueios ativos. */ }
    if (!Array.isArray(domains)) domains = [];
    const rules = domains.map((domain, index) => ({
      id: index + 1, priority: 1,
      action: {type: 'redirect', redirect: {extensionPath: '/blocked.html'}},
      condition: {requestDomains: [domain], resourceTypes: ['main_frame']}
    }));
    const old = await api.declarativeNetRequest.getSessionRules();
    const existingDomains = old.map(rule => rule.condition.requestDomains?.[0]);
    if (JSON.stringify(existingDomains) !== JSON.stringify(domains)) {
      await api.declarativeNetRequest.updateSessionRules({removeRuleIds: old.map(rule => rule.id), addRules: rules});
    }
    if (domains.length) {
      for (const tab of await api.tabs.query({})) {
        try {
          const url = new URL(tab.url);
          if (['http:', 'https:'].includes(url.protocol) && domains.some(d => url.hostname === d || url.hostname.endsWith('.' + d))) {
            await api.tabs.update(tab.id, {url: api.runtime.getURL('blocked.html')});
          }
        } catch (_) { /* Abas internas e abas fechadas não precisam de ação. */ }
      }
    }
  } catch (error) {
    console.error('The Vigilant: falha ao atualizar bloqueios', error);
  } finally {
    running = false;
  }
}

api.runtime.onInstalled.addListener(sync);
api.runtime.onStartup.addListener(sync);
api.alarms.create('sync', {periodInMinutes: 0.5});
api.alarms.onAlarm.addListener(sync);
setInterval(sync, 2000);
sync();
