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


def haystack(service: str, entry: dict) -> str:
    """The text a search query is matched against: the service name and the
    username, joined by a character no query can contain, so a match can never
    straddle the two fields."""
    return "%s\x00%s" % (service.lower(), str(entry.get("user", "")).lower())


def visible_services(vault_data: dict, query: str = "", sort_mode: str = "name_asc") -> list:
    """Service names filtered by a search query and ordered by `sort_mode`.
    The query matches against both the service name and its username."""
    services = ordered_services(vault_data, sort_mode)
    q = (query or "").strip().lower()
    if not q:
        return services
    return [s for s in services if q in haystack(s, vault_data[s])]


class SearchCache:
    """Remembers what the search box would otherwise redo on every keystroke:
    the lowercased text to match against, the order per sort mode, and the
    result of each query typed so far.

    Typing another character narrows the previous result instead of rescanning
    the vault — a substring match can only ever shrink the set, so any query
    containing an earlier one can be answered from that earlier result.

    The whole cache is dropped when `revision` changes, which is how the app
    says "the vault was edited".
    """

    def __init__(self):
        self._revision = None
        self._haystacks = {}
        self._ordered = {}
        self._results = {}

    def services(self, vault_data: dict, revision, query: str = "",
                 sort_mode: str = "name_asc") -> list:
        if revision != self._revision:
            self._revision = revision
            self._haystacks = {s: haystack(s, e) for s, e in vault_data.items()}
            self._ordered = {}
            self._results = {}

        q = (query or "").strip().lower()
        key = (sort_mode, q)
        cached = self._results.get(key)
        if cached is not None:
            return cached

        if sort_mode not in self._ordered:
            self._ordered[sort_mode] = ordered_services(vault_data, sort_mode)
        result = self._ordered[sort_mode]
        if q:
            result = [s for s in self._narrowest(sort_mode, q) if q in self._haystacks[s]]
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