import os

VAULT_FILE = "vault.pwmanager"

def read_vault() -> bytes:
    if not os.path.exists(VAULT_FILE):
        return b""
    with open(VAULT_FILE, "rb") as f:
        return f.read()

def write_vault(data: bytes):
    # Resolve through a symlink (e.g. a OneDrive backup link) so the atomic
    # replace targets the real file and the link itself stays intact.
    target = os.path.realpath(VAULT_FILE)
    temp_file = target + ".tmp"
    with open(temp_file, "wb") as f:
        f.write(data)
    os.replace(temp_file, target) # Atomic swap