from odoo import models, fields, api
import re

class MaintenanceProductCategory(models.Model):
    _name = 'maintenance.product.category'
    _description = 'Categoría de Producto de Mantenimiento'

    name = fields.Char(string='Nombre de categoría', required=True)
    description = fields.Text(string='Descripción')


# class MaintenanceEquipment(models.Model):
#     _inherit = 'maintenance.equipment'

#     product_category_id = fields.Many2one(
#         'maintenance.product.category',
#         string='Tipo de producto',
#         tracking=True
#     )

#     cantidad = fields.Char(string='Cantidad')
#     talla = fields.Char(string='Talla')
#     estado = fields.Char(string='Estado')

#     name = fields.Char('Name', translate=True)

#     @api.onchange('category_id', 'department_id')
#     def _onchange_category_department(self):
#         """Genera un código preliminar mientras se llenan los campos."""
#         if self.category_id and self.department_id:
#             cat = (self.category_id.name or '')[:3].capitalize()
#             dept = (self.department_id.name or '')[:3].capitalize()
#             self.name = f"{cat}-{dept}-XXX"

#     @api.model
#     def create(self, vals):
#         category = ''
#         department = ''
#         if vals.get('category_id'):
#             category_rec = self.env['maintenance.equipment.category'].browse(vals['category_id'])
#             category = (category_rec.name or '')[:3].capitalize()
#         if vals.get('department_id'):
#             dept_rec = self.env['hr.department'].browse(vals['department_id'])
#             department = (dept_rec.name or '')[:3].capitalize()

#         prefix = f"{category}-{department}-"
#         last_equipment = self.search([('name', 'like', prefix)], order='name desc', limit=1)

#         next_seq = 1
#         if last_equipment:
#             match = re.search(rf"{prefix}(\d+)", last_equipment.name)
#             if match:
#                 last_num = int(match.group(1))
#                 next_seq = last_num + 1

#         # Formatear con padding de 3 dígitos
#         seq_str = str(next_seq).zfill(3)

#         vals['name'] = f"{prefix}{seq_str}"

#         return super(MaintenanceEquipment, self).create(vals)

#     def write(self, vals):
#         """Recalcula el código si cambian categoría o departamento."""
#         for rec in self:
#             if vals.get('category_id') or vals.get('department_id'):
#                 category = ''
#                 department = ''
#                 if vals.get('category_id'):
#                     category_rec = self.env['maintenance.equipment.category'].browse(vals['category_id'])
#                     category = (category_rec.name or '')[:3].capitalize()
#                 else:
#                     category = (rec.category_id.name or '')[:3].capitalize()

#                 if vals.get('department_id'):
#                     dept_rec = self.env['hr.department'].browse(vals['department_id'])
#                     department = (dept_rec.name or '')[:3].capitalize()
#                 else:
#                     department = (rec.department_id.name or '')[:3].capitalize()

#                 prefix = f"{category}-{department}-"

#                 # Buscar último registro con ese prefijo
#                 last_equipment = self.search([('name', 'like', prefix)], order='name desc', limit=1)
#                 next_seq = 1
#                 if last_equipment:
#                     match = re.search(rf"{prefix}(\d+)", last_equipment.name)
#                     if match:
#                         last_num = int(match.group(1))
#                         next_seq = last_num + 1

#                 seq_str = str(next_seq).zfill(3)
#                 vals['name'] = f"{prefix}{seq_str}"

#         return super(MaintenanceEquipment, self).write(vals)

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
    name = fields.Char('Nombre de categoría', translate=True, required=True)

    @api.onchange('category_id', 'department_id')
    def _onchange_category_department(self):
        """Previsualiza el código mientras se llenan los campos."""
        if self.category_id and self.department_id:
            cat = (self.category_id.name or '')[:3].capitalize()
            dept = (self.department_id.name or '')[:3].capitalize()
            self.name = f"{cat}-{dept}-XXX"

    def _build_name(self, category, department, user_text):
        """Construye el nombre con prefijo, secuencia y texto adicional."""
        prefix = f"{category}-{department}-"

        # Buscar último registro con ese prefijo
        last_equipment = self.search([('name', 'like', prefix)], order='name desc', limit=1)
        next_seq = 1
        if last_equipment:
            match = re.search(rf"{prefix}(\d+)", last_equipment.name)
            if match:
                last_num = int(match.group(1))
                next_seq = last_num + 1

        seq_str = str(next_seq).zfill(3)

        # Eliminar cualquier prefijo viejo del texto del usuario
        extra_text = re.sub(rf"^{prefix}\d+\s*", "", user_text or "").strip()

        return f"{prefix}{seq_str} {extra_text}".strip()

    @api.model
    def create(self, vals):
        category = ''
        department = ''
        if vals.get('category_id'):
            category_rec = self.env['maintenance.equipment.category'].browse(vals['category_id'])
            category = (category_rec.name or '')[:3].capitalize()
        if vals.get('department_id'):
            dept_rec = self.env['hr.department'].browse(vals['department_id'])
            department = (dept_rec.name or '')[:3].capitalize()

        vals['name'] = self._build_name(category, department, vals.get('name'))
        return super(MaintenanceEquipment, self).create(vals)

    def write(self, vals):
        for rec in self:
            if vals.get('category_id') or vals.get('department_id') or vals.get('name'):
                category = (self.env['maintenance.equipment.category'].browse(vals.get('category_id')) if vals.get('category_id') else rec.category_id).name[:3].capitalize()
                department = (self.env['hr.department'].browse(vals.get('department_id')) if vals.get('department_id') else rec.department_id).name[:3].capitalize()
                user_text = vals.get('name', rec.name)
                vals['name'] = self._build_name(category, department, user_text)
        return super(MaintenanceEquipment, self).write(vals)

