"""Checks the phone's side of syncing with the desktop's code.

CI runs it after the iOS and the Android unit tests, on files they exported:
  sync_reply.bin             the SVY2 reply the phone builds
  sync_phone_vault.pwmanager a vault with every kind of change marked
The marked vault is merged into the fixture vault by the desktop's own
data_handler.merge_phone_changes, and the result is checked.

Usage, from the repository root:
    python ios/tools/check_sync.py <export dir> [added entry name] [phone name]
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from core import data_handler, encryption, phone_transfer, storage_compression  # noqa: E402

FIXTURES = os.path.join(ROOT, "ios", "SecureVaultTests", "Fixtures")


def read(*parts):
    with open(os.path.join(*parts), "rb") as f:
        return f.read()


def open_vault(blob, password):
    payload, *_ = encryption.open_vault(blob, password)
    return json.loads(storage_compression.decompress_data(payload))


def main(export_dir, added="Added on iOS", phone_name="Test iPhone"):
    with open(os.path.join(FIXTURES, "expected.json"), encoding="utf-8") as f:
        password = json.load(f)["password"]
    pc_blob = read(FIXTURES, "vault_v2.bin")

    sender, payload = phone_transfer.parse_frame(
        read(export_dir, "sync_reply.bin"), phone_transfer.SYNC_VAULT, "123456")
    assert sender == phone_name, sender
    assert payload == pc_blob, "SVY2 payload differs from the vault it carried"

    phone_blob = read(export_dir, "sync_phone_vault.pwmanager")
    # The PC opens the phone's copy with its own key, as the app does.
    _payload, key, salt, params = encryption.open_vault(pc_blob, password)
    phone = json.loads(storage_compression.decompress_data(
        encryption.open_with_key(phone_blob, key, salt, params)))

    pc = open_vault(pc_blob, password)
    report = data_handler.merge_phone_changes(pc, phone)
    assert report == {"added": [added], "changed": ["GitHub", "Legacy Renamed"],
                      "deleted": ["Bank"]}, report
    assert list(pc) == ["GitHub", "Café ☕", "Legacy Renamed", added], list(pc)
    assert pc["GitHub"]["user"] == "octo-new"
    assert pc["Legacy Renamed"]["pass"] == "legacy-pw"
    assert pc[added]["pass"] == "new-pw" and pc[added]["favourite"] is True
    for name, entry in pc.items():
        assert not ({"sync_pending", "sync_renamed_from"} & set(entry)), (name, entry)
    print("OK: the desktop applies the phone's marked changes (%s)" %
          ", ".join("%d %s" % (len(v), k) for k, v in report.items()))


if __name__ == "__main__":
    main(*sys.argv[1:4])
