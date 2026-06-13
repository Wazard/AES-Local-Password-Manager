"""A tiny, authenticated localhost HTTP server that lets a paired browser
extension request credentials for the current site.

Security model (MVP):
  * Binds to 127.0.0.1 only.
  * Every request must carry the pairing token in the `X-Vault-Token` header.
    The token is a shared secret the user copies into the extension once.
  * Requests whose `Origin` is a real web page (http/https) are rejected, so a
    malicious site cannot reach the API even if it learns the port.
  * Credentials are only returned while the vault is unlocked.

Built on the standard library so the frozen build needs no extra packages.
"""
import hmac
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs


class _Handler(BaseHTTPRequestHandler):
    # Silence the default stderr request logging.
    def log_message(self, *args):
        pass

    @property
    def _ctx(self):
        return self.server.ctx

    def _send(self, code, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _authorized(self):
        # Block real web origins outright; allow extension / no-origin callers.
        origin = self.headers.get("Origin", "")
        if origin.startswith("http://") or origin.startswith("https://"):
            return False
        token = self.headers.get("X-Vault-Token", "")
        return bool(self._ctx.token) and hmac.compare_digest(token, self._ctx.token)

    def do_GET(self):
        parsed = urlparse(self.path)

        if not self._authorized():
            return self._send(401, {"error": "unauthorized"})

        if parsed.path == "/status":
            return self._send(200, {"unlocked": bool(self._ctx.is_unlocked())})

        if parsed.path == "/credentials":
            if not self._ctx.is_unlocked():
                return self._send(423, {"error": "locked"})
            domain = (parse_qs(parsed.query).get("domain", [""])[0] or "").lower()
            return self._send(200, {"matches": self._ctx.lookup(domain)})

        return self._send(404, {"error": "not found"})

    def do_POST(self):
        if not self._authorized():
            return self._send(401, {"error": "unauthorized"})
        if urlparse(self.path).path == "/save":
            if not self._ctx.is_unlocked():
                return self._send(423, {"error": "locked"})
            length = int(self.headers.get("Content-Length", 0) or 0)
            try:
                data = json.loads(self.rfile.read(length) or b"{}")
            except Exception:
                return self._send(400, {"error": "bad json"})
            ok = self._ctx.add_entry(data)
            return self._send(200 if ok else 409, {"saved": bool(ok)})
        return self._send(404, {"error": "not found"})


class AutofillServer:
    def __init__(self, host, port, token, is_unlocked, lookup, add_entry):
        self.host = host
        self.port = port
        self.token = token
        self.is_unlocked = is_unlocked   # callable() -> bool
        self.lookup = lookup             # callable(domain) -> list[dict]
        self.add_entry = add_entry       # callable(dict) -> bool
        self._httpd = None
        self._thread = None

    def start(self):
        if self._httpd is not None:
            return
        self._httpd = ThreadingHTTPServer((self.host, self.port), _Handler)
        self._httpd.ctx = self
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()

    def stop(self):
        if self._httpd is not None:
            try:
                self._httpd.shutdown()
                self._httpd.server_close()
            except Exception:
                pass
            self._httpd = None
            self._thread = None

    @property
    def running(self):
        return self._httpd is not None
