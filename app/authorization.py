from typing import List, Dict


ROLE_ACCESS_GROUPS: Dict[str, List[str]] = {
    "admin": ["admin", "hr", "engineering", "finance"],
    # `admin` is an access group granted only to the administrator role.
    # Do not put it in ordinary roles: many records also grant admin access.
    "hr": ["hr"],
    "engineering": ["engineering"],
    "finance": ["finance"],
}


def get_allowed_access_groups(user_role: str) -> List[str]:
    return ROLE_ACCESS_GROUPS.get(user_role, [])


def check_access(user_role: str, required_groups: List[str]) -> bool:
    allowed_groups = get_allowed_access_groups(user_role)
    return any(group in allowed_groups for group in required_groups)


def filter_metadata_by_access(metadata: dict, user_role: str) -> bool:
    access_groups = metadata.get("access_groups", [])
    if isinstance(access_groups, str):
        import json
        try:
            access_groups = json.loads(access_groups)
        except:
            access_groups = [access_groups]
    return check_access(user_role, access_groups)
