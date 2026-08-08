# Changelog

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
