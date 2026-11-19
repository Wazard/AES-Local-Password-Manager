// Background relay (MV3 service worker): the content script and popup talk to
// the local app through here, so the pairing token never lives in page context
// and CORS is avoided.
//
// This runs as a service worker that Chrome can suspend at any time, so the
// session-only `muted` flag can't live in a plain variable (it would reset on
// every suspend). It lives in chrome.storage.session instead, which is
// in-memory and cleared when the browser closes. The extension never holds a
// credential of its own: passwords are fetched on demand and passed straight to
// the page, never cached here.

async function getConfig() {
  return chrome.storage.local.get(["port", "token"]);
}

async function apiFetch(path, options = {}) {
  const { port, token } = await getConfig();
  if (!port || !token) return { ok: false, status: "unpaired" };
  try {
    const res = await fetch(`http://127.0.0.1:${port}${path}`, {
      ...options,
      headers: { "X-Vault-Token": token, ...(options.headers || {}) },
    });
    let body = null;
    try { body = await res.json(); } catch (e) {}
    return { ok: res.ok, status: res.status, body };
  } catch (e) {
    return { ok: false, status: "unreachable" };
  }
}

async function handle(msg) {
  switch (msg && msg.type) {
    case "GET_CREDENTIALS":
      return apiFetch(`/credentials?domain=${encodeURIComponent(msg.domain)}`);
    case "GET_STATUS":
      return apiFetch(`/status`);
    case "GENERATE":
      return apiFetch(`/generate`);
    case "SAVE_CREDENTIAL":
      return apiFetch(`/save`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(msg.data),
      });
    case "LAUNCH_APP": {
      // Triggers the securevault:// handler to open or focus the desktop app.
      const tab = await chrome.tabs.create({ url: "securevault://open", active: false })
        .catch(() => null);
      if (tab) setTimeout(() => chrome.tabs.remove(tab.id).catch(() => {}), 1500);
      return { ok: true };
    }
    case "GET_MUTE": {
      const { muted } = await chrome.storage.session.get("muted");
      return { muted: !!muted };
    }
    case "SET_MUTE":
      await chrome.storage.session.set({ muted: !!msg.value });
      return { muted: !!msg.value };
  }
  return undefined;
}

// Chrome does not honour a promise returned from onMessage (Firefox does), so
// reply via sendResponse and return true to keep the channel open for the async
// result.
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  handle(msg).then(sendResponse);
  return true;
});
