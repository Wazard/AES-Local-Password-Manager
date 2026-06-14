"""Register a per-user `securevault://` URL protocol so the browser extension
can launch / focus the app. Writes only to HKCU (no admin required)."""
import os
import sys

PROTOCOL = "securevault"
_BASE = r"Software\Classes\\" + PROTOCOL
_CMD_KEY = _BASE + r"\shell\open\command"


def _launch_command():
    """The command Windows runs for securevault:// links (with the URL as %1)."""
    if getattr(sys, "frozen", False) or "__compiled__" in globals():
        return f'"{sys.executable}" "%1"'
    main_py = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "main.py"))
    return f'"{sys.executable}" "{main_py}" "%1"'


def is_registered():
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _CMD_KEY) as k:
            return bool(winreg.QueryValueEx(k, "")[0])
    except OSError:
        return False


def register():
    import winreg
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _BASE) as k:
        winreg.SetValueEx(k, "", 0, winreg.REG_SZ, "URL:Secure Vault Protocol")
        winreg.SetValueEx(k, "URL Protocol", 0, winreg.REG_SZ, "")
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _CMD_KEY) as k:
        winreg.SetValueEx(k, "", 0, winreg.REG_SZ, _launch_command())
    return True


def unregister():
    import winreg
    for sub in (_CMD_KEY, _BASE + r"\shell\open", _BASE + r"\shell", _BASE):
        try:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, sub)
        except OSError:
            pass
    return True
