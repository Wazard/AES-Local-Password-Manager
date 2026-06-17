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
- **OneDrive backup** — optional symlink so the encrypted vault syncs as a
  continuous backup.
- **Auto-lock and tray** — re-locks after inactivity and can keep running in the
  system tray.
- **Localisation** — English, Italian, French, and Danish.

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

The companion extension in [`extension/firefox`](extension/firefox) fills and
saves credentials by talking to the running app on `127.0.0.1`. It never
contacts a remote server. See [`extension/README.md`](extension/README.md) for
setup, pairing, and usage.

## Running from source

Requires Python 3.11+ on Windows.

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

On first launch, the master password you enter creates a new local vault
(`vault.pwmanager`, stored under `%APPDATA%\SecureVault` so it keeps working
even when the app is installed in a read-only location).

## Building the installer

`build.ps1` compiles the app into a standalone folder build with Nuitka, then
packages it into a per-user Windows installer with Inno Setup:

```
.\build.ps1
```

This produces `installer\SecureVaultSetup.exe`. It requires
[Inno Setup](https://jrsoftware.org/isdl.php) on the `PATH` (or set `$env:ISCC`
to `ISCC.exe`); a folder build is used rather than `--onefile` because it trips
far fewer antivirus heuristics.

To deploy the folder build locally without producing a setup `.exe`, run
`install.ps1` — it copies the most recent `main.dist\` into
`%LOCALAPPDATA%\Programs\SecureVault`, adds Start Menu and Desktop shortcuts,
and writes a matching uninstaller. A prebuilt installer is also on the releases
tab.

## Tech stack

- Python 3.11, CustomTkinter — interface
- cryptography, argon2-cffi — encryption
- pystray, Pillow — system tray
- Nuitka — packaging

## Credits

Application icon by [Freepik](https://www.flaticon.com/) on Flaticon.

## License

Released under the MIT License. See [LICENSE](LICENSE) for details.
