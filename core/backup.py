"""Helpers to back up the encrypted vault to a folder via a symbolic link.

Strategy: move the real `vault.pwmanager` into a chosen folder (OneDrive or any
user-selected directory) and leave a symlink in its place. The app keeps reading
and writing the same path, while the folder holds an always-current encrypted
backup (and syncs it, in OneDrive's case).

create_link / remove_link return (ok, message, reason). reason == "permission"
means the symlink operation needs administrator rights — the caller can then
re-run the operation elevated.
"""
import os
import shutil

SUBFOLDER = "SecureVault"


def can_symlink():
    """Non-destructive check of whether this process may create symlinks
    (true with admin rights or Windows Developer Mode)."""
    import tempfile
    d = tempfile.mkdtemp()
    link, tgt = os.path.join(d, "l"), os.path.join(d, "t")
    open(tgt, "w").close()
    try:
        os.symlink(tgt, link)
        return True
    except OSError:
        return False
    finally:
        shutil.rmtree(d, ignore_errors=True)


def get_onedrive_dir():
    """Returns the user's OneDrive root, or None if not configured."""
    for var in ("OneDriveConsumer", "OneDrive", "OneDriveCommercial"):
        path = os.environ.get(var)
        if path and os.path.isdir(path):
            return path
    return None


def status(vault_file):
    is_link = os.path.islink(vault_file)
    return {
        "onedrive": get_onedrive_dir(),
        "is_link": is_link,
        "target": os.path.realpath(vault_file) if is_link else None,
        "vault_exists": os.path.exists(vault_file),
    }


def create_link(vault_file, base_dir):
    """Moves the vault into base_dir/SecureVault and symlinks it back."""
    if os.path.islink(vault_file):
        return True, "Already linked — your vault is backed up.", "already"

    backup_dir = os.path.join(base_dir, SUBFOLDER)
    target = os.path.join(backup_dir, os.path.basename(vault_file))

    try:
        os.makedirs(backup_dir, exist_ok=True)
    except OSError as e:
        return False, "Cannot write to that folder: %s" % e, "error"

    moved = False
    if os.path.exists(vault_file) and not os.path.islink(vault_file):
        if os.path.exists(target):
            return False, "A backup already exists there. Remove one copy first.", "conflict"
        try:
            shutil.move(vault_file, target)
            moved = True
        except OSError as e:
            return False, "Could not move the vault: %s" % e, "error"

    try:
        os.symlink(target, vault_file)
    except OSError:
        if moved and not os.path.exists(vault_file):
            shutil.move(target, vault_file)  # roll back
        return False, "Creating the backup link needs administrator rights.", "permission"

    return True, "Backup link created. Your vault now syncs to this folder.", "ok"


def import_vault(vault_file, source, mode):
    """Adopt an existing vault file. mode 'move' relocates it here; mode 'link'
    leaves it in place and points a symlink at it (so cloud backups keep working).
    Returns (ok, message, reason)."""
    if os.path.lexists(vault_file):
        return False, "A vault already exists here.", "exists"
    if not os.path.isfile(source):
        return False, "That file was not found.", "error"
    if mode == "move":
        try:
            shutil.move(source, vault_file)
            return True, "Vault imported.", "ok"
        except OSError as e:
            return False, "Could not move the file: %s" % e, "error"
    try:
        os.symlink(source, vault_file)
        return True, "Vault linked.", "ok"
    except OSError:
        return False, "Linking needs administrator rights.", "permission"


def prepare_link(vault_file, base_dir):
    """Create the backup folder and move the vault into it (unprivileged part of
    linking). Returns (ok, target_path_or_message)."""
    if os.path.islink(vault_file):
        return False, "Already linked."
    backup_dir = os.path.join(base_dir, SUBFOLDER)
    target = os.path.join(backup_dir, os.path.basename(vault_file))
    try:
        os.makedirs(backup_dir, exist_ok=True)
    except OSError as e:
        return False, "Cannot write to that folder: %s" % e
    if os.path.exists(vault_file) and not os.path.islink(vault_file):
        if os.path.exists(target):
            return False, "A backup already exists there. Remove one copy first."
        try:
            shutil.move(vault_file, target)
        except OSError as e:
            return False, "Could not move the vault: %s" % e
    return True, target


def rollback_link(vault_file, target):
    """Undo prepare_link if the symlink was never created (move the vault back)."""
    if not os.path.lexists(vault_file) and os.path.exists(target):
        try:
            shutil.move(target, vault_file)
        except OSError:
            pass


def remove_link(vault_file):
    """Replaces the symlink with a real local copy of the vault."""
    if not os.path.islink(vault_file):
        return False, "No backup link is set up.", "none"
    target = os.path.realpath(vault_file)
    try:
        os.unlink(vault_file)
    except OSError:
        return False, "Removing the backup link needs administrator rights.", "permission"
    if os.path.exists(target):
        try:
            shutil.copy2(target, vault_file)
        except OSError as e:
            return False, "Link removed, but the local copy could not be restored: %s" % e, "error"
    return True, "Backup link removed. The backup copy was kept.", "ok"
