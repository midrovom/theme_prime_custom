from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    census_originated = fields.Boolean(string="Originada desde catastro", copy=False, index=True)
    census_visit_id = fields.Many2one(
        "conedera.census.visit",
        string="Visita comercial",
        copy=False,
        index=True,
        ondelete="set null",
    )
