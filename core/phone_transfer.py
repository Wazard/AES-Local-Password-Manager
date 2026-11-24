"""Sending the vault file to the phone app (iOS or Android) over the local network.

The phone, on its "Connect to PC" screen, listens on TCP port PORT,
announces itself over Bonjour as SERVICE, and shows a 6-digit code. This side
finds it and sends one message:

    b"SVX1" | name length (1) | this PC's name (UTF-8) | vault size (4, big-endian)
            | vault bytes | HMAC-SHA256(key = the code, message = everything before)

The phone answers with one line: b"OK\\n", or b"ERR <reason>\\n" where reason is
one of badcode, toolarge, notvault, protocol.

Syncing uses the same framing on one connection, three messages:

    PC -> phone  b"SVY1", empty payload            "send me your vault"
    phone -> PC  b"SVY2", the phone's vault file   (or an ERR line: badcode,
                                                    locked, novault)
    PC -> phone  b"SVY3", the merged vault file    -> phone answers OK / ERR

The PC opens the phone's vault with its own key (same master password and
salt — the phone's copy came from this PC), applies the changes the phone
marked as not yet synced (see data_handler.merge_phone_changes), saves, and
sends the result back, so both sides end up with the same file.

Finding phones: the Bonjour query below, and, because a phone can't always
announce itself (inside LiveContainer iOS refuses; some Android builds don't
answer the kind of query sent here), a probe of PORT on every address of the
local /24 networks. The probe sends HELLO and the phone answers one line,
b"HELLO <its name>\\n" — older apps answer b"ERR protocol\\n", which still
says a Secure Vault phone is listening there.

What travels is the vault file exactly as it is on disk — already encrypted
with the master password — so nothing here ever sees vault contents. The code
proves the file came from the PC the user is standing at: without it the phone
refuses the file, and after a few wrong codes it stops listening. Someone on
the same network could still record the encrypted file in transit, which is
the same exposure as keeping it in a cloud folder.
"""
import hashlib
import hmac
import ipaddress
import random
import select
import socket
import struct
import time
from concurrent.futures import ThreadPoolExecutor

PORT = 53917
SERVICE = "_securevault._tcp.local"
MAGIC = b"SVX1"
HELLO = b"SVH1"
MAX_SIZE = 16 * 1024 * 1024

_MDNS = ("224.0.0.251", 5353)
_PTR, _A, _SRV = 12, 1, 33


# --------------------------------------------------------------------------
# Sending
# --------------------------------------------------------------------------
SYNC_REQUEST, SYNC_VAULT, SYNC_MERGED = b"SVY1", b"SVY2", b"SVY3"


class TransferError(Exception):
    """`reason` is one of the phone's ERR reasons, or protocol / noreply."""

    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


def build_frame(kind: bytes, payload: bytes, code: str, sender: str) -> bytes:
    name = sender.encode("utf-8")[:255]
    body = kind + bytes([len(name)]) + name + struct.pack(">I", len(payload)) + payload
    return body + hmac.new(code.encode("ascii"), body, hashlib.sha256).digest()


def build_message(vault: bytes, code: str, sender: str) -> bytes:
    return build_frame(MAGIC, vault, code, sender)


def parse_frame(data: bytes, kind: bytes, code: str):
    """(sender, payload) from one complete frame, checked against the code."""
    if len(data) < 9 + 32 or data[:4] != kind:
        raise TransferError("protocol")
    n = data[4]
    size = struct.unpack(">I", data[5 + n:9 + n])[0]
    end = 9 + n + size
    if len(data) != end + 32:
        raise TransferError("protocol")
    mac = hmac.new(code.encode("ascii"), data[:end], hashlib.sha256).digest()
    if not hmac.compare_digest(mac, data[end:]):
        raise TransferError("badcode")
    return data[5:5 + n].decode("utf-8", "replace"), data[9 + n:end]


def _recv_exact(s, count):
    out = b""
    while len(out) < count:
        chunk = s.recv(min(65536, count - len(out)))
        if not chunk:
            raise TransferError("noreply")
        out += chunk
    return out


def _read_frame(s, kind: bytes, code: str):
    """Read one frame of `kind`, or turn the phone's ERR line into an error."""
    head = _recv_exact(s, 4)
    if head == b"ERR ":
        line = b""
        while not line.endswith(b"\n") and len(line) < 64:
            line += _recv_exact(s, 1)
        raise TransferError(line.decode("ascii", "replace").strip() or "protocol")
    rest = _recv_exact(s, 1)
    n = rest[0]
    name_and_size = _recv_exact(s, n + 4)
    size = struct.unpack(">I", name_and_size[n:])[0]
    if size > MAX_SIZE:
        raise TransferError("toolarge")
    data = head + rest + name_and_size + _recv_exact(s, size + 32)
    return parse_frame(data, kind, code)


def sync(host: str, code: str, merge, sender: str = None,
         port: int = PORT, timeout: float = 20.0):
    """Sync with the phone at `host`.

    `merge(phone_vault_bytes)` applies the phone's changes to this PC's vault
    and returns the merged vault bytes to send back; it may raise
    TransferError (e.g. "mismatch" when the vaults have different keys).
    Returns (result, phone_name): result is "ok", one of the phone's reasons,
    "unreachable", "noreply", "protocol" or whatever `merge` raised."""
    sender = sender or socket.gethostname()
    try:
        s = socket.create_connection((host, port), timeout=timeout)
    except OSError:
        return "unreachable", ""
    phone = ""
    try:
        with s:
            s.sendall(build_frame(SYNC_REQUEST, b"", code, sender))
            phone, phone_vault = _read_frame(s, SYNC_VAULT, code)
            merged = merge(phone_vault)
            s.sendall(build_frame(SYNC_MERGED, merged, code, sender))
            reply = b""
            while not reply.endswith(b"\n") and len(reply) < 64:
                chunk = s.recv(64)
                if not chunk:
                    break
                reply += chunk
    except TransferError as e:
        return e.reason, phone
    except OSError:
        return "noreply", phone
    reply = reply.decode("ascii", "replace").strip()
    if reply == "OK":
        return "ok", phone
    return (reply[4:].strip() or "protocol") if reply.startswith("ERR ") else "noreply", phone


def send(host: str, vault: bytes, code: str, sender: str = None,
         port: int = PORT, timeout: float = 15.0) -> str:
    """Send the vault to the phone at `host`. Returns "ok", one of the
    phone's reasons (badcode, toolarge, notvault, protocol), "unreachable" if
    no connection could be made, or "noreply" if the phone didn't answer."""
    if len(vault) > MAX_SIZE:
        return "toolarge"
    message = build_message(vault, code, sender or socket.gethostname())
    try:
        s = socket.create_connection((host, port), timeout=timeout)
    except OSError:
        return "unreachable"
    reply = b""
    try:
        with s:
            s.sendall(message)
            while not reply.endswith(b"\n") and len(reply) < 64:
                chunk = s.recv(64)
                if not chunk:
                    break
                reply += chunk
    except OSError:
        return "noreply"
    reply = reply.decode("ascii", "replace").strip()
    if reply == "OK":
        return "ok"
    if reply.startswith("ERR "):
        return reply[4:].strip() or "protocol"
    return "noreply"


# --------------------------------------------------------------------------
# Finding phones
# --------------------------------------------------------------------------
def discover(timeout: float = 1.5) -> list:
    """Phones currently showing the Connect to PC screen, as
    [{"name": ..., "host": ..., "port": ...}]; "name" is empty when the phone
    was found by the probe but runs an app too old to say its name.

    Bonjour and the network probe run at the same time; a phone both find is
    listed once, under its Bonjour name. An empty list just means nothing
    answered; the user can still type the phone's address."""
    with ThreadPoolExecutor(max_workers=1) as pool:
        probed = pool.submit(_probe_subnets)
        found = {d["host"]: d for d in _discover_bonjour(timeout)}
        for device in probed.result():
            found.setdefault(device["host"], device)
    return sorted(found.values(), key=lambda d: (not d["name"], d["name"].lower(), d["host"]))


def _probe_subnets(port: int = PORT, timeout: float = 1.0) -> list:
    """Every address on this PC's private /24 networks that answers HELLO.

    Plain outgoing TCP connections, so the firewall doesn't get involved.
    Addresses with nothing behind them fail after `timeout`; the probes run
    in parallel, so a whole /24 takes about two timeouts."""
    targets = []
    for ip in _local_ipv4s():
        addr = ipaddress.ip_address(ip)
        if not addr.is_private or addr.is_link_local or addr.is_loopback:
            continue
        net = ipaddress.ip_network(ip + "/24", strict=False)
        targets += [str(h) for h in net.hosts() if str(h) != ip]
    targets = list(dict.fromkeys(targets))[:4 * 254]   # at most four networks
    if not targets:
        return []
    with ThreadPoolExecutor(max_workers=min(160, len(targets))) as pool:
        results = pool.map(lambda h: probe(h, port, timeout), targets)
        return [r for r in results if r]


