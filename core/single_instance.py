"""Single-instance control channel.

The app listens on a localhost control port. A second launch (e.g. from a
securevault:// link while the app is already running/in the tray) detects the
running instance, tells it to focus, and exits — instead of opening a duplicate.

A handshake banner is used so we don't mistake some other service on the port
for our own instance.
"""
import socket
import threading

CONTROL_HOST = "127.0.0.1"
CONTROL_PORT = 8766
BANNER = b"SECUREVAULT\n"
FOCUS = b"FOCUS\n"


def try_signal_focus(timeout=0.6):
    """Returns True if a running instance was found and told to focus."""
    try:
        with socket.create_connection((CONTROL_HOST, CONTROL_PORT), timeout=timeout) as s:
            s.settimeout(timeout)
            hello = s.recv(len(BANNER))
            if not hello.startswith(b"SECUREVAULT"):
                return False  # something else is on this port
            s.sendall(FOCUS)
            return True
    except OSError:
        return False


class ControlServer:
    def __init__(self, on_focus):
        self.on_focus = on_focus
        self._sock = None
        self._thread = None

    def start(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind((CONTROL_HOST, CONTROL_PORT))  # no SO_REUSEADDR: detect duplicates
        s.listen(5)
        self._sock = s
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def _serve(self):
        while self._sock is not None:
            try:
                conn, _ = self._sock.accept()
            except OSError:
                break
            with conn:
                try:
                    conn.sendall(BANNER)
                    if conn.recv(16).strip() == b"FOCUS":
                        self.on_focus()
                except OSError:
                    pass

    def stop(self):
        s, self._sock = self._sock, None
        if s is not None:
            try:
                s.close()
            except OSError:
                pass
