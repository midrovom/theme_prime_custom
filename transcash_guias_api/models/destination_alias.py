# -*- coding: utf-8 -*-
"""Equivalencias explícitas de códigos ERP para destinos del maestro operativo.

Un texto parecido no constituye identidad logística. El jefe de logística puede
mapear un código ERP histórico (p.ej. -NAJ) a un destino operativo concreto.
"""
import re
import unicodedata

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


def normalize_destination_code(value):
    raw = unicodedata.normalize('NFKD', str(value or '').strip().upper())
    raw = ''.join(c for c in raw if not unicodedata.combining(c))
    # Excluye espacios normales/no separables, marcas invisibles y separadores.
    return re.sub(r'[^A-Z0-9]', '', raw)


class TCDestinationAlias(models.Model):
    _name = 'tc.destination.alias'
    _description = 'Equivalencia de código de destino ERP - Transcash'
    _rec_name = 'codigo_erp'
    _order = 'codigo_normalizado, id'

    codigo_erp = fields.Char('Código recibido del ERP', required=True)
    codigo_normalizado = fields.Char('Código normalizado', required=True, readonly=True,
                                     index=True, copy=False)
    destino_id = fields.Many2one('transcash.destino', string='Destino de Logística',
                                  required=True, ondelete='restrict', index=True)
    company_id = fields.Many2one('res.company', string='Compañía', required=True,
                                  readonly=True, index=True)
    active = fields.Boolean(default=True)
    note = fields.Char('Observación')

    _sql_constraints = [
        ('tc_destination_alias_unique', 'unique(company_id,codigo_normalizado)',
         'Este código ERP ya tiene una equivalencia en esta compañía.'),
    ]

    def _check_manager(self):
        if not self.env.su and not (self.env.user.has_group('logistica_transcash.group_logistica_manager') or
                                    self.env.user.has_group('base.group_system')):
            raise AccessError(_('Solo el jefe de Logística o el administrador configura equivalencias.'))

    @api.model_create_multi
    def create(self, vals_list):
        self._check_manager()
        Destination = self.env['transcash.destino'].sudo()
        prepared = []
        for item in vals_list:
            vals = dict(item)
            master = Destination.browse(int(vals.get('destino_id') or 0)).exists()
            if not master:
                raise ValidationError(_('Seleccione un destino de Logística válido.'))
            if not self.env.su and master.company_id not in self.env.user.company_ids:
                raise AccessError(_('No puede configurar destinos de otra compañía.'))
            code = normalize_destination_code(vals.get('codigo_erp'))
            if not code or len(code) > 80:
                raise ValidationError(_('Indique un código ERP válido para el destino.'))
            vals.update({'codigo_normalizado': code, 'company_id': master.company_id.id})
            prepared.append(vals)
        return super().create(prepared)

    def write(self, vals):
        self._check_manager()
        # Evitar que una actualización cambie silenciosamente la compañía del mapeo.
        if 'company_id' in vals or 'codigo_normalizado' in vals:
            raise ValidationError(_('La compañía y el código normalizado son automáticos.'))
        if 'codigo_erp' in vals or 'destino_id' in vals:
            for rec in self:
                master = (self.env['transcash.destino'].sudo().browse(vals['destino_id']).exists()
                          if vals.get('destino_id') else rec.destino_id)
                if not master:
                    raise ValidationError(_('Destino de logística inválido.'))
                if master.company_id != rec.company_id:
                    raise ValidationError(_('El destino pertenece a otra compañía. Cree otra equivalencia.'))
                code = normalize_destination_code(vals.get('codigo_erp', rec.codigo_erp))
                if not code or len(code) > 80:
                    raise ValidationError(_('Código ERP inválido.'))
                if len(self) != 1:
                    raise ValidationError(_('Actualice una equivalencia a la vez.'))
                vals = dict(vals, codigo_normalizado=code)
                # Llamar al super con los campos técnicos garantizados por nosotros.
                return super().write(vals)
        return super().write(vals)

    def unlink(self):
        self._check_manager()
        return super().unlink()
