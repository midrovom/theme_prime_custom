from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

class StockQuant(models.Model):
    _inherit = 'stock.quant'

    check_update = fields.Boolean('Se actualiza', default=False)
    