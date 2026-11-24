# Secure Vault

A local, offline password manager for Windows, built with Python and
CustomTkinter. Vault data is encrypted on disk with Argon2id and AES-256-GCM,
and an optional Firefox extension provides autofill over a token-authenticated
localhost connection.

![Secure Vault](images/screenshot.png)

## Features

- **Strong encryption at rest** — Argon2id key derivation with AES-256-GCM
  authenticated encryption.
- **In-memory protection** — passwords are held encrypted with a per-session
  key and decrypted only when actually needed.
- **Password generator** — configurable length and character sets, in a
  hyphen-grouped format, with a live "decryption" animation.
- **Organisation** — search, sort by name or date added, favourites, and
  switchable grid / list views.
- **Firefox extension** — autofill, save-on-signup, and password generation,
  all over localhost.
- **Dated backups** — a read-only encrypted copy on every change, named
  `vault_bk_2026_08_08_1432_01.pwmanager` so the folder sorts chronologically,
  kept in OneDrive when there is one, and restorable from inside the app.
- **Editable account names** — renaming an account keeps its place in the vault.
- **Sync with your phone** (iPhone or Android) — over your Wi-Fi, confirmed
  with a code shown on the phone: what you add or change on the phone comes
  into the PC's vault, and the phone gets the PC's accounts back.
- **Auto-lock and tray** — re-locks after inactivity and can keep running in the
  system tray.
- **Localisation** — English, Italian, French, and Danish.

## Theming

Every colour, font, radius and spacing value lives in
[`UI/palette.json`](UI/palette.json). Nothing visual is hard-coded in the
screens, so a different look is a matter of editing that file and restarting
the app — no code changes. The bundled palette is "Midnight Indigo": cool
near-black neutrals, an indigo primary, and amber kept for favourites only.

`fonts.ui` and `fonts.mono` fall back to `ui_fallback` / `mono_fallback` when
the preferred family isn't installed, so a palette can name any font safely.

## Security

- **Key derivation:** Argon2id (64 MiB, 3 passes, 4 lanes). Vaults created with
  the earlier PBKDF2 format are migrated to Argon2id automatically on the next
  save.
- **Encryption:** AES-256-GCM, so tampering with the vault file is detected.
- **Master password:** never written to disk. It is used once at login to derive
  the key and then discarded; only the derived key is kept for the session.
- **In memory:** each password is re-encrypted with a random per-session key and
  decrypted only at the moment it is displayed, copied, filled, or saved.
- **Extension bridge:** served only on `127.0.0.1`, gated by a pairing token,
  rejected for web-page origins, and only while the vault is unlocked.

This protects data at rest and in transit to the extension. It does not defend
against malware already running on the machine while the vault is unlocked,
which is outside the scope of a user-space password manager.

## Firefox extension

The companion extension ~in [`extension/firefox`](extension/firefox)~ (now approved and can be found [here](https://addons.mozilla.org/en-US/firefox/addon/securevault/)) fills and
saves credentials by talking to the running app on `127.0.0.1`. It never
contacts a remote server. See [`extension/README.md`](extension/README.md) for
setup, pairing, and usage.

## iOS app

A native iOS version lives in [`ios/`](ios/README.md). It opens the same vault
file (for example from OneDrive), and GitHub Actions builds an unsigned `.ipa`
for sideloading with AltStore or Sideloadly.

## Android app

The Android version lives in [`android/`](android/README.md): the same vault
file and the same Wi-Fi sync, with fingerprint unlock instead of Face ID.
GitHub Actions builds an `.apk` to install directly.

## Running from source

Requires Python 3.11+ on Windows.

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

On first launch you choose to create a new vault; the master password you enter
protects it. The vault (`vault.pwmanager`) starts under `%APPDATA%\SecureVault`,
so it keeps working even when the app is installed in a read-only location.

The vault file can live anywhere — another drive, a synced folder. Where it is
gets recorded in `vault_location.json`. If you move the file, the app says so on
the next launch and lets you point it at the new place; it never starts an empty
vault on its own.

## Building the installer

Requires [Inno Setup](https://jrsoftware.org/isdl.php) (set `$env:ISCC` if it is
installed somewhere unusual) and `pip install nuitka`.

```
.\build.ps1
```

That compiles `main.dist\` with Nuitka and packages it as
`installer\SecureVaultSetup.exe`. A folder build is used rather than `--onefile`
because it trips far fewer antivirus heuristics. `-SkipCompile` repackages an
existing build. The version comes from [`core/version.py`](core/version.py)
alone — bump it there and the exe metadata, the installer and the app's settings
screen all follow.

### Updating an existing install

Run the new `SecureVaultSetup.exe`; it installs over the old version in place,
keeping the same entry in Apps & features. What makes that work is the `AppId`
GUID in [`installer.iss`](installer.iss) — Windows identifies an installed
product by it, so **it must never change**, or an update becomes a second,
parallel installation. A copy that was never installed by Setup (an unpacked
`main.dist\`, say) is found via the app's own `securevault://` registration and
offered as the destination, so it gets replaced rather than duplicated.

Setup asks you to close Secure Vault first if it is running (including from the
tray), because the app holds a named mutex while it runs and its files can't be
replaced underneath it.

Your data is never part of the install: the vault, its backups, the recorded
vault location and the extension settings all live in `%APPDATA%\SecureVault`.
Updating leaves them alone, and so does uninstalling — remove that folder by
hand if you ever want the data gone.

## Tech stack

- Python 3.11, CustomTkinter — interface
- cryptography, argon2-cffi — encryption
- pystray, Pillow — system tray
- Nuitka — packaging

## Credits

Application icon by [Freepik](https://www.flaticon.com/) on Flaticon.

## License

Released under the MIT License. See [LICENSE](LICENSE) for details.
