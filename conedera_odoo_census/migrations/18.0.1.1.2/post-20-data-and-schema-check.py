import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def _table_exists(cr, table):
    cr.execute("SELECT to_regclass(%s)", [table])
    return bool(cr.fetchone()[0])


def migrate(cr, version):
    """Re-run legacy data conversion safely and verify new relational models.

    This script is idempotent so it also repairs installations where an older
    post-migration never completed.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    Partner = env["res.partner"].with_context(active_test=False)
    BusinessType = env["conedera.census.business.type"].with_context(active_test=False)

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

    for partner in Partner.search(
        [("phone", "=", False), ("commercial_contact_phone", "!=", False)]
    ):
        partner.phone = partner.commercial_contact_phone

    segment_map = {
        "wholesaler": "wholesaler",
        "reseller": "reseller",
        "route": "other",
    }
    for legacy_value, new_value in segment_map.items():
        Partner.search(
            [
                ("customer_census_type", "=", legacy_value),
                ("customer_segment", "=", False),
            ]
        ).write({"customer_segment": new_value})

    expected_tables = {
        "conedera_census_business_type",
        "conedera_partner_opening_hour",
        "conedera_census_visit",
        "conedera_partner_business_type_rel",
    }
    missing = sorted(t for t in expected_tables if not _table_exists(cr, t))
    if missing:
        raise RuntimeError(
            "Conedera upgrade finished model loading but required tables are missing: %s"
            % ", ".join(missing)
        )

    _logger.info("Conedera 18.0.1.1.2 post-upgrade verification completed")
