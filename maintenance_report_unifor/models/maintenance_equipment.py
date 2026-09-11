from odoo import models, fields

class MaintenanceProductCategory(models.Model):
    _name = 'maintenance.product.category'
    _description = 'Categoría de Producto de Mantenimiento'

    name = fields.Char(string='Nombre de categoría', required=True)
    description = fields.Text(string='Descripción')


class MaintenanceEquipment(models.Model):
    _inherit = 'maintenance.equipment'

    product_category_id = fields.Many2one('maintenance.product.category', string='Tipo de producto',
        tracking=True
    )
