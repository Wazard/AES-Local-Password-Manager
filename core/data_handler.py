import re
import unicodedata


def ordered_services(vault_data: dict, sort_mode: str = "name_asc") -> list:
    """
    Returns every service name in the requested order.

    Time ordering uses the vault's natural insertion order (oldest-first by
    design) rather than the "created" timestamp, which is missing on legacy
    entries. "time_new" simply inverts that order.

    Favourited entries are always grouped first, keeping their relative order
    from the chosen sort.
    """
    services = list(vault_data.keys())

    if sort_mode == "name_asc":
        services.sort(key=str.lower)
    elif sort_mode == "name_desc":
        services.sort(key=str.lower, reverse=True)
    elif sort_mode == "time_new":
        services.reverse()  # insertion order is oldest-first; invert it
    # "time_old" keeps the natural (oldest-first) insertion order.

    # Pin favourites to the top (stable: preserves the sort within each group).
    favourites = [s for s in services if vault_data[s].get("favourite")]
    others = [s for s in services if not vault_data[s].get("favourite")]
    return favourites + others


_NOT_ALNUM = re.compile(r"[\W_]+")


def _fold(text) -> str:
    """Lowercase with accents dropped, so "CAFÉ" and "cafe" compare equal."""
    text = unicodedata.normalize("NFKD", str(text or "").casefold())
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def search_fields(service: str, entry: dict) -> tuple:
    """What a search looks at: the account name, the username and the website
    (its bare host too), folded. Computed once per vault revision."""
    url = _fold(entry.get("url", ""))
    fields = [_fold(service), _fold(entry.get("user", "")), url, _host(url)]
    fields = [f for f in dict.fromkeys(fields) if f]
    return tuple(fields), tuple(_NOT_ALNUM.sub("", f) for f in fields)


def _term_matches(term: str, fields: tuple, squashed: tuple) -> bool:
    if any(term in f for f in fields):
        return True
    # Punctuation doesn't count: "luca rossi" or "lucarossi" finds luca.rossi@…
    # A word that is only punctuation ("-", ".") says nothing, so it matches.
    bare = _NOT_ALNUM.sub("", term)
    if not bare or any(bare in f for f in squashed):
        return True
    # An address typed loosely: "luca@outlook" finds luca.rossi@outlook.it —
    # the part before @ anywhere in the mailbox name, the part after it as the
    # start of the domain.
    if term.count("@") == 1:
        name, domain = term.split("@")
        for f in fields:
            if "@" in f:
                f_name, f_domain = f.rsplit("@", 1)
                if name in f_name and f_domain.startswith(domain):
                    return True
    return False


def matches(fields, query: str) -> bool:
    """Every word of the query has to turn up in one of the fields (any field,
    any order), ignoring case, accents and punctuation.

    A query that contains an earlier one can only ever match fewer accounts,
    which is what lets SearchCache narrow a previous result."""
    words = _fold(query).split()
    return all(_term_matches(w, *fields) for w in words)


def visible_services(vault_data: dict, query: str = "", sort_mode: str = "name_asc") -> list:
    """Service names filtered by a search query and ordered by `sort_mode`."""
    services = ordered_services(vault_data, sort_mode)
    if not (query or "").strip():
        return services
    return [s for s in services if matches(search_fields(s, vault_data[s]), query)]


class SearchCache:
    """Remembers what the search box would otherwise redo on every keystroke:
    the folded fields to match against, the order per sort mode, and the
    result of each query typed so far.

    Typing another character narrows the previous result instead of rescanning
    the vault — a longer query can only ever match fewer accounts (see
    `matches`), so any query containing an earlier one can be answered from
    that earlier result.

    The whole cache is dropped when `revision` changes, which is how the app
    says "the vault was edited".
    """

    def __init__(self):
        self._revision = None
        self._fields = {}
        self._ordered = {}
        self._results = {}

    def services(self, vault_data: dict, revision, query: str = "",
                 sort_mode: str = "name_asc") -> list:
        if revision != self._revision:
            self._revision = revision
            self._fields = {s: search_fields(s, e) for s, e in vault_data.items()}
            self._ordered = {}
            self._results = {}

        q = " ".join(_fold(query).split())
        key = (sort_mode, q)
        cached = self._results.get(key)
        if cached is not None:
            return cached

        if sort_mode not in self._ordered:
            self._ordered[sort_mode] = ordered_services(vault_data, sort_mode)
        result = self._ordered[sort_mode]
        if q:
            result = [s for s in self._narrowest(sort_mode, q) if matches(self._fields[s], q)]
        self._results[key] = result
        return result

    def _narrowest(self, sort_mode, query):
        """The smallest cached result the query can be filtered from: any
        result whose query is contained in this one still holds every match."""
        best = self._ordered[sort_mode]
        for (mode, cached_q), result in self._results.items():
            if mode == sort_mode and cached_q and cached_q in query and len(result) < len(best):
                best = result
        return best


def _host(url: str) -> str:
    """Extracts a normalised hostname from a possibly-bare URL/domain string."""
    from urllib.parse import urlparse
    u = (url or "").strip()
    if not u:
        return ""
    if "://" not in u:
        u = "http://" + u
    host = (urlparse(u).hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    return host


def match_domain(vault_data: dict, domain: str) -> list:
    """
    Returns service names whose stored URL matches the given page domain.

    Matching is host-based (exact or subdomain in either direction). As a
    convenience fallback, an entry whose service name appears in the domain
    also matches, so entries without a URL can still be found.
    """
    domain = (domain or "").lower()
    if domain.startswith("www."):
        domain = domain[4:]
    if not domain:
        return []

    matches = []
    for name, entry in vault_data.items():
        host = _host(entry.get("url", ""))
        ok = bool(host) and (
            domain == host
            or domain.endswith("." + host)
            or host.endswith("." + domain)
        )
        if not ok:
            ok = name.lower() in domain
        if ok:
            matches.append(name)
    return matches


def delete_entry(vault_data: dict, service: str) -> bool:
    """
    Removes a service and its associated data entirely.
    Prevents orphaned data by deleting the full key-value pair.
    """
    if service in vault_data:
        del vault_data[service]
        return True
    return False

def rename_entry(vault_data: dict, service: str, new_name: str) -> bool:
    """
    Renames a service, keeping its position in the vault.

    The name is the dictionary key, so the entry is reinserted in place rather
    than re-added at the end — otherwise a rename would quietly reorder the
    "oldest/newest" sorts. Refuses to overwrite a different existing entry.
    """
    new_name = (new_name or "").strip()
    if not new_name or service not in vault_data:
        return False
    if new_name == service:
        return True
    if new_name in vault_data:
        return False
    renamed = [(new_name if key == service else key, value)
               for key, value in vault_data.items()]
    vault_data.clear()
    vault_data.update(renamed)
    return True


def modify_entry(vault_data: dict, service: str, new_user: str = None, new_pass: str = None) -> bool:
    """
    Updates the username, password, or both for a specific service.
    Validates service existence before performing partial updates.
    """
    if service not in vault_data:
        return False
    
    if new_user:
        vault_data[service]['user'] = new_user
    
    if new_pass:
        vault_data[service]['pass'] = new_pass
        
    return True


# --- Syncing with the iPhone app ---------------------------------------------
# The iOS app marks every entry it changes; these keys live inside the
# encrypted vault and are dropped again when the PC applies the change.
SYNC_STATE = "sync_pending"          # "new" | "changed" | "deleted" (True: changed)
SYNC_RENAMED_FROM = "sync_renamed_from"   # the name the PC knows the entry by


def merge_phone_changes(vault_data: dict, phone_vault: dict, seal=lambda p: p) -> dict:
    """Apply the changes the iPhone marked as not yet synced.

    New and edited entries replace the PC's version (the phone's edit is the
    newer one); a rename on the phone renames the PC's entry in place; a
    deletion on the phone deletes it here. Entries the phone didn't mark are
    left exactly as the PC has them. `seal` turns a plaintext password into
    how `vault_data` stores it (the app's per-session encryption).

    Returns {"added": [...], "changed": [...], "deleted": [...]}.
    """
    report = {"added": [], "changed": [], "deleted": []}
    for name, entry in phone_vault.items():
        state = entry.get(SYNC_STATE)
        if not state:
            continue
        old = entry.get(SYNC_RENAMED_FROM)
        if state == "deleted":
            for gone in (name, old):
                if gone and delete_entry(vault_data, gone):
                    report["deleted"].append(gone)
            continue
        incoming = {k: v for k, v in entry.items() if k not in (SYNC_STATE, SYNC_RENAMED_FROM)}
        incoming["pass"] = seal(incoming.get("pass", ""))
        if old and old != name and old in vault_data and name not in vault_data:
            rename_entry(vault_data, old, name)
        report["changed" if name in vault_data else "added"].append(name)
        vault_data[name] = incoming
    return report
