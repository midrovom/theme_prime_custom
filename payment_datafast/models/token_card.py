from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

class TokenCard(models.Model):
    _name = 'token.card'
    
    name = fields.Char('Nombre de la tarjeta')
    token = fields.Char('Registro tokenizado')
    partner_id = fields.Many2one('res.partner', string='Cliente')
    reference_card = fields.Char('Numero de referencia')
    expiry_month = fields.Char('Mes de expiración')
    expiry_year = fields.Char('Año de expiración')
    