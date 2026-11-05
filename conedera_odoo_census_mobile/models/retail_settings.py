"""User-friendly wizard to configure the existing Consumer Final for a company.

No res.company records or stored columns are created. The existing non-stored
res.company.catastro_retail_partner_id field remains the single source of truth.
"""
from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError


class CatastroRetailSettingsWizard(models.TransientModel):
    _name = 'catastro.retail.settings.wizard'
    _description = 'Configuración de Consumidor Final para Catastro PWA'

    company_id = fields.Many2one(
        'res.company', string='Empresa que utilizará este cliente', required=True,
        default=lambda self: self.env.company,
        help='Seleccione una empresa existente. Esta opción no crea empresas.'
    )
    retail_partner_id = fields.Many2one(
        'res.partner', string='Cliente Consumidor Final', required=True,
        help='Contacto de Odoo que se asignará a las cotizaciones de mostrador de la empresa.'
    )

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        if 'retail_partner_id' in fields_list:
            company = self.env['res.company'].browse(vals.get('company_id') or self.env.company.id)
            vals['retail_partner_id'] = company.catastro_retail_partner_id.id or False
        return vals

    @api.onchange('company_id')
    def _onchange_company_id(self):
        for wizard in self:
            wizard.retail_partner_id = wizard.company_id.catastro_retail_partner_id if wizard.company_id else False

    def action_save(self):
        self.ensure_one()
        if not self.env.user.has_group('base.group_system'):
            raise AccessError('Solo un administrador puede definir el cliente Consumidor Final.')
        if self.company_id not in self.env.companies:
            raise AccessError('Active primero la empresa seleccionada en el selector de compañías de Odoo.')
        partner = self.retail_partner_id
        if not partner or not partner.exists():
            raise ValidationError('Seleccione un contacto de Consumidor Final válido.')
        if partner.company_id and partner.company_id != self.company_id:
            raise ValidationError('El contacto pertenece a otra empresa. Seleccione uno compartido o de la empresa indicada.')
        # Reutilizar el inverse existente, que persiste en ir.config_parameter
        # y evita columnas nuevas en res_company durante la actualización.
        self.company_id.write({'catastro_retail_partner_id': partner.id})
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Consumidor Final configurado',
                'message': 'La empresa %s utilizará el cliente %s en Cotizador de tienda.' % (
                    self.company_id.display_name, partner.display_name),
                'type': 'success',
                'sticky': False,
            },
        }
