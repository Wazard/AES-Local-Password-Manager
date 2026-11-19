"""Sending the vault file to the iOS app over the local network.

The iPhone, on its "Receive from PC" screen, listens on TCP port PORT,
announces itself over Bonjour as SERVICE, and shows a 6-digit code. This side
finds it and sends one message:

    b"SVX1" | name length (1) | this PC's name (UTF-8) | vault size (4, big-endian)
            | vault bytes | HMAC-SHA256(key = the code, message = everything before)

The phone answers with one line: b"OK\\n", or b"ERR <reason>\\n" where reason is
one of badcode, toolarge, notvault, protocol.

What travels is the vault file exactly as it is on disk — already encrypted
with the master password — so nothing here ever sees vault contents. The code
proves the file came from the PC the user is standing at: without it the phone
refuses the file, and after a few wrong codes it stops listening. Someone on
the same network could still record the encrypted file in transit, which is
the same exposure as keeping it in a cloud folder.
"""
import hashlib
import hmac
import random
import select
import socket
import struct
import time

PORT = 53917
SERVICE = "_securevault._tcp.local"
MAGIC = b"SVX1"
MAX_SIZE = 16 * 1024 * 1024

_MDNS = ("224.0.0.251", 5353)
_PTR, _A, _SRV = 12, 1, 33


# --------------------------------------------------------------------------
# Sending
# --------------------------------------------------------------------------
def build_message(vault: bytes, code: str, sender: str) -> bytes:
    name = sender.encode("utf-8")[:255]
    body = MAGIC + bytes([len(name)]) + name + struct.pack(">I", len(vault)) + vault
    return body + hmac.new(code.encode("ascii"), body, hashlib.sha256).digest()


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
# Finding iPhones (Bonjour, without a dependency)
# --------------------------------------------------------------------------
def discover(timeout: float = 1.5) -> list:
    """iPhones currently showing the Receive screen, as
    [{"name": ..., "host": ..., "port": ...}].

    Sends a one-shot mDNS query from an ordinary port on every local
    interface. Responders answer such "legacy unicast" queries straight back
    to the asking port (RFC 6762 §6.7), so nothing has to listen on 5353 and
    Windows Firewall has no reason to prompt. An empty list just means
    nothing answered; the user can still type the phone's address."""
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
    return sorted(found.values(), key=lambda d: d["name"].lower())


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
