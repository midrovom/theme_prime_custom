from odoo import models, fields, api

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

    cantidad = fields.Char(string='Cantidad')
    talla = fields.Char(string='Talla')
    estado = fields.Char(string='Estado')

    @api.model
    def create(self, vals):
        category = ''
        department = ''
        if vals.get('category_id'):
            category_rec = self.env['maintenance.equipment.category'].browse(vals['category_id'])
            category = (category_rec.name or '')[:3].capitalize()
        if vals.get('department_id'):
            dept_rec = self.env['erp.request.department'].browse(vals['department_id'])
            department = (dept_rec.name or '')[:3].capitalize()

        seq = self.env['ir.sequence'].next_by_code('maintenance.equipment.code') or '000'
        vals['name'] = f"{category}-{department}-{seq}"

        return super(MaintenanceEquipment, self).create(vals)
