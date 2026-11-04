from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ConederaCreditVehicle(models.Model):
    _name = 'conedera.credit.vehicle'
    _description = 'Vehículo de una solicitud de crédito'
    _order = 'sequence, id'

    application_id = fields.Many2one('conedera.credit.application', string='Solicitud',
                                     required=True, index=True, ondelete='cascade')
    sequence = fields.Integer(string='Orden', default=10)
    brand = fields.Char(string='Marca')
    model = fields.Char(string='Modelo')
    year = fields.Char(string='Año')
    value = fields.Monetary(string='Avalúo comercial', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', related='application_id.currency_id',
                                  store=True, readonly=True)
    # 1 y 2 se utilizan únicamente al migrar los antiguos campos vehicle1/vehicle2.
    legacy_slot = fields.Integer(string='Posición antigua', copy=False, readonly=True)

    @api.constrains('value')
    def _check_vehicle_value(self):
        for vehicle in self:
            if vehicle.value < 0:
                raise ValidationError(_('El avalúo comercial del vehículo no puede ser negativo.'))
