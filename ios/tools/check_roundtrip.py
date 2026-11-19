"""Opens a vault the iOS unit tests wrote, using the desktop app's code.

CI runs this after the tests: if it passes, the PC app can read what the
phone saves. Usage:  python ios/tools/check_roundtrip.py <roundtrip.pwmanager>
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from core import encryption, storage_compression  # noqa: E402


def main(path):
    with open(os.path.join(ROOT, "ios", "SecureVaultTests", "Fixtures", "expected.json"), encoding="utf-8") as f:
        expected = json.load(f)
    with open(path, "rb") as f:
        blob = f.read()
    payload, _key, _salt, params = encryption.open_vault(blob, expected["password"])
    vault = json.loads(storage_compression.decompress_data(payload))

    assert list(vault) == expected["order"] + ["Added on iOS"], list(vault)
    for name, want in expected["entries"].items():
        got = vault[name]
        for field in ("user", "pass"):
            assert got[field] == want[field], (name, field, got[field])
        if "created" in want:
            assert abs(got["created"] - want["created"]) < 1e-6, (name, got["created"])
    assert vault["Bank"]["future_field"] == [1, "two", None]
    added = vault["Added on iOS"]
    assert added["pass"] == "from-the-phone" and added["favourite"] is False
    assert isinstance(added["created"], float)
    assert params == {"time": 3, "memory": 65536, "parallel": 4}, params
    print("OK: the desktop code reads the vault written on iOS (%d entries)" % len(vault))


if __name__ == "__main__":
    main(sys.argv[1])
