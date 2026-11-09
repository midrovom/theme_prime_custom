"""Domain scope shared by PWA product promotions and Odoo's native Loyalty flow.

Kept independent of the Odoo runtime to enable fast regression testing.
Empty program warehouse set = applies to all warehouses (backwards-compatible).
A program with selected warehouses matches only its listed warehouse IDs.
Without a selected warehouse only unrestricted programs are eligible.
"""


def warehouse_scope_domain(warehouse_id, related_prefix=''):
    field = '%scatastro_warehouse_ids' % related_prefix
    warehouse_id = int(warehouse_id or 0)
    if warehouse_id > 0:
        return ['|', (field, '=', False), (field, 'in', [warehouse_id])]
    return [(field, '=', False)]
