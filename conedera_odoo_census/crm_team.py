"""Compatibility bootstrap for legacy/flattened package initializers.

A correct Odoo addon imports ``models`` from the package root. Some prior
deployments accidentally copied ``models/__init__.py`` into the package root
and therefore attempted ``from . import crm_team``. Importing this shim loads
the canonical models package and registers aliases for the legacy root-level
module names so that such an installation can still bootstrap far enough to
be upgraded cleanly.
"""
import sys

from . import models

_LEGACY_MODEL_NAMES = (
    "crm_team",
    "census_business_type",
    "census_mobile_brand",
    "partner_opening_hour",
    "res_partner",
    "census_customer_lookup_wizard",
    "census_unlock_request",
    "census_reassignment_request",
    "census_visit",
    "sale_order",
    "census_commercial_report",
    "product_template",
    "census_role_wizard",
)

for _name in _LEGACY_MODEL_NAMES:
    _module = getattr(models, _name, None)
    if _module is not None:
        sys.modules.setdefault(f"{__package__}.{_name}", _module)
