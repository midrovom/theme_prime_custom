import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def _table_exists(cr, table):
    cr.execute("SELECT to_regclass(%s)", [table])
    return bool(cr.fetchone()[0])


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Partner = env["res.partner"].with_context(active_test=False)
    BusinessType = env["conedera.census.business.type"].with_context(active_test=False)

    # Safe legacy conversions.
    type_map = {
        "cellphones": ["cellphones"],
        "accessories": ["accessories"],
        "mixed": ["cellphones", "accessories"],
        "commercial_house": ["commercial_house"],
        "computing": ["computing"],
        "other": ["other"],
    }
    for legacy_value, codes in type_map.items():
        partners = Partner.search([("business_type", "=", legacy_value)])
        tags = BusinessType.search([("code", "in", codes)])
        if partners and tags:
            partners.write({"business_type_ids": [(4, tag.id) for tag in tags]})

    # Do not invent a store count. Unknown values stay pending until a user enters them.

    expected_tables = {
        "conedera_census_business_type",
        "conedera_partner_opening_hour",
        "conedera_census_visit",
        "conedera_partner_business_type_rel",
    }
    missing = sorted(t for t in expected_tables if not _table_exists(cr, t))
    if missing:
        raise RuntimeError(
            "Conedera upgrade missing required tables: %s" % ", ".join(missing)
        )

    _logger.info("Conedera 18.0.1.2.0 post-upgrade verification completed")
