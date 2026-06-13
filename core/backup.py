"""Helpers to back up the encrypted vault to OneDrive via a symbolic link.

Strategy: move the real `vault.pwmanager` into a OneDrive folder and leave a
symlink in its place. The app keeps reading/writing the same path, while
OneDrive syncs the real file as an always-current encrypted backup.
"""
import os
import shutil

SUBFOLDER = "SecureVault"


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


def create_link(vault_file, onedrive_dir):
    """Moves the vault into OneDrive and symlinks it back. Returns (ok, message)."""
    if os.path.islink(vault_file):
        return False, "Already linked — your vault is backed up to OneDrive."

    backup_dir = os.path.join(onedrive_dir, SUBFOLDER)
    os.makedirs(backup_dir, exist_ok=True)
    target = os.path.join(backup_dir, os.path.basename(vault_file))

    moved = False
    if os.path.exists(vault_file) and not os.path.islink(vault_file):
        if os.path.exists(target):
            return False, ("A backup already exists in OneDrive. Remove one copy "
                           "so they don't conflict, then try again.")
        shutil.move(vault_file, target)
        moved = True

    try:
        os.symlink(target, vault_file)
    except OSError as e:
        if moved and not os.path.exists(vault_file):
            shutil.move(target, vault_file)  # roll back
        return False, ("Could not create the link: %s. On Windows this needs "
                       "Developer Mode enabled (Settings → Privacy & security → "
                       "For developers) or running the app as administrator." % e)

    return True, "Backup link created. Your vault now syncs to OneDrive."


def remove_link(vault_file):
    """Replaces the symlink with a real local copy of the vault. (ok, message)."""
    if not os.path.islink(vault_file):
        return False, "No backup link is set up."
    target = os.path.realpath(vault_file)
    os.unlink(vault_file)
    if os.path.exists(target):
        shutil.copy2(target, vault_file)
    return True, "Backup link removed. The OneDrive copy was kept as a backup."
