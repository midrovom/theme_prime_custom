from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ConederaCreditReference(models.Model):
    _name = 'conedera.credit.reference'
    _description = 'Referencia de solicitud de crédito CONEDERA'
    _order = 'reference_type, sequence, id'

    application_id = fields.Many2one(
        'conedera.credit.application', string='Solicitud', required=True,
        ondelete='cascade', index=True,
    )
    reference_type = fields.Selection([
        ('commercial', 'Comercial'),
        ('personal', 'Personal'),
        ('bank', 'Bancaria'),
    ], string='Tipo de referencia', required=True, index=True)
    sequence = fields.Integer(default=10)

    # Referencias comerciales
    provider = fields.Char(string='Proveedor')
    customer_since = fields.Char(string='Cliente desde')
    credit_limit = fields.Monetary(string='Cupo', currency_field='currency_id')
    term = fields.Char(string='Plazo')
    phone = fields.Char(string='Teléfono')
    contact = fields.Char(string='Contacto')

    # Referencias personales
    person_name = fields.Char(string='Nombres')
    address = fields.Char(string='Dirección')
    home_phone = fields.Char(string='Teléfono domicilio')
    relationship = fields.Char(string='Parentesco')

    # Referencias bancarias
    bank_name = fields.Char(string='Banco / tarjeta de crédito')
    account_number = fields.Char(string='Número de cuenta')
    opening_date = fields.Date(string='Fecha de apertura')
    account_type = fields.Selection([('current', 'Cuenta corriente'), ('savings', 'Ahorros')], string='Tipo de cuenta')
    currency_id = fields.Many2one('res.currency', string='Moneda', default=lambda self: self.env.company.currency_id, required=True)


    @api.constrains('credit_limit')
    def _check_credit_limit(self):
        for record in self:
            if record.credit_limit < 0:
                raise ValidationError(_('El cupo de la referencia comercial no puede ser negativo.'))
