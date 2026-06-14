# Secure Vault — Firefox Autofill Add-on

Fills usernames and passwords from your locally running **Secure Vault** app.
The add-on never sees your master password or your full vault — it asks the
running app for the credentials matching the current site, over an
authenticated `127.0.0.1` connection, and only while the vault is unlocked.

## How it works

```
Firefox page ── popup ──► 127.0.0.1:<port> (Secure Vault app, unlocked) ──► matching credentials ──► fills the form
```

Requests are authenticated with a pairing **token** and reject real web-page
origins, so a website can't read your vault even if it guesses the port.

## Setup

1. **In the Secure Vault app**: open the **⚙ Extension** screen (top bar of the
   Accounts page) and tick **Enable autofill server**. Note the **port** and
   **pairing token** shown there.
2. **Give your accounts a URL**: edit each account and fill in the *Website URL*
   field (e.g. `github.com`) so the add-on can match it to a page.
3. **Load the add-on in Firefox** (temporary, for development):
   - Go to `about:debugging#/runtime/this-firefox`
   - Click **Load Temporary Add-on…**
   - Select `extension/firefox/manifest.json`
4. **Pair it**: click the add-on's toolbar icon → it will prompt you to open
   options. Paste the **port** and **token** from step 1 and click **Save**.

## Use

The add-on works proactively on any page with a login form:

- **Fill** — if you have a saved account for the site, a prompt offers to fill it.
  You can also click the toolbar button to pick from matching accounts.
- **Generate** — on a signup / create-password page for a site you haven't
  saved, a prompt offers to generate a strong password *through the app* and
  fills it (including the confirm-password field).
- **Save** — after you submit a login/signup that isn't saved yet, a prompt
  offers to store it in your vault.
- **Unlock** — if the app is closed or locked, a prompt reminds you to open and
  log in to Secure Vault.

### Opening the app from the browser

If the app is closed or locked when you ask to generate or save, the extension
will open/focus it via a `securevault://` link. To enable this:

1. In the app: **⚙ Extension → Allow the browser to open this app**.
2. The first time a `securevault://` link fires, Firefox asks for confirmation —
   allow it (and optionally tick "remember").

Then: pressing **Generate** (or **Save**) when the app isn't ready opens/focuses
it on the login screen; once you log in, the password fills / saves
automatically. If the app is already running and unlocked, it just works with no
launch. (The launcher points at whatever copy of the app registered it, so
re-toggle it if you move from the dev script to the built `.exe`.)

### Muting suggestions

The popup has a **Mute suggestions** toggle. As stated there: *mute only works
for the current session; if you want a permanent mute, disable the extension —
it's a password manager, so if you don't intend to use it you have no business
having it on.*

## Notes / limitations (MVP)

- Field detection is heuristic (the visible password field plus the nearest
  preceding text/email field); unusual login forms may not be detected.
- A temporary add-on is removed when Firefox restarts. For a permanent install,
  the add-on needs to be signed/published on addons.mozilla.org.
