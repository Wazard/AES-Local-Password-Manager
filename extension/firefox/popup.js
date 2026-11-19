const content = document.getElementById("content");
const muteBox = document.getElementById("mute");

const send = (m) => browser.runtime.sendMessage(m);
const openOptions = () => browser.runtime.openOptionsPage();

function clear() {
  while (content.firstChild) content.removeChild(content.firstChild);
}

function el(tag, opts = {}) {
  const node = document.createElement(tag);
  if (opts.text) node.textContent = opts.text;
  if (opts.className) node.className = opts.className;
  return node;
}

// Show a plain message, optionally with one inline action button.
function showMessage(parts) {
  clear();
  const wrap = el("div", { className: "msg" });
  for (const p of parts) {
    if (typeof p === "string") {
      wrap.appendChild(document.createTextNode(p));
    } else if (p.link) {
      const b = el("button", { text: p.link, className: "link" });
      b.addEventListener("click", p.onClick);
      wrap.appendChild(b);
    } else if (p.err) {
      wrap.appendChild(el("span", { text: p.err, className: "err" }));
    }
  }
  content.appendChild(wrap);
}

muteBox.addEventListener("change", (e) => send({ type: "SET_MUTE", value: e.target.checked }));

async function main() {
  const { muted } = await send({ type: "GET_MUTE" });
  muteBox.checked = !!muted;

  const [tab] = await browser.tabs.query({ active: true, currentWindow: true });
  let domain = "";
  try { domain = new URL(tab.url).hostname; } catch (e) {}
  if (!domain) { showMessage(["No website in this tab."]); return; }

  const res = await send({ type: "GET_CREDENTIALS", domain });
  if (res.status === "unpaired") {
    showMessage(["Not paired yet. ", { link: "Open options", onClick: openOptions },
                 " to enter the port and token."]);
    return;
  }
  if (res.status === "unreachable") {
    showMessage([{ err: "Can't reach the app." },
                 " Is Secure Vault running with the server enabled?"]);
    return;
  }
  if (res.status === 401) {
    showMessage([{ err: "Pairing failed." }, " ", { link: "Fix in options", onClick: openOptions }, "."]);
    return;
  }
  if (res.status === 423) {
    showMessage([{ err: "Vault is locked." }, " Unlock the app, then retry."]);
    return;
  }
  if (!res.ok) { showMessage([{ err: "Unexpected error." }]); return; }

  const matches = (res.body && res.body.matches) || [];
  if (!matches.length) { showMessage([`No saved accounts for ${domain}.`]); return; }

  clear();
  for (const m of matches) {
    const btn = el("button", { className: "match" });
    btn.appendChild(el("span", { text: m.name, className: "name" }));
    btn.appendChild(el("span", { text: m.user || "", className: "user" }));
    btn.addEventListener("click", async () => {
      await browser.tabs.sendMessage(tab.id, { type: "FILL", user: m.user, pass: m.pass });
      window.close();
    });
    content.appendChild(btn);
  }
}

main();
