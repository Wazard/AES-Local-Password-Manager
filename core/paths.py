"""Per-user data location.

When the app is installed (e.g. under Program Files), the executable's folder is
not writable, so the vault, config and log live in %APPDATA%\\SecureVault. A
one-time migration moves any vault/config that used to sit next to the script or
exe into this folder, so existing data is preserved.
"""
import os

APP_DIR_NAME = "SecureVault"


def data_dir():
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    path = os.path.join(base, APP_DIR_NAME)
    try:
        os.makedirs(path, exist_ok=True)
    except OSError:
        pass
    return path


def migrate_legacy(filenames):
    """Move legacy files (kept in the current dir or next to the exe) into the
    data dir, once, if they aren't already there."""
    import sys
    import shutil
    dest_dir = data_dir()
    legacy_dirs = []
    try:
        legacy_dirs.append(os.getcwd())
    except OSError:
        pass
    if sys.argv and sys.argv[0]:
        legacy_dirs.append(os.path.dirname(os.path.abspath(sys.argv[0])))

    for name in filenames:
        dest = os.path.join(dest_dir, name)
        if os.path.lexists(dest):
            continue
        for d in legacy_dirs:
            src = os.path.join(d, name)
            if os.path.abspath(src) == os.path.abspath(dest):
                continue
            if os.path.isfile(src) and not os.path.islink(src):
                try:
                    shutil.move(src, dest)
                    break
                except OSError:
                    pass
