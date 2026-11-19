# Changelog

## Unreleased

### Added

- An iOS app (`ios/`) that opens the same vault file, built as an unsigned
  `.ipa` by GitHub Actions for sideloading.
- **Send to iPhone**: the phone icon in the top bar sends the vault to the iOS
  app over the local Wi-Fi. The iPhone shows a 6-digit code that has to be
  typed on the PC, and asks before it replaces anything.

## 1.2.0

### Changed

- The interface was rebuilt. Colours, fonts, sizes, radii and spacing now come
  from `UI/palette.json`, so the whole look can be changed by editing one file;
  a `palette.json` in `%APPDATA%\SecureVault` overrides the bundled one and
  survives updates.
- Headings are sentence case instead of ALL CAPS, and are properly cased per
  language — title-casing translated strings produced "Generateur De Mots De
  Passe" in French.
- Confirmations, warnings and errors are in-app panels rather than Windows
  message boxes.
- Settings is split into labelled sections, with each explanation next to the
  control it belongs to.

### Added

- Passwords are masked by default everywhere, with a reveal toggle.
- Password strength is shown when creating a vault, changing the master
  password, and saving an account; the generator reports entropy in bits.
- A copy-password button on each account row, and a countdown on the copy
  buttons showing when the clipboard is wiped.
- A warning 30 seconds before the idle auto-lock, and the login screen now says
  when it locked because of inactivity.
- Inline validation on the account form, including duplicate names.
- Website URL and date added are shown on the account detail screen.

## 1.1.0

### Fixed

- Moving `vault.pwmanager` no longer looks like a first run. The location is
  recorded, the vault can live anywhere, and a missing one gets a "Vault not
  found" screen instead of a login form that silently created an empty vault.
- Creating a vault is now a deliberate choice — typing a master password never
  creates one.
- A dangling backup symlink no longer locks you out ("no vault" on one screen,
  "a vault already exists here" on the other).

### Added

- Dated backups: a read-only encrypted copy on every change, named
  `vault_bk_2026_08_08_1432_01.pwmanager` so the folder sorts chronologically.
  Newest 20 kept, plus one per day for 60 days.
- Restore from the backup screen; the current vault is copied first, so a
  restore is undoable.
- Editable account names — renaming keeps the entry's position.
- Version shown on the login and settings screens.

### Changed

- Backups replace the OneDrive symlink, which needed admin rights and kept only
  one copy. Existing links are retired at startup; the vault is never touched.
- Search is cached: 200 searches over 400 accounts, 25.5 ms to ~0.
- The installer updates in place instead of installing a second copy, and keeps
  your vault and backups in `%APPDATA%\SecureVault`.

## 1.0.0

Initial release.
