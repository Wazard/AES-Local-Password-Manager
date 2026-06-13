"""Per-session in-memory encryption for secrets.

The decrypted vault would otherwise sit in process memory as plaintext for the
whole session. Instead we keep each password encrypted with a key that is
generated fresh every session (every login) and only ever decrypt a single
password at the moment it is actually needed (display, copy, autofill, save).

This is defence-in-depth: an attacker who can fully read the process memory can
still recover the key, but casual scraping of plaintext passwords is prevented
and plaintext exists only transiently.
"""
from cryptography.fernet import Fernet


class SessionCrypto:
    def __init__(self):
        self._fernet = Fernet(Fernet.generate_key())

    def rotate(self):
        """Generate a brand-new session key (call on each login)."""
        self._fernet = Fernet(Fernet.generate_key())

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt((plaintext or "").encode("utf-8")).decode("ascii")

    def decrypt(self, token: str) -> str:
        if not token:
            return ""
        return self._fernet.decrypt(token.encode("ascii")).decode("utf-8")
