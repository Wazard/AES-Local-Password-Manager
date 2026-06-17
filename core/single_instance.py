"""Single-instance detection + focus channel.

Detection uses a named mutex (reliable: the OS releases it the moment the
owning process exits, so a crashed/leftover process can't block or be missed).
Focusing the existing window uses a small localhost socket.

A second launch (e.g. a double-click or securevault:// link while the app is in
the tray) detects the running instance, asks it to come to the front, and exits
instead of opening a duplicate (which would also collide on the autofill port).
"""
import socket
import threading
import ctypes
from ctypes import wintypes

CONTROL_HOST = "127.0.0.1"
CONTROL_PORT = 8766
BANNER = b"SECUREVAULT\n"
FOCUS = b"FOCUS\n"

_MUTEX_NAME = "Local\\SecureVault_SingleInstance"
_ERROR_ALREADY_EXISTS = 183
_mutex_handle = None  # kept for the process lifetime so the mutex isn't released


def already_running():
    """True if another instance of this app already holds the singleton mutex."""
    global _mutex_handle
    try:
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.CreateMutexW.restype = wintypes.HANDLE
        k32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
        _mutex_handle = k32.CreateMutexW(None, False, _MUTEX_NAME)
        return ctypes.get_last_error() == _ERROR_ALREADY_EXISTS
    except Exception:
        return False


def signal_focus(timeout=1.0):
    """Best-effort: tell the running instance to restore/focus its window."""
    try:
        with socket.create_connection((CONTROL_HOST, CONTROL_PORT), timeout=timeout) as s:
            s.settimeout(timeout)
            hello = s.recv(len(BANNER))
            if not hello.startswith(b"SECUREVAULT"):
                return False
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
