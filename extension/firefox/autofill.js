// Content script (all pages): proactively offers to fill saved logins, prompts
// to save new ones, and nudges the user to unlock the app — all suppressible
// with the session mute toggle. Also handles FILL requests from the popup.
if (!window.__secureVaultLoaded) {
  window.__secureVaultLoaded = true;

  const send = (m) => browser.runtime.sendMessage(m);
  const isVisible = (el) => !!el && el.offsetParent !== null;
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  let cancelWait = false;

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

  function visiblePasswords() {
    return Array.from(document.querySelectorAll('input[type="password"]')).filter(isVisible);
  }

  // Looks like account creation rather than login: an explicit new-password
  // field, or a password + confirm-password pair.
  function isSignupContext() {
    if (document.querySelector('input[autocomplete="new-password"]')) return true;
    return visiblePasswords().length >= 2;
  }

  function fillGeneratedPassword(value) {
    const pwds = visiblePasswords();
    pwds.forEach((p) => setValue(p, value));      // also fills the confirm field
    if (pwds[0]) pwds[0].focus();
  }

  async function generatePassword() {
    let pw = null;
    const r = await send({ type: "GENERATE" });
    if (r.ok && r.body && r.body.password) {
      pw = r.body.password;
    } else {
      // App closed or locked → open/focus it and wait for the user to log in.
      await send({ type: "LAUNCH_APP" });
      cancelWait = false;
      banner("Opening Secure Vault — log in and your password will fill automatically…",
             [{ label: "Cancel", onClick: () => { cancelWait = true; removeBanner(); } }]);
      for (let i = 0; i < 40 && !cancelWait; i++) {
        await sleep(1500);
        const g = await send({ type: "GENERATE" });
        if (g.ok && g.body && g.body.password) { pw = g.body.password; break; }
      }
      if (cancelWait || pw === null) return;
    }
    fillGeneratedPassword(pw);
    offerSaveGenerated();
  }

  // After generating/filling, immediately offer to save (reads the username and
  // password live at click time, so a late-typed email is still captured).
  function offerSaveGenerated() {
    const domain = location.hostname;
    banner("Password filled. Save this login to Secure Vault?", [
      { label: "Save", primary: true, onClick: () => {
          const pwd = findPasswordField();
          const userField = findUsernameField(pwd);
          saveWithUnlock({ domain, name: domain,
                           user: userField ? userField.value : "",
                           pass: pwd ? pwd.value : "" });
      } },
      { label: "Not now", onClick: removeBanner },
    ]);
  }

  async function saveWithUnlock(payload) {
    if (!payload.pass) { removeBanner(); return; }
    let s = await send({ type: "SAVE_CREDENTIAL", data: payload });
    if (s.ok) { removeBanner(); return; }
    // Only chase a login if the failure was "locked/closed" (not e.g. invalid).
    if (s.status !== 423 && s.status !== "unreachable" && s.status !== "unpaired") {
      removeBanner();
      return;
    }
    await send({ type: "LAUNCH_APP" });
    cancelWait = false;
    banner("Log in to Secure Vault to save this login…",
           [{ label: "Cancel", onClick: () => { cancelWait = true; removeBanner(); } }]);
    for (let i = 0; i < 40 && !cancelWait; i++) {
      await sleep(1500);
      const st = await send({ type: "GET_STATUS" });
      if (st.ok && st.body && st.body.unlocked) {
        const s2 = await send({ type: "SAVE_CREDENTIAL", data: payload });
        if (s2.ok) { removeBanner(); return; }
      }
    }
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
        const payload = { domain, name: domain, user: c.user, pass: c.pass };
        banner(`Save this login for ${domain} to Secure Vault?`, [
          { label: "Save", primary: true, onClick: () => saveWithUnlock(payload) },
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
    } else if (res.ok && isSignupContext()) {
      // New account on a site you haven't saved → offer a strong password.
      banner("Generate a strong password with Secure Vault?", [
        { label: "Generate & fill", primary: true, onClick: generatePassword },
      ]);
    }
  }

  init();
}
