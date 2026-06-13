const content = document.getElementById("content");
const muteBox = document.getElementById("mute");

const send = (m) => browser.runtime.sendMessage(m);
const show = (html) => { content.innerHTML = html; };
const openOptions = () => browser.runtime.openOptionsPage();

muteBox.addEventListener("change", (e) => send({ type: "SET_MUTE", value: e.target.checked }));

async function main() {
  const { muted } = await send({ type: "GET_MUTE" });
  muteBox.checked = !!muted;

  const [tab] = await browser.tabs.query({ active: true, currentWindow: true });
  let domain = "";
  try { domain = new URL(tab.url).hostname; } catch (e) {}
  if (!domain) { show("No website in this tab."); return; }

  const res = await send({ type: "GET_CREDENTIALS", domain });
  if (res.status === "unpaired") {
    show('Not paired yet. <button class="link" id="opt">Open options</button> to enter the port and token.');
    document.getElementById("opt").addEventListener("click", openOptions);
    return;
  }
  if (res.status === "unreachable") {
    show('<span class="err">Can\'t reach the app.</span> Is Secure Vault running with the server enabled?');
    return;
  }
  if (res.status === 401) {
    show('<span class="err">Pairing failed.</span> <button class="link" id="opt">Fix in options</button>.');
    document.getElementById("opt").addEventListener("click", openOptions);
    return;
  }
  if (res.status === 423) { show('<span class="err">Vault is locked.</span> Unlock the app, then retry.'); return; }
  if (!res.ok) { show('<span class="err">Unexpected error.</span>'); return; }

  const matches = (res.body && res.body.matches) || [];
  if (!matches.length) { show(`No saved accounts for <b>${domain}</b>.`); return; }

  show("");
  for (const m of matches) {
    const btn = document.createElement("button");
    btn.className = "match";
    btn.innerHTML = `<span class="name"></span><span class="user"></span>`;
    btn.querySelector(".name").textContent = m.name;
    btn.querySelector(".user").textContent = m.user || "";
    btn.addEventListener("click", async () => {
      await browser.tabs.sendMessage(tab.id, { type: "FILL", user: m.user, pass: m.pass });
      window.close();
    });
    content.appendChild(btn);
  }
}

main();
