from UI.gui_app import PasswordManagerGUI
import sys
import os

# Redirect errors to a log file in the app's directory
if hasattr(sys, 'frozen') or '__compiled__' in globals():
    log_path = os.path.join(os.path.dirname(sys.executable), "debug_log.txt")
    sys.stdout = open(log_path, "w")
    sys.stderr = sys.stdout

if __name__ == "__main__":
    app = PasswordManagerGUI()
    app.mainloop()