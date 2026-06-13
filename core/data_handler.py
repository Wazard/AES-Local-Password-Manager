def visible_services(vault_data: dict, query: str = "", sort_mode: str = "name_asc") -> list:
    """
    Returns the list of service names filtered by a search query and ordered
    by the requested sort mode.

    The query matches against both the service name and its username.

    Time ordering uses the vault's natural insertion order (oldest-first by
    design) rather than the "created" timestamp, which is missing on legacy
    entries. "time_new" simply inverts that order.

    Favourited entries are always grouped first, keeping their relative order
    from the chosen sort.
    """
    services = list(vault_data.keys())

    q = (query or "").strip().lower()
    if q:
        services = [
            s for s in services
            if q in s.lower() or q in str(vault_data[s].get("user", "")).lower()
        ]

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