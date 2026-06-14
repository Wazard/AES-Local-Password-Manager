import sys
import time
import ctypes
from ctypes import wintypes

pid = int(sys.argv[1])
secs = float(sys.argv[2]) if len(sys.argv) > 2 else 5.0
k = ctypes.WinDLL("kernel32", use_last_error=True)


class DEBUG_EVENT(ctypes.Structure):
    _fields_ = [
        ("dwDebugEventCode", wintypes.DWORD),
        ("dwProcessId", wintypes.DWORD),
        ("dwThreadId", wintypes.DWORD),
        ("u", ctypes.c_byte * 1024),
    ]


DBG_CONTINUE = 0x00010002
k.DebugActiveProcess.argtypes = [wintypes.DWORD]
if not k.DebugActiveProcess(pid):
    print("DebugActiveProcess failed, err", ctypes.get_last_error())
    sys.exit(1)
print("attached to", pid, flush=True)
try:
    k.DebugSetProcessKillOnExit(False)
except Exception:
    pass

ev = DEBUG_EVENT()
end = time.time() + secs
while time.time() < end:
    if k.WaitForDebugEvent(ctypes.byref(ev), 200):
        k.ContinueDebugEvent(ev.dwProcessId, ev.dwThreadId, DBG_CONTINUE)

k.DebugActiveProcessStop.argtypes = [wintypes.DWORD]
k.DebugActiveProcessStop(pid)
print("detached", flush=True)
