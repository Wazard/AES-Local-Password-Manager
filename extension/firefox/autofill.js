// Content script (all pages): proactively offers to fill saved logins, prompts
// to save new ones, and nudges the user to unlock the app — all suppressible
// with the session mute toggle. Also handles FILL requests from the popup.
if (!window.__secureVaultLoaded) {
  window.__secureVaultLoaded = true;

  const send = (m) => browser.runtime.sendMessage(m);
  const isVisible = (el) => !!el && el.offsetParent !== null;

  function findPasswordField() {
    const pwds = Array.from(document.querySelectorAll('input[type="password"]'));
    return pwds.find(isVisible) || pwds[0] || null;
  }

  function findUsernameField(pwd) {
    const inputs = Array.from(document.querySelectorAll("input"));
    if (pwd) {
      const idx = inputs.indexOf(pwd);
      for (let i = idx - 1; i >= 0; i--) {
        const t = (inputs[i].type || "text").toLowerCase();
        if (["text", "email", "tel", ""].includes(t) && isVisible(inputs[i])) return inputs[i];
      }
    }
    return document.querySelector(
      'input[autocomplete="username"], input[type="email"], ' +
      'input[name*="user" i], input[name*="email" i], input[id*="user" i]');
  }

  function setValue(el, value) {
    const proto = el.tagName === "TEXTAREA"
      ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
    Object.getOwnPropertyDescriptor(proto, "value").set.call(el, value);
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
  }

  function fill(user, pass) {
    const pwd = findPasswordField();
    const userField = findUsernameField(pwd);
    if (userField && user) setValue(userField, user);
    if (pwd && pass) { setValue(pwd, pass); pwd.focus(); }
  }

  // --- Banner UI ---
  function removeBanner() {
    const old = document.getElementById("__sv_banner");
    if (old) old.remove();
  }

  function banner(text, actions) {
    removeBanner();
    const box = document.createElement("div");
    box.id = "__sv_banner";
    box.style.cssText =
      "position:fixed;top:16px;right:16px;z-index:2147483647;max-width:300px;" +
      "background:#292929;color:#98B1BD;font-family:'Segoe UI',sans-serif;" +
      "font-size:13px;line-height:1.4;padding:12px;border-radius:10px;" +
      "box-shadow:0 4px 16px rgba(0,0,0,.4);border:1px solid #43443F;";
    const msg = document.createElement("div");
    msg.textContent = text;
    msg.style.marginBottom = actions.length ? "8px" : "0";
    box.appendChild(msg);
    for (const a of actions) {
      const b = document.createElement("button");
      b.textContent = a.label;
      b.style.cssText =
        "margin-right:6px;margin-top:4px;border:none;border-radius:6px;cursor:pointer;" +
        "padding:6px 10px;font-size:12px;color:#F2F4F5;background:" +
        (a.primary ? "#66769C" : "#43443F") + ";";
      b.addEventListener("click", a.onClick);
      box.appendChild(b);
    }
    const close = document.createElement("button");
    close.textContent = "✕";
    close.style.cssText = "float:right;border:none;background:none;color:#7E8C93;cursor:pointer;font-size:13px;";
    close.addEventListener("click", removeBanner);
    box.insertBefore(close, msg);
    document.body.appendChild(box);
  }

  // FILL request from the popup.
  browser.runtime.onMessage.addListener((msg) => {
    if (msg && msg.type === "FILL") fill(msg.user, msg.pass);
  });

  // Capture submitted credentials so we can offer to save after navigation.
  document.addEventListener("submit", (e) => {
    try {
      const pwd = (e.target.querySelector &&
        e.target.querySelector('input[type="password"]')) || findPasswordField();
      if (!pwd || !pwd.value) return;
      const user = findUsernameField(pwd);
      send({ type: "SAVE_CANDIDATE",
             data: { domain: location.hostname, user: user ? user.value : "", pass: pwd.value } });
    } catch (err) {}
  }, true);

  async function init() {
    const domain = location.hostname;
    if (!domain) return;
    const { muted } = await send({ type: "GET_MUTE" });
    if (muted) return;

    const pwd = findPasswordField();

    // Offer to save a just-submitted login (survives the page navigation).
    const cand = await send({ type: "GET_SAVE_CANDIDATE", domain });
    if (cand && cand.candidate) {
      const c = cand.candidate;
      const res = await send({ type: "GET_CREDENTIALS", domain });
      const exists = res.ok && res.body && (res.body.matches || []).some((m) => m.user === c.user);
      if (!exists) {
        banner(`Save this login for ${domain} to Secure Vault?`, [
          { label: "Save", primary: true, onClick: async () => {
              await send({ type: "SAVE_CREDENTIAL",
                           data: { domain, name: domain, user: c.user, pass: c.pass } });
              removeBanner();
          } },
          { label: "Not now", onClick: removeBanner },
        ]);
        return;
      }
    }

    if (!pwd) return; // not a login page → nothing else to offer

    const res = await send({ type: "GET_CREDENTIALS", domain });
    if (res.status === "unreachable") {
      banner("Secure Vault is closed. Open and log in to autofill here.", []);
    } else if (res.status === 423) {
      banner("Secure Vault is locked. Log in to autofill here.", []);
    } else if (res.ok && res.body && (res.body.matches || []).length) {
      banner(`Fill your login for ${domain}?`,
        res.body.matches.map((m) => ({
          label: `Fill ${m.name}`, primary: true,
          onClick: () => { fill(m.user, m.pass); removeBanner(); },
        })));
    }
  }

  init();
}
