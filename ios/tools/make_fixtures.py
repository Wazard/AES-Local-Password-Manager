"""Writes the vaults the iOS unit tests open, using the desktop app's own code.

Run from the repository root:  python ios/tools/make_fixtures.py
The tests then prove the iOS app reads exactly what the desktop writes.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from core import encryption, phone_transfer, storage_compression  # noqa: E402

PASSWORD = "correct horse battery staple"
OUT = os.path.join(ROOT, "ios", "SecureVaultTests", "Fixtures")

# Insertion order matters (it drives the oldest/newest sorts), so it is part
# of what the tests check. "Café ☕" exercises json's \u escapes, including a
# surrogate pair; "Legacy" has no "created", like entries from old versions.
VAULT = {
    "GitHub": {"user": "octo", "pass": "gh-Pa55-word", "url": "github.com",
               "created": 1731000000.123456, "favourite": True},
    "Café ☕": {"user": "barista@example.com", "pass": "ünïcødé \"quoted\" \ back",
               "url": "", "created": 1731000100.5, "favourite": False},
    "Legacy": {"user": "old", "pass": "legacy-pw"},
    "Bank": {"user": "me", "pass": "", "url": "https://bank.example",
             "created": 1731000200, "favourite": False, "future_field": [1, "two", None]},
}


def write(name, blob):
    with open(os.path.join(OUT, name), "wb") as f:
        f.write(blob)


def main():
    os.makedirs(OUT, exist_ok=True)
    payload = storage_compression.compress_data(json.dumps(VAULT))
    key, salt, params = encryption.derive_new(PASSWORD)
    v2 = encryption.encrypt_with_key(payload, key, salt, params)
    write("vault_v2.bin", v2)
    # What "Send to iPhone" puts on the wire for that vault, with code 123456.
    write("transfer_frame.bin", phone_transfer.build_message(v2, "123456", "TEST-PC ☕"))
    write("vault_v1.bin", encryption.encrypt_data(payload, PASSWORD))
    with open(os.path.join(OUT, "expected.json"), "w", encoding="utf-8") as f:
        json.dump({"password": PASSWORD, "order": list(VAULT),
                   "entries": VAULT}, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
