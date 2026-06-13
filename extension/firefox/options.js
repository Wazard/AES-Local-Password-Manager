const portEl = document.getElementById("port");
const tokenEl = document.getElementById("token");
const statusEl = document.getElementById("status");

async function load() {
  const { port, token } = await browser.storage.local.get(["port", "token"]);
  if (port) portEl.value = port;
  if (token) tokenEl.value = token;
}

document.getElementById("save").addEventListener("click", async () => {
  const port = parseInt(portEl.value.trim(), 10);
  const token = tokenEl.value.trim();
  if (!port || !token) {
    statusEl.textContent = "Enter both a port and a token.";
    return;
  }
  await browser.storage.local.set({ port, token });
  statusEl.textContent = "Saved. You can close this and use the toolbar button.";
});

load();
