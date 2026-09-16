from odoo import SUPERUSER_ID, api


def migrate(cr, version):
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
        if not partners:
            continue
        tags = BusinessType.search([("code", "in", codes)])
        if tags:
            partners.write({"business_type_ids": [(4, tag.id) for tag in tags]})

    # Reutilizar el teléfono estándar de Odoo cuando existía el campo comercial antiguo.
    for partner in Partner.search([("phone", "=", False), ("commercial_contact_phone", "!=", False)]):
        partner.phone = partner.commercial_contact_phone

    segment_map = {
        "wholesaler": "wholesaler",
        "reseller": "reseller",
        # El valor antiguo "Ruteo" no tenía una semántica suficientemente clara.
        # Se conserva como legado pero se migra a "Otro" para evitar asumir una categoría.
        "route": "other",
    }
    for legacy_value, new_value in segment_map.items():
        Partner.search([
            ("customer_census_type", "=", legacy_value),
            ("customer_segment", "=", False),
        ]).write({"customer_segment": new_value})
