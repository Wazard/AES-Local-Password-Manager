# Secure Vault — Browser Autofill Add-on

Fills usernames and passwords from your locally running **Secure Vault** app.
Two builds share the same logic: `extension/firefox/` (Manifest V2) and
`extension/chromium/` (Manifest V3, for Chrome / Edge / Brave / any Chromium
browser).
The add-on never sees your master password or your full vault — it asks the
running app for the credentials matching the current site, over an
authenticated `127.0.0.1` connection, and only while the vault is unlocked.

## How it works

```
Browser page ── popup ──► 127.0.0.1:<port> (Secure Vault app, unlocked) ──► matching credentials ──► fills the form
```

Requests are authenticated with a pairing **token** and reject real web-page
origins, so a website can't read your vault even if it guesses the port.

## Setup

1. **In the Secure Vault app**: open the **Extension** screen (top bar of the
   Accounts page) and tick **Enable autofill server**. Note the **port** and
   **pairing token** shown there.
2. **Give your accounts a URL**: edit each account and fill in the *Website URL*
   field (e.g. `github.com`) so the add-on can match it to a page.
3. **Install the add-on**:
   - **Firefox**: install it from
     [Firefox Add-ons](https://addons.mozilla.org/en-US/firefox/addon/securevault/).
     For development, go to `about:debugging#/runtime/this-firefox` → **Load
     Temporary Add-on…** → select `extension/firefox/manifest.json`.
   - **Chrome / Edge / Brave**: go to `chrome://extensions`, enable **Developer
     mode**, click **Load unpacked**, and select the `extension/chromium/`
     folder.
4. **Pair it**: click the add-on's toolbar icon → it will prompt you to open
   options. Paste the **port** and **token** from step 1 and click **Save**.

## Use

The add-on works proactively on any page with a login form:

- **Fill** — if you have a saved account for the site, a prompt offers to fill it.
  You can also click the toolbar button to pick from matching accounts.
- **Generate & save** — on a signup / create-password page for a site you
  haven't saved, a prompt offers to generate a strong password *through the app*
  and fills it (including the confirm-password field), then offers to save the
  new login. This is the only path that stores an account, so a credential is
  only ever saved deliberately, never captured behind the scenes.
- **Not saved yet** — when you reach a login page for a site you have no account
  for (and it isn't a signup page), a prompt notes it isn't saved and offers an
  **Open app** button so you can add it in Secure Vault yourself. The extension
  never reads or captures the password you type into a login form.
- **Unlock** — if the app is closed or locked, a prompt reminds you to open and
  log in to Secure Vault.

### Opening the app from the browser

If the app is closed or locked when you ask to generate or save, the extension
will open/focus it via a `securevault://` link. It comes on together with
**Enable autofill server** in the app's settings.

The first time a `securevault://` link fires, the browser asks for
confirmation — allow it (and optionally tick "remember" / "always allow").

Then: pressing **Generate** (or **Save**) when the app isn't ready opens/focuses
it on the login screen; once you log in, the password fills / saves
automatically. If the app is already running and unlocked, it just works with no
launch. The link points at whichever copy of the app last started with the
autofill server on, and is rewritten on every start — so switching between the
dev script and the installed `.exe` only takes launching the one you want.

### Muting suggestions

The popup has a **Mute suggestions** toggle. As stated there: *mute only works
for the current session; if you want a permanent mute, disable the extension —
it's a password manager, so if you don't intend to use it you have no business
having it on.*

## Notes / limitations (MVP)

- Field detection is heuristic (the visible password field plus the nearest
  preceding text/email field); unusual login forms may not be detected.
- A temporary add-on is removed when Firefox restarts. For a permanent install,
  the add-on needs to be signed/published on addons.mozilla.org. A Chromium
  "Load unpacked" extension persists across restarts but shows a developer-mode
  warning until published to the Chrome Web Store.
- The Chromium build runs as an MV3 service worker, so its only session-only
  state (the mute toggle) lives in `chrome.storage.session` rather than in
  memory; behaviour matches the Firefox build. No credential is ever stored by
  the extension in either build.
