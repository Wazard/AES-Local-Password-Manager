"""Where the vault and its backups live.

The vault is not pinned to one path. Its location is recorded in
`vault_location.json` inside the per-user data dir, so the file can sit in
OneDrive, on another drive, or anywhere else, and keep working once the app has
been pointed at it.

The record also lets the app tell "the vault moved" apart from "there is no
vault yet". Without it a relocated file looks exactly like a first run, and the
app would silently start with an empty vault while the real one sits untouched
somewhere else.
"""
import os
import json

from core import paths

FILE_NAME = "vault.pwmanager"
POINTER_FILE = os.path.join(paths.data_dir(), "vault_location.json")


def default_path():
    """Where a vault goes when the user hasn't chosen anywhere else."""
    return os.path.join(paths.data_dir(), FILE_NAME)


def _load():
    try:
        with open(POINTER_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _store(key, value):
    """Merge one setting into the pointer file, keeping the others. Best-effort:
    if this fails the only cost is a trip through the "find my vault" screen on
    the next launch."""
    data = _load()
    if data.get(key) == value:
        return
    data[key] = value
    tmp = POINTER_FILE + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, POINTER_FILE)
    except OSError:
        pass


def recorded():
    """The path the vault was last used at, or None if we've never had one."""
    path = _load().get("path")
    return os.path.abspath(path) if path else None


def remember(path):
    """Record where the vault lives."""
    _store("path", os.path.abspath(path))


def backup_dir():
    """The folder the user chose for backups, or None for the default."""
    path = _load().get("backup_dir")
    return os.path.abspath(path) if path else None


def set_backup_dir(path):
    _store("backup_dir", os.path.abspath(path))


def exists(path):
    """True if `path` holds a usable vault file. A dangling symlink (a backup
    link whose target was moved or deleted) counts as missing, not as a vault."""
    return bool(path) and os.path.isfile(path)


def known_places():
    """Paths a vault may plausibly be, best first: where we last used it, the
    default data dir, and the folder the old OneDrive link feature used."""
    from core import backup
    places = [recorded(), default_path()]
    onedrive = backup.get_onedrive_dir()
    if onedrive:
        places.append(os.path.join(onedrive, backup.SUBFOLDER, FILE_NAME))
    unique = []
    for path in places:
        if path and path not in unique:
            unique.append(path)
    return unique


def current():
    """The path the app reads and writes right now.

    A recorded location wins even when the file is missing: the app has to say
    "your vault isn't there any more" rather than quietly adopt some other copy
    it happens to find.
    """
    return recorded() or found_elsewhere() or default_path()


def found_elsewhere():
    """A vault sitting at a known place other than the current one, if any —
    offered as a suggestion when the vault has gone missing."""
    here = recorded()
    for path in known_places():
        if path != here and exists(path):
            return path
    return None


def sync():
    """Adopt the vault already on this machine if no location is recorded yet
    (upgrades from the versions that hard-coded the data dir). Called once at
    startup, before any screen asks where the vault is."""
    if recorded():
        return
    for path in known_places():
        if exists(path):
            remember(path)
            return


def adopt_symlink_target():
    """Retire the old OneDrive symlink: earlier versions kept the vault in a
    cloud folder by leaving a link in the data dir, which needed administrator
    rights to set up. Locations are recorded now, so the link is redundant —
    point straight at the file it refers to and drop it.

    The vault itself is never touched. If the link can't be removed, reading
    through it still works, so this is safe to skip."""
    path = recorded() or default_path()
    if not os.path.islink(path):
        return
    target = os.path.realpath(path)
    if not os.path.isfile(target):
        return  # broken link — the "vault not found" screen handles this
    remember(target)
    try:
        os.unlink(path)
    except OSError:
        pass
