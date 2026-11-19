# Secure Vault for iOS

A native SwiftUI app that opens the **same `.pwmanager` file** as the Windows
app: same Argon2id + AES-256-GCM format, same gzip+JSON payload, same entry
order, unknown fields kept as they are. Legacy (PBKDF2) vaults open too and
are upgraded on the next save, as on the desktop.

## Getting the .ipa (no Mac needed)

The `iOS app` GitHub Actions workflow (`.github/workflows/ios.yml`) builds it
on a macOS runner whenever `ios/`, `core/` or the palette changes, or on
demand from **Actions › iOS app › Run workflow**. It:

1. generates the Xcode project from `project.yml` with XcodeGen,
2. runs the unit tests on a simulator — they open vaults written by the
   desktop's own Python code (`tools/make_fixtures.py`),
3. checks that the desktop code can open a vault written by the iOS code
   (`tools/check_roundtrip.py`),
4. builds an **unsigned** `SecureVault-<version>.ipa` and attaches it to the run
   as an artifact (it downloads as a .zip with the .ipa inside).

## Sideloading

Unsigned is what sideloading tools expect: they sign the app with your own
Apple ID when they install it.

- **AltStore / SideStore** — open the .ipa from the Files app with AltStore,
  or use *My Apps › +*.
- **Sideloadly** (Windows) — drag the .ipa in, enter your Apple ID, Start.

With a free Apple ID the install expires after 7 days. Refresh it in the tool
before that — your vault and settings are kept. If it does lapse, reinstall
the same build over it without deleting the app.

## Using it with the PC vault

On first launch choose **Open an existing vault** and pick `vault.pwmanager`
in the Files picker, for example in your OneDrive folder (the OneDrive app must
be installed and show up in Files). The file is edited in place, so changes
show up on the PC too. Before every save the app re-reads the file. If the PC
saved in the meantime, the PC's version is loaded first and your change is
applied on top of it, so neither side's edits are overwritten.

### Or sync with the PC over Wi-Fi

No cloud folder needed. With the phone and the PC on the same network:

1. On the iPhone tap **Receive from your PC over Wi-Fi** (on the first screen,
   on the lock screen, or in Settings). It shows a 6-digit code. Allow
   *Local Network* access the first time iOS asks.
2. On the PC click the **phone icon** in the top bar (Send to iPhone). The
   iPhone appears in the list; if it doesn't, type the address the phone shows.
3. Type the code and click **Send vault**, then tap **Use this vault** on the
   phone and unlock with your master password.

After that, use **Sync** to keep the two in step. On the iPhone open
**Settings › Sync with PC over Wi-Fi**. On the PC click the phone icon, type
the address and code, and click **Sync**. Everything you added, changed,
renamed or deleted on the iPhone since the last sync goes into the PC's vault,
and the iPhone gets the merged vault back, including what's new on the PC.
If the same account was edited on both sides, the iPhone's edit wins.
**Replace iPhone vault** on the PC overwrites the iPhone instead.

The file is sent exactly as it is stored, already encrypted with your master
password. The code proves the file came from your PC, and the phone stops
listening after one transfer or five wrong codes. The received vault is stored
in the app. If one was already there it goes to the backups first, and the
app switches to the new one. Syncing needs both apps open on the same network;
it doesn't happen in the background.

You can also **Create a new vault** that lives in the app
(Files › On My iPhone › Secure Vault). Every save keeps a dated backup in the
`backups` folder next to it, using the same names and retention rules as the
desktop.

## What's in it

Unlock (master password or Face ID), search, the four sorts, favourites,
add / edit / rename / delete, reveal and copy (the clipboard stays on this
device and clears itself), password generator, master-password change,
backups and restore. The app locks when it leaves the foreground: right away,
or after a delay you choose, with the screen hidden from the app switcher.

Not ported: the browser extension bridge, tray, translations, and the
Windows-only parts.

## Building locally (on a Mac)

```
brew install xcodegen
cd ios && xcodegen generate && open SecureVault.xcodeproj
```

`Vendor/argon2` is the reference Argon2 implementation (tag 20190702,
CC0 / Apache-2.0); `UI/palette.json` is bundled from the desktop app, so the
colours follow it.
