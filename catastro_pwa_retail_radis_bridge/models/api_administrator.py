# -*- coding: utf-8 -*-
"""Enriquecimiento mínimo del contrato de Radis; NO edita stock_api_assing.

Se ejecuta tanto en acción manual como en cron porque ambos usan
api.administrator.call_api(api_name='check_update_qoutes', ...).
El ID de empresa REAL sigue siendo el que escoge URL/credenciales de Radis.
"""
from odoo import models, _
from odoo.exceptions import UserError


class ApiAdministrator(models.Model):
    _inherit = 'api.administrator'

    def call_api(self, api_name, method='get', company_id=1, params=None, headers_extra=None):
        if api_name != 'check_update_qoutes' or (method or '').lower() != 'post':
            return super().call_api(api_name, method=method, company_id=company_id,
                                    params=params, headers_extra=headers_extra)
        if not isinstance(params, (list, tuple)):
            return super().call_api(api_name, method=method, company_id=company_id,
                                    params=params, headers_extra=headers_extra)

        try:
            company_id_int = int(company_id)
        except (ValueError, TypeError):
            company_id_int = 0
        if not company_id_int:
            return super().call_api(api_name, method=method, company_id=company_id,
                                    params=params, headers_extra=headers_extra)

        names = {entry.get('order_name') for entry in params
                 if isinstance(entry, dict) and isinstance(entry.get('order_name'), str)
                 and entry.get('order_name')}
        orders = self.env['sale.order'].sudo().search([
            ('company_id', '=', company_id_int),
            ('name', 'in', list(names)),
            ('catastro_pwa_origin', '=', True),
            ('catastro_pwa_retail_origin', '=', True),
        ]) if names else self.env['sale.order']

        by_name = {}
        for order in orders:
            # No permitir ambigüedad por secuencias duplicadas en la misma empresa.
            if order.name in by_name:
                raise UserError(_('Existe más de una proforma de Tienda con número %s en esta empresa.') % order.name)
            by_name[order.name] = order

        enriched = []
        for entry in params:
            if not isinstance(entry, dict) or entry.get('order_name') not in by_name:
                enriched.append(entry)
                continue
            order = by_name[entry['order_name']]
            if order.company_id.id != company_id_int:
                raise UserError(_('La proforma de Tienda pertenece a otra empresa.'))
            key = 'conedera_odoo_census_mobile.retail_erp_company_code.company_%s' % company_id_int
            code = self.env['ir.config_parameter'].sudo().get_param(key)
            if not code or not code.strip():
                raise UserError(_('Configure el Código de empresa ERP para Tienda en Catastro → Configuración → Configurar Consumidor Final antes de enviar %s a Radis.') % order.name)
            code = code.strip()
            if len(code) > 64 or any(ord(ch) < 32 for ch in code):
                raise UserError(_('Código ERP de Tienda inválido para la empresa %s.') % order.company_id.display_name)
            modified = dict(entry)
            # No cambiar company_id, order_company_name ni los códigos normales.
            modified['order_company_code'] = code
            enriched.append(modified)

        return super().call_api(api_name, method=method, company_id=company_id,
                                params=enriched, headers_extra=headers_extra)
