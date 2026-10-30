"""Decide legacy data work from the installed module version, not on each UI update."""


def required_upgrade_steps(installed_version):
    """Successful 1.6+ updates already completed the unique/weight/pallet conversion.

    A failed upgrade does not advance the installed version, so Odoo retries the
    required legacy work in the same transactional way. Empty initial installs
    use their noupdate XML setup and need no historical conversion.
    """
    if not installed_version:
        return ()
    try:
        version = tuple(int(part) for part in str(installed_version).split("."))
        # Also accept a module-only version in tests or older custom packages.
        if version[0] < 10:
            version = (18, 0, *version)
        version += (0,) * max(0, 5 - len(version))
    except (TypeError, ValueError, IndexError):
        # An unrecognised historical version must not silently lose migration.
        return ("cities", "unique_records")
    steps = []
    if version < (18, 0, 1, 3, 0):
        steps.append("cities")
    if version < (18, 0, 1, 6, 0):
        steps.append("unique_records")
    return tuple(steps)
