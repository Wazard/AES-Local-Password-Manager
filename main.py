from UI.gui_app import PasswordManagerGUI
from core.single_instance import already_running, signal_focus
from core import paths
import sys
import os

# Bring forward any vault/config that predates the per-user data location.
paths.migrate_legacy(["vault.pwmanager", "extension_config.json"])

# Redirect errors to a log file in the writable per-user data dir.
if hasattr(sys, 'frozen') or '__compiled__' in globals():
    log_path = os.path.join(paths.data_dir(), "debug_log.txt")
    sys.stdout = open(log_path, "w")
    sys.stderr = sys.stdout

if __name__ == "__main__":
    # If another instance is already running (e.g. in the tray), bring it to the
    # front instead of opening a duplicate (which would also collide on the
    # autofill port). Detection is mutex-based; focus is best-effort.
    if already_running():
        signal_focus()
        sys.exit(0)
    app = PasswordManagerGUI()
    app.start_control_server()
    app.mainloop()