def probe(host: str, port: int = PORT, timeout: float = 1.0):
    """{"name", "host", "port"} if a phone app is listening at host:port, else None."""
    try:
        with socket.create_connection((host, port), timeout=timeout) as s:
            s.settimeout(1.5)
            s.sendall(HELLO)
            reply = b""
            while not reply.endswith(b"\n") and len(reply) < 320:
                chunk = s.recv(320)
                if not chunk:
                    break
                reply += chunk
    except OSError:
        return None
    line = reply.decode("utf-8", "replace").strip()
    if line.startswith("HELLO"):
        return {"name": line[5:].strip(), "host": host, "port": port}
    if line.startswith("ERR "):   # an app from before HELLO: listening, but nameless
        return {"name": "", "host": host, "port": port}
    return None


def _discover_bonjour(timeout: float) -> list:
    """Sends a one-shot mDNS query from an ordinary port on every local
    interface. Responders answer such "legacy unicast" queries straight back
    to the asking port (RFC 6762 §6.7), so nothing has to listen on 5353 and
    Windows Firewall has no reason to prompt."""
    query_id = random.randint(1, 0xFFFF)
    query = (struct.pack(">HHHHHH", query_id, 0, 1, 0, 0, 0)
             + _encode_name(SERVICE) + struct.pack(">HH", _PTR, 1))
    sockets = []
    for ip in _local_ipv4s():
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.bind((ip, 0))
            s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(ip))
            s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 255)
            s.sendto(query, _MDNS)
            sockets.append(s)
        except OSError:
            continue

    records = {"ptr": [], "srv": {}, "a": {}}
    try:
        deadline = time.monotonic() + timeout
        while sockets:
            left = deadline - time.monotonic()
            if left <= 0:
                break
            ready, _, _ = select.select(sockets, [], [], left)
            for s in ready:
                try:
                    data, (sender_ip, _) = s.recvfrom(9000)
                    _parse_response(data, records, sender_ip)
                except (OSError, ValueError, IndexError, struct.error):
                    continue
    finally:
        for s in sockets:
            s.close()

    found = {}
    for instance in records["ptr"]:
        srv = records["srv"].get(instance.lower())
        if not srv:
            continue
        target, port, sender_ip = srv
        host = records["a"].get(target.lower()) or sender_ip
        label = instance[:-len(SERVICE) - 1] if instance.lower().endswith("." + SERVICE.lower()) else instance
        found[(host, port)] = {"name": label, "host": host, "port": port}
    return list(found.values())


def _local_ipv4s():
    ips = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.add(info[4][0])
    except OSError:
        pass
    try:  # the interface the default route uses (no packet is sent)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("192.0.2.1", 9))
            ips.add(s.getsockname()[0])
    except OSError:
        pass
    return sorted(ip for ip in ips if not ip.startswith(("127.", "169.254.")))


def _encode_name(name):
    out = b""
    for label in name.strip(".").split("."):
        raw = label.encode("utf-8")
        out += bytes([len(raw)]) + raw
    return out + b"\x00"


def _read_name(data, offset):
    """A possibly-compressed DNS name. Returns (name, offset after it)."""
    labels, jumped, end, hops = [], False, offset, 0
    while True:
        length = data[offset]
        if length & 0xC0 == 0xC0:
            if not jumped:
                end = offset + 2
            offset = ((length & 0x3F) << 8) | data[offset + 1]
            jumped = True
            hops += 1
            if hops > 20:
                raise ValueError("name loop")
            continue
        offset += 1
        if length == 0:
            break
        labels.append(data[offset:offset + length].decode("utf-8", "replace"))
        offset += length
    return ".".join(labels), (end if jumped else offset)


def _parse_response(data, records, sender_ip):
    _id, flags, qd, an, ns, ar = struct.unpack(">HHHHHH", data[:12])
    if not flags & 0x8000:
        return  # a query, not an answer
    offset = 12
    for _ in range(qd):
        _, offset = _read_name(data, offset)
        offset += 4
    for _ in range(an + ns + ar):
        name, offset = _read_name(data, offset)
        rtype, _rclass, _ttl, rdlen = struct.unpack(">HHIH", data[offset:offset + 10])
        offset += 10
        rdata = offset
        offset += rdlen
        if rtype == _PTR and name.lower() == SERVICE.lower():
            instance, _ = _read_name(data, rdata)
            if instance not in records["ptr"]:
                records["ptr"].append(instance)
        elif rtype == _SRV:
            _prio, _weight, port = struct.unpack(">HHH", data[rdata:rdata + 6])
            target, _ = _read_name(data, rdata + 6)
            records["srv"][name.lower()] = (target, port, sender_ip)
        elif rtype == _A and rdlen == 4:
            records["a"][name.lower()] = socket.inet_ntoa(data[rdata:rdata + 4])
