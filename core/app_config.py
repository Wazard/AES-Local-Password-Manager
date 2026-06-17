"""Small non-secret app config (browser-extension pairing token, port, toggle).

Stored as plain JSON next to the executable — it holds no vault data, only the
extension pairing token and preferences. Lives beside `vault.pwmanager`.
"""
import os
import json
import secrets
from core import paths

CONFIG_FILE = os.path.join(paths.data_dir(), "extension_config.json")
DEFAULT_PORT = 8765


def load():
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save(cfg):
    tmp = CONFIG_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
    os.replace(tmp, CONFIG_FILE)


def get_or_create_token(cfg):
    """Returns the pairing token, generating and persisting one if absent."""
    if not cfg.get("token"):
        cfg["token"] = secrets.token_hex(16)
        save(cfg)
    return cfg["token"]
