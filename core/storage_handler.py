"""Reading and writing the encrypted vault file.

The path isn't fixed — see `core.vault_location`. Everything here goes through
`vault_path()` so a vault that has been moved is found again instead of being
mistaken for one that never existed.
"""
import os

from core import encryption
from core import vault_location

# Vault states, as far as the UI is concerned.
PRESENT = "present"   # a vault file is where we expect it
MOVED = "moved"       # a vault has been used before, but it isn't there now
ABSENT = "absent"     # no vault has ever been used here (genuine first run)


def vault_path() -> str:
    return vault_location.current()


def vault_state() -> str:
    if vault_location.exists(vault_path()):
        return PRESENT
    return MOVED if vault_location.recorded() else ABSENT


def looks_like_vault(path) -> bool:
    """Cheap sanity check before adopting a file the user picked. The contents
    can't be verified without the master password; this only rules out files
    that plainly aren't vault blobs."""
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as f:
            magic = f.read(4)
    except OSError:
        return False
    # v2 vaults start with a magic string; legacy v1 blobs are salt+nonce+data.
    return magic == encryption.MAGIC or size > 28


def read_vault() -> bytes:
    path = vault_path()
    if not vault_location.exists(path):
        return b""
    with open(path, "rb") as f:
        return f.read()


def write_vault(data: bytes):
    path = vault_path()
    # Resolve through a symlink (e.g. a OneDrive backup link) so the atomic
    # replace targets the real file and the link itself stays intact.
    target = os.path.realpath(path)
    temp_file = target + ".tmp"
    with open(temp_file, "wb") as f:
        f.write(data)
    os.replace(temp_file, target)  # Atomic swap
    vault_location.remember(path)
