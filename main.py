from UI.gui_app import PasswordManagerGUI
from core.single_instance import try_signal_focus
import sys
import os

# Redirect errors to a log file in the app's directory
if hasattr(sys, 'frozen') or '__compiled__' in globals():
    log_path = os.path.join(os.path.dirname(sys.executable), "debug_log.txt")
    sys.stdout = open(log_path, "w")
    sys.stderr = sys.stdout

if __name__ == "__main__":
    # If another instance is already running (e.g. in the tray), focus it
    # instead of opening a duplicate. Handles securevault:// re-launches.
    if try_signal_focus():
        sys.exit(0)
    app = PasswordManagerGUI()
    app.start_control_server()
    app.mainloop()