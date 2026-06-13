def visible_services(vault_data: dict, query: str = "", sort_mode: str = "name_asc") -> list:
    """
    Returns the list of service names filtered by a search query and ordered
    by the requested sort mode.

    The query matches against both the service name and its username.
    Entries missing a "created" timestamp (legacy data) sort as oldest.
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
        services.sort(key=lambda s: vault_data[s].get("created", 0), reverse=True)
    elif sort_mode == "time_old":
        services.sort(key=lambda s: vault_data[s].get("created", 0))

    return services


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