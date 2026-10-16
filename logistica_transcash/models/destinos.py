"""Catálogo único de destinos para API, tarifarios y planificación."""
import re
from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


class TranscashDestino(models.Model):
    _name = 'transcash.destino'
    _description = 'Destino logístico Transcash (código del ERP)'
    _order = 'name, codigo'
    _rec_name = 'name'

    name = fields.Char('Destino', required=True, index=True)
    codigo = fields.Char('Código ERP', required=True, index=True)
    ciudad = fields.Char('Ciudad')
    provincia = fields.Char('Provincia')
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    active = fields.Boolean('Activo', default=True)
    fuente = fields.Selection([('manual', 'Manual'), ('erp', 'ERP'), ('migrado', 'Migrado')],
                              default='manual', readonly=True)

    _sql_constraints = [('codigo_company_unique','unique(company_id,codigo)',
                         'Este código de destino ya está registrado para la compañía.')]

    @api.model
    def _normalizar_codigo(self, code):
        code = str(code or '').strip().upper()
        if not code or len(code) > 80 or not re.fullmatch(r'[A-Z0-9][A-Z0-9._\-]*', code):
            raise ValidationError(_('Código de destino inválido: utilice letras, números, puntos, guiones o guiones bajos.'))
        return code

    def _check_manager(self):
        if not self.env.su and not self.env.user.has_group('logistica_transcash.group_logistica_manager'):
            raise AccessError(_('Solo el jefe de Logística administra el maestro de destinos.'))

    @api.model_create_multi
    def create(self, vals_list):
        self._check_manager()
        for vals in vals_list:
            vals['codigo'] = self._normalizar_codigo(vals.get('codigo'))
            vals['name'] = (vals.get('name') or '').strip()
            if not vals['name']:
                raise ValidationError(_('Indique el nombre del destino.'))
        return super().create(vals_list)

    def write(self, vals):
        self._check_manager()
        vals = dict(vals)
        if 'codigo' in vals:
            if any(self.env['transcash.hoja.ruta'].sudo().search_count([('destino_id','=',d.id)]) or
                   self.env['transcash.tarifa.traslado'].sudo().search_count([('destino_id','=',d.id)]) or
                   self.env['transcash.guia'].sudo().search_count([('destino_id','=',d.id)]) for d in self):
                raise UserError(_('El destino ya se utiliza en rutas, tarifas o guías. No cambie su código; cree otro destino.'))
            vals['codigo'] = self._normalizar_codigo(vals['codigo'])
        if 'company_id' in vals and any(d.company_id.id != vals['company_id'] for d in self):
            raise UserError(_('No se puede cambiar la compañía de un destino.'))
        return super().write(vals)

    def unlink(self):
        self._check_manager()
        for d in self:
            if (self.env['transcash.tarifa.traslado'].sudo().search_count([('destino_id','=',d.id)]) or
                self.env['transcash.hoja.ruta'].sudo().search_count([('destino_id','=',d.id)]) or
                self.env['transcash.guia'].sudo().search_count([('destino_id','=',d.id)])):
                raise UserError(_('Este destino ya tiene historial. Desactívelo en lugar de borrarlo.'))
        return super().unlink()

    @api.model
    def obtener_desde_erp(self, codigo, ciudad=None, provincia=None, company_id=None):
        """Registrar nuevos códigos del ERP al recibir la guía, sin reescribir fichas existentes."""
        code = self._normalizar_codigo(codigo)
        company_id = company_id or self.env.company.id
        Catalog = self.sudo().with_context(active_test=False)
        found = Catalog.search([('company_id','=',company_id),('codigo','=',code)], limit=1)
        if found:
            return found
        # Una importación concurrente del mismo código no debe duplicar fichas.
        self.env.cr.execute('SELECT id FROM res_company WHERE id = %s FOR UPDATE', (company_id,))
        found = Catalog.search([('company_id','=',company_id),('codigo','=',code)], limit=1)
        if found:
            return found
        return Catalog.create({'company_id':company_id,'codigo':code,
                               'name':(ciudad or code).strip()[:255],
                               'ciudad':(ciudad or '')[:255],
                               'provincia':(provincia or '')[:255], 'fuente':'erp'})


class GuiaDestino(models.Model):
    _inherit = 'transcash.guia'

    destino_id = fields.Many2one('transcash.destino', string='Destino homologado',
                                 index=True, ondelete='restrict', copy=False)
