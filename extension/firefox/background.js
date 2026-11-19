// Background relay: the content script and popup talk to the local app through
// here, so the pairing token never lives in page context and CORS is avoided.
//
// `muted` is kept in memory only, so it resets when the browser session ends —
// matching the "mute is session-only" behaviour. The extension never holds a
// credential of its own: passwords are fetched on demand and passed straight to
// the page, never cached here.
let muted = false;

async function getConfig() {
  return browser.storage.local.get(["port", "token"]);
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

browser.runtime.onMessage.addListener((msg) => {
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
    case "LAUNCH_APP":
      // Triggers the securevault:// handler to open or focus the desktop app.
      browser.tabs.create({ url: "securevault://open", active: false })
        .then((t) => setTimeout(() => browser.tabs.remove(t.id).catch(() => {}), 1500))
        .catch(() => {});
      return Promise.resolve({ ok: true });
    case "GET_MUTE":
      return Promise.resolve({ muted });
    case "SET_MUTE":
      muted = !!msg.value;
      return Promise.resolve({ muted });
  }
});
