"""Best-effort tamper tripwire.

Detects a debugger attached to our own process (in-process or remote, e.g.
x64dbg / WinDbg attaching). This is a deterrent, not a guarantee: it does not
detect plain memory reads, and a determined attacker with code execution can
patch it out. It exists so the app can lock the moment something obvious starts
inspecting it.
"""
import ctypes


def debugger_attached():
    try:
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.IsDebuggerPresent.restype = ctypes.c_int
        if k32.IsDebuggerPresent():
            return True
        k32.GetCurrentProcess.restype = ctypes.c_void_p
        k32.CheckRemoteDebuggerPresent.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int)]
        present = ctypes.c_int(0)
        k32.CheckRemoteDebuggerPresent(k32.GetCurrentProcess(), ctypes.byref(present))
        return bool(present.value)
    except Exception:
        return False
