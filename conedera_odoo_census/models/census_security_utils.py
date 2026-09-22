CENSUS_USER_GROUP = "conedera_odoo_census.group_census_user"
CENSUS_SUPERVISOR_GROUP = "conedera_odoo_census.group_census_supervisor"
CENSUS_MANAGER_GROUP = "conedera_odoo_census.group_census_manager"


def is_census_user(user):
    """True only for explicit Catastro roles.

    1.8.2 migrates legacy Sales users/managers to these groups, so runtime access
    no longer depends implicitly on unrelated standard Sales permissions.
    """
    return bool(
        user.has_group(CENSUS_USER_GROUP)
        or user.has_group(CENSUS_SUPERVISOR_GROUP)
        or user.has_group(CENSUS_MANAGER_GROUP)
    )


def is_census_supervisor(user):
    return bool(
        user.has_group(CENSUS_SUPERVISOR_GROUP)
        or user.has_group(CENSUS_MANAGER_GROUP)
    )


def is_census_manager(user):
    return bool(user.has_group(CENSUS_MANAGER_GROUP))
