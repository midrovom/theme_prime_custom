from odoo import api, fields, models, _

class ResPartner(models.Model):
    _inherit = "res.partner"

    is_petty_cash_beneficiary = fields.Boolean(
        string="Beneficiario de caja chica",
        help="Permite seleccionar este contacto como beneficiario de un gasto de caja chica.",
    )