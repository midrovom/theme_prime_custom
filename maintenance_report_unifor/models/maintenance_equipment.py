from odoo import models, fields, api
import re

class MaintenanceProductCategory(models.Model):
    _name = 'maintenance.product.category'
    _description = 'Categoría de Producto de Mantenimiento'

    name = fields.Char(string='Nombre de categoría', required=True)
    description = fields.Text(string='Descripción')


class MaintenanceEquipment(models.Model):
    _inherit = 'maintenance.equipment'

    product_category_id = fields.Many2one(
        'maintenance.product.category',
        string='Tipo de producto',
        tracking=True
    )

    cantidad = fields.Char(string='Cantidad')
    talla = fields.Char(string='Talla')
    estado = fields.Char(string='Estado')

    name = fields.Char('Name', translate=True)

    company_related_id = fields.Many2one('res.partner', string='Compañía relacionada',
        domain="[('is_company', '=', True)]", related='partner_id',
        store=True, readonly=False
    )

    @api.onchange('category_id', 'partner_id')
    def _onchange_category_partner(self):
        """Previsualiza el código mientras se llenan los campos."""
        if self.category_id and self.partner_id:
            cat = (self.category_id.name or '')[:3].capitalize()
            prov = (self.partner_id.name or '')[:3].capitalize()
            self.name = f"{cat}-{prov}-XXX"

    @api.model
    def create(self, vals):
        category = ''
        provider = ''
        if vals.get('category_id'):
            category_rec = self.env['maintenance.equipment.category'].browse(vals['category_id'])
            category = (category_rec.name or '')[:3].capitalize()
        if vals.get('partner_id'):
            prov_rec = self.env['res.partner'].browse(vals['partner_id'])
            provider = (prov_rec.name or '')[:3].capitalize()

        prefix = f"{category}-{provider}-"
        last_equipment = self.search([('name', 'like', prefix)], order='name desc', limit=1)

        next_seq = 1
        if last_equipment:
            match = re.search(rf"{prefix}(\d+)", last_equipment.name)
            if match:
                last_num = int(match.group(1))
                next_seq = last_num + 1

        seq_str = str(next_seq).zfill(3)
        vals['name'] = f"{prefix}{seq_str}"

        return super(MaintenanceEquipment, self).create(vals)

    def write(self, vals):
        """Recalcula el código si cambian categoría o proveedor."""
        for rec in self:
            if vals.get('category_id') or vals.get('partner_id'):
                category = (self.env['maintenance.equipment.category'].browse(vals.get('category_id')) if vals.get('category_id') else rec.category_id).name[:3].capitalize()
                provider = (self.env['res.partner'].browse(vals.get('partner_id')) if vals.get('partner_id') else rec.partner_id).name[:3].capitalize()

                prefix = f"{category}-{provider}-"
                last_equipment = self.search([('name', 'like', prefix)], order='name desc', limit=1)

                next_seq = 1
                if last_equipment:
                    match = re.search(rf"{prefix}(\d+)", last_equipment.name)
                    if match:
                        last_num = int(match.group(1))
                        next_seq = last_num + 1

                seq_str = str(next_seq).zfill(3)
                vals['name'] = f"{prefix}{seq_str}"

        return super(MaintenanceEquipment, self).write(vals)

    @api.onchange('company_related_id')
    def _onchange_company_related_id(self):
        if self.company_related_id:
            self.partner_id = self.company_related_id

