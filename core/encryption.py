"""Vault encryption.

Current format (v2): Argon2id key derivation + AES-256-GCM. The KDF parameters
and salt are stored in the file header, so the key is derived once at login and
reused (the plaintext master password can then be discarded). Older vaults
(PBKDF2) are still readable and are transparently migrated to v2 on next save.

Header layout (v2):
    b"PWV2" | time_cost(1) | memory_kib(4, big-endian) | parallelism(1)
            | salt(16) | nonce(12) | ciphertext
"""
import os
from argon2.low_level import hash_secret_raw, Type
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

MAGIC = b"PWV2"
KEY_LEN = 32

# Argon2id defaults (interactive use): 64 MiB, 3 passes, 4 lanes.
ARGON_TIME = 3
ARGON_MEMORY_KIB = 64 * 1024
ARGON_PARALLELISM = 4

# Legacy (v1) PBKDF2 parameters — only used to open and migrate old vaults.
LEGACY_ITERATIONS = 100_000


def _argon2_key(password: str, salt: bytes, time_cost: int, memory_kib: int, parallelism: int) -> bytes:
    return hash_secret_raw(
        password.encode("utf-8"), salt,
        time_cost=time_cost, memory_cost=memory_kib, parallelism=parallelism,
        hash_len=KEY_LEN, type=Type.ID,
    )


def derive_new(password: str):
    """Fresh salt + default Argon2id params + derived key (new or migrated vault)."""
    salt = os.urandom(16)
    params = {"time": ARGON_TIME, "memory": ARGON_MEMORY_KIB, "parallel": ARGON_PARALLELISM}
    key = _argon2_key(password, salt, params["time"], params["memory"], params["parallel"])
    return key, salt, params


def encrypt_with_key(data: bytes, key: bytes, salt: bytes, params: dict) -> bytes:
    """Encrypts with an already-derived key (fresh GCM nonce each call)."""
    nonce = os.urandom(12)
    ciphertext = AESGCM(key).encrypt(nonce, data, None)
    header = (MAGIC
              + bytes([params["time"]])
              + int(params["memory"]).to_bytes(4, "big")
              + bytes([params["parallel"]])
              + salt)
    return header + nonce + ciphertext


def open_vault(blob: bytes, password: str):
    """Decrypts a vault blob.

    Returns (payload, key, salt, params) where key/salt/params are what to use
    for *future* saves. For a legacy (v1) blob this returns freshly derived
    Argon2id material, so the next save migrates the file to v2.
    """
    if blob[:4] == MAGIC:
        i = 4
        time_cost = blob[i]; i += 1
        memory_kib = int.from_bytes(blob[i:i + 4], "big"); i += 4
        parallelism = blob[i]; i += 1
        salt = blob[i:i + 16]; i += 16
        nonce = blob[i:i + 12]; i += 12
        ciphertext = blob[i:]
        params = {"time": time_cost, "memory": memory_kib, "parallel": parallelism}
        key = _argon2_key(password, salt, time_cost, memory_kib, parallelism)
        payload = AESGCM(key).decrypt(nonce, ciphertext, None)
        return payload, key, salt, params

    # Legacy v1: salt(16) | nonce(12) | ciphertext, PBKDF2-HMAC-SHA256.
    salt, nonce, ciphertext = blob[:16], blob[16:28], blob[28:]
    legacy_key = PBKDF2HMAC(algorithm=hashes.SHA256(), length=KEY_LEN,
                            salt=salt, iterations=LEGACY_ITERATIONS).derive(password.encode("utf-8"))
    payload = AESGCM(legacy_key).decrypt(nonce, ciphertext, None)
    key, new_salt, params = derive_new(password)  # migrate on next save
    return payload, key, new_salt, params


# --- Legacy helpers kept for the CLI (app.py) ---
def derive_key(password: str, salt: bytes) -> bytes:
    return PBKDF2HMAC(algorithm=hashes.SHA256(), length=KEY_LEN,
                      salt=salt, iterations=LEGACY_ITERATIONS).derive(password.encode())


def encrypt_data(data: bytes, password: str) -> bytes:
    salt = os.urandom(16)
    nonce = os.urandom(12)
    ciphertext = AESGCM(derive_key(password, salt)).encrypt(nonce, data, None)
    return salt + nonce + ciphertext


def decrypt_data(encrypted_blob: bytes, password: str) -> bytes:
    salt, nonce, ciphertext = encrypted_blob[:16], encrypted_blob[16:28], encrypted_blob[28:]
    return AESGCM(derive_key(password, salt)).decrypt(nonce, ciphertext, None)
