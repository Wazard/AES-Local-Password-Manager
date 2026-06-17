"""Windows UAC elevation helper.

Used for the one privileged operation in the app — creating/removing the
backup symlink. We elevate the system `cmd.exe` (running `mklink`/`del`) rather
than relaunching our own binary, which fires the UAC prompt reliably in both the
dev script and the compiled (Nuitka onefile) build.
"""
import os
import ctypes


def is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def run_elevated_cmd(command):
    """Run a cmd.exe command elevated (shows the 'allow changes?' UAC prompt).
    Returns True if the elevated process started (i.e. the user accepted)."""
    try:
        comspec = os.environ.get("ComSpec", "cmd.exe")
        shell_execute = ctypes.windll.shell32.ShellExecuteW
        shell_execute.restype = ctypes.c_void_p
        rc = shell_execute(None, "runas", comspec, "/c " + command, None, 0)
        return int(rc or 0) > 32
    except Exception:
        return False
