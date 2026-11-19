"""Dated backup copies of the encrypted vault.

Every save drops a copy into the backup folder — the OneDrive `SecureVault`
folder when OneDrive is set up, so copies sync off this machine, otherwise the
per-user data dir. Copies are named

    vault_bk_<year>_<month>_<day>_<time>_<index>.pwmanager

with fixed-width, zero-padded fields, so sorting by name is sorting by date.
They are made read-only, which is what makes Windows ask twice before one is
deleted by accident.

A copy is an ordinary vault file: the master password that opened the vault
opens the copy, and restoring one is a file copy. Nothing here can read vault
contents — backups stay encrypted throughout.
"""
import os
import re
import shutil
import stat
import time

SUBFOLDER = "SecureVault"
BACKUPS_DIR_NAME = "backups"

# Retention: every one of the most recent KEEP_RECENT saves, plus the last
# backup of each day going back KEEP_DAYS — so a busy afternoon can't push a
# month of history out.
KEEP_RECENT = 20
KEEP_DAYS = 60

PREFIX = "vault_bk_"
STAMP_FORMAT = "%Y_%m_%d_%H%M"
NAME_RE = re.compile(r"^vault_bk_(\d{4}_\d{2}_\d{2}_\d{4})_\d{2}\.pwmanager$")


def _when(name):
    """When a backup was taken, read from its name.

    Not from the file's timestamp: copying a file carries the original's
    modification time along with it, so every backup of one vault would claim
    the same moment. The name is the record — that is what it is for.
    """
    match = NAME_RE.match(name)
    if not match:
        return None
    try:
        return time.mktime(time.strptime(match.group(1), STAMP_FORMAT))
    except ValueError:
        return None


def get_onedrive_dir():
    """Returns the user's OneDrive root, or None if not configured."""
    for var in ("OneDriveConsumer", "OneDrive", "OneDriveCommercial"):
        path = os.environ.get(var)
        if path and os.path.isdir(path):
            return path
    return None


def default_dir():
    """Backups land in OneDrive when there is one — a copy that survives this
    machine is the point — and in the app's own data dir otherwise."""
    from core import paths
    onedrive = get_onedrive_dir()
    if onedrive:
        return os.path.join(onedrive, SUBFOLDER, BACKUPS_DIR_NAME)
    return os.path.join(paths.data_dir(), BACKUPS_DIR_NAME)


def backup_dir():
    """The folder backups go to: the user's choice, else the default."""
    from core import vault_location
    return vault_location.backup_dir() or default_dir()


def set_backup_dir(path):
    from core import vault_location
    vault_location.set_backup_dir(path)


def _protect(path):
    """Make a backup read-only, so deleting it takes a deliberate confirmation
    rather than a stray Del keypress."""
    try:
        os.chmod(path, stat.S_IREAD)
    except OSError:
        pass


def _unprotect(path):
    try:
        os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
    except OSError:
        pass


def _next_name(folder, when=None):
    """A name that sorts chronologically, with an index to separate copies made
    within the same minute."""
    stamp = time.strftime(STAMP_FORMAT, time.localtime(when))
    for index in range(1, 100):
        name = "%s%s_%02d.pwmanager" % (PREFIX, stamp, index)
        if not os.path.exists(os.path.join(folder, name)):
            return name
    return "%s%s_99.pwmanager" % (PREFIX, stamp)


def make_backup(vault_file, folder=None):
    """Copy the current vault into the backup folder. Returns the new path, or
    None if there was nothing to copy or the folder can't be written to —
    a failed backup must never stop the vault itself from being saved."""
    source = os.path.realpath(vault_file)
    if not os.path.isfile(source):
        return None
    folder = folder or backup_dir()
    try:
        os.makedirs(folder, exist_ok=True)
        target = os.path.join(folder, _next_name(folder))
        shutil.copy(source, target)  # not copy2: a backup's own time is its own
    except OSError:
        return None
    _protect(target)
    prune(folder)
    return target


def list_backups(folder=None):
    """Every backup in the folder, newest first."""
    folder = folder or backup_dir()
    try:
        names = os.listdir(folder)
    except OSError:
        return []
    found = []
    for name in sorted(names, reverse=True):  # the names sort chronologically
        when = _when(name)
        if when is None:
            continue
        path = os.path.join(folder, name)
        try:
            found.append({"path": path, "name": name, "when": when,
                          "size": os.path.getsize(path)})
        except OSError:
            pass
    return found


def prune(folder=None, keep_recent=KEEP_RECENT, keep_days=KEEP_DAYS):
    """Drop old backups: keep the newest `keep_recent`, plus the last backup of
    each day within `keep_days`. Only files matching the backup naming scheme
    are ever removed — anything else in the folder is left alone."""
    backups = list_backups(folder)
    keep = {b["path"] for b in backups[:keep_recent]}
    cutoff = time.time() - keep_days * 86400
    seen_days = set()
    for b in backups:
        if b["when"] < cutoff:
            continue
        day = time.strftime("%Y%m%d", time.localtime(b["when"]))
        if day not in seen_days:
            seen_days.add(day)
            keep.add(b["path"])
    removed = 0
    for b in backups:
        if b["path"] not in keep and delete_backup(b["path"]):
            removed += 1
    return removed


def delete_backup(path):
    """Remove one backup (read-only has to be cleared first, by design)."""
    if not NAME_RE.match(os.path.basename(path)):
        return False
    _unprotect(path)
    try:
        os.remove(path)
        return True
    except OSError:
        return False


def restore(backup_path, vault_file):
    """Put a backup back in place as the live vault.

    The vault as it stands is copied into the backup folder first, so restoring
    the wrong one is itself undoable. Returns (ok, message).
    """
    from core import storage_handler

    if not os.path.isfile(backup_path):
        return False, "That backup is no longer there."
    if not storage_handler.looks_like_vault(backup_path):
        return False, "That file does not look like a vault."

    target = os.path.realpath(vault_file)
    tmp = target + ".restore"
    try:
        os.makedirs(os.path.dirname(target), exist_ok=True)
        # Take the copy first: backing up the current vault prunes old ones, and
        # the backup being restored could be among them.
        shutil.copy(backup_path, tmp)
        # Backups are read-only; a live vault must not be, or the next save fails.
        _unprotect(tmp)
        make_backup(vault_file)  # safety net: the vault as it stands right now
        os.replace(tmp, target)  # atomic: the vault is never half-written
    except OSError as e:
        try:
            os.remove(tmp)
        except OSError:
            pass
        return False, "Could not restore the backup: %s" % e
    return True, "Backup restored."
