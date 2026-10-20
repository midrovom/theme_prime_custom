# -*- coding: utf-8 -*-
"""Verificación y reparación acotada de datos comerciales en staging ERP.

No escribe en transcash.guia, transcash.guia.linea, embarques ni liquidaciones.
"""
import logging

from odoo import api, models, _
from odoo.exceptions import AccessError, UserError
from .commercial_parser import extract_commercial, guide_lines
from .sync import clean, number

_logger = logging.getLogger(__name__)


class TCGuideCommercialAudit(models.Model):
    _inherit = 'tc.guide.sync'

    def _commercial_admin_check(self):
        if not (self.env.is_superuser()
                or self.env.user.has_group('transcash_guias_api.group_tc_sync_admin')
                or self.env.user.has_group('base.group_system')):
            raise AccessError(_('Únicamente administradores de integración o Ajustes.'))

    def _commercial_api_response(self, company_id):
        config = self.env['api.administrator'].sudo().search([
            ('name', '=', 'getguiaslogistica'), ('type', '=', 'get'),
            ('status', '=', 'A'), ('company_id', '=', company_id)], limit=1)
        if not config:
            raise UserError(_('Configure getguiaslogistica GET activa en API Administrator.'))
        response = self.env['api.administrator'].sudo().call_api(
            'getguiaslogistica', method='get', company_id=company_id)
        if not isinstance(response, dict) or response.get('success') is False:
            raise UserError(_('La API devolvió error o un objeto inesperado.'))
        data = response.get('data')
        if not isinstance(data, list):
            raise UserError(_('Se esperaba data: [guías] en la respuesta ERP.'))
        return data

    @api.model
    def run_commercial_audit(self, company_id=None, repair=False):
        self._commercial_admin_check()
        company_id = company_id or self.env.company.id
        if not self.env['res.company'].browse(company_id).exists():
            raise UserError(_('Empresa inexistente.'))
        data = self._commercial_api_response(company_id)
        Guide = self.env['tc.guide'].sudo()
        Line = self.env['tc.guide.line'].sudo()
        Private = self.env['tc.guide.line.private'].sudo()
        Product = self.env['tc.product'].sudo()
        base_domain = [('company_id', '=', company_id)]
        counters = {name: 0 for name in (
            'guides_api', 'lines_api', 'brand_api', 'supplier_api', 'lines_empty_api',
            'guides_missing', 'lines_missing', 'private_missing',
            'brand_missing_db', 'supplier_missing_db', 'brand_mismatch',
            'supplier_mismatch', 'lines_repaired', 'private_created',
            'brands_linked', 'suppliers_linked', 'errors')}
        failures = []
        samples = []
        guide_cache = {}
        for row in data:
            if not isinstance(row, dict):
                counters['errors'] += 1
                failures.append('Elemento de data no es objeto JSON')
                continue
            counters['guides_api'] += 1
            external = clean(row.get('id_externo'))
            if external not in guide_cache:
                guide_cache[external] = Guide.search(base_domain + [('external_id', '=', external)], limit=1) if external else Guide.browse()
            guide = guide_cache[external]
            if not guide:
                counters['guides_missing'] += 1
            lines = guide_lines(row)
            if not lines and len(samples) < 12:
                samples.append('Guía %s sin arreglo detalle/lineas/productos; claves: %s' % (
                    external or '?', ', '.join(sorted(str(k) for k in row.keys())[:22])))
            for item in lines:
                if not isinstance(item, dict):
                    counters['errors'] += 1
                    continue
                counters['lines_api'] += 1
                ext_line = clean(item.get('id_linea'))
                parsed = extract_commercial(item)
                has_brand = bool(parsed['brand_code'] or parsed['brand_name'])
                has_supplier = bool(parsed['supplier_code'] or parsed['supplier_name'])
                counters['brand_api'] += int(has_brand)
                counters['supplier_api'] += int(has_supplier)
                counters['lines_empty_api'] += int(not has_brand and not has_supplier)
                if not guide or not ext_line:
                    continue
                line = Line.search([('guide_id', '=', guide.id), ('external_line_id', '=', ext_line)], limit=1)
                if not line:
                    counters['lines_missing'] += 1
                    if repair and clean(item.get('sku')):
                        try:
                            with self.env.cr.savepoint():
                                sku = clean(item['sku'])
                                product = Product.search(base_domain + [('sku', '=', sku)], limit=1)
                                if not product:
                                    product = Product.create({'company_id': company_id, 'sku': sku,
                                                              'name': clean(item.get('descripcion')) or sku})
                                line = Line.create({
                                    'guide_id': guide.id, 'external_line_id': ext_line,
                                    'product_id': product.id, 'sku': sku,
                                    'name': clean(item.get('descripcion')) or sku,
                                    'quantity': number(item.get('cantidad')),
                                    'weight_kg': number(item.get('peso_kg')),
                                    'pallets': number(item.get('pallets')),
                                    'boxes': number(item.get('cajas')),
                                })
                                counters['lines_repaired'] += 1
                        except Exception as exc:
                            counters['errors'] += 1
                            failures.append('Guía %s línea %s: %s' % (external, ext_line, str(exc)[:120]))
                            continue
                    else:
                        if len(samples) < 12:
                            samples.append('Línea no importada %s / %s' % (external, ext_line))
                        continue
                private = Private.search([('line_id', '=', line.id)], limit=1)
                if not private:
                    counters['private_missing'] += 1
                else:
                    counters['brand_missing_db'] += int(has_brand and not (private.brand_code_raw or private.brand_name_raw))
                    counters['supplier_missing_db'] += int(has_supplier and not (private.supplier_code_raw or private.supplier_name_raw))
                    counters['brand_mismatch'] += int(bool(parsed['brand_code']) and
                        clean(private.brand_code_raw).upper() != parsed['brand_code'].upper())
                    counters['supplier_mismatch'] += int(bool(parsed['supplier_code']) and
                        clean(private.supplier_code_raw).upper() != parsed['supplier_code'].upper())
                if repair:
                    try:
                        with self.env.cr.savepoint():
                            old_brand = bool(private.brand_id) if private else False
                            old_supplier = bool(private.supplier_id) if private else False
                            self._commercial_line_payload(line, item, company_id)
                            saved = Private.search([('line_id', '=', line.id)], limit=1)
                            counters['private_created'] += int(not private and bool(saved))
                            counters['brands_linked'] += int(not old_brand and bool(saved.brand_id))
                            counters['suppliers_linked'] += int(not old_supplier and bool(saved.supplier_id))
                    except Exception as exc:
                        counters['errors'] += 1
                        _logger.exception('Error reparando datos privados guía %s línea %s', external, ext_line)
                        failures.append('Guía %s línea %s: %s' % (external, ext_line, str(exc)[:120]))
                if (has_brand or has_supplier) and not private and len(samples) < 12:
                    samples.append('Faltaba ficha privada %s / %s (marca=%s proveedor=%s)' % (
                        external, ext_line, parsed['brand_code'], parsed['supplier_code']))
        title = 'REPARACIÓN' if repair else 'AUDITORÍA (sin modificaciones)'
        details = [title, 'Empresa: %s' % company_id,
                   'El ERP se leyó usando getguiaslogistica de API Administrator.',
                   'Ningún viaje, ruta, embarque o liquidación fue modificado.', '']
        label_map = {
            'guides_api': 'Guías recibidas ERP', 'lines_api': 'Líneas recibidas ERP',
            'brand_api': 'Líneas ERP que traen marca', 'supplier_api': 'Líneas ERP que traen proveedor de producto',
            'lines_empty_api': 'Líneas ERP sin información comercial',
            'guides_missing': 'Guías sin registro importado tc.guide',
            'lines_missing': 'Líneas sin registro tc.guide.line (antes de reparar)',
            'private_missing': 'Líneas sin registro privado (antes de reparar)',
            'brand_missing_db': 'Marca ausente en registro privado existente',
            'supplier_missing_db': 'Proveedor ausente en registro privado existente',
            'brand_mismatch': 'Código marca diferente al ERP',
            'supplier_mismatch': 'Código proveedor diferente al ERP',
            'lines_repaired': 'Líneas staging creadas', 'private_created': 'Fichas privadas creadas',
            'brands_linked': 'Marcas vinculadas', 'suppliers_linked': 'Proveedores vinculados',
            'errors': 'Errores',
        }
        details += ['%s: %s' % (label_map[k], value) for k, value in counters.items()]
        if samples:
            details += ['', 'EJEMPLOS:', *samples]
        if failures:
            details += ['', 'ERRORES:', *failures[:25]]
        if counters['brand_api'] == 0 or counters['supplier_api'] == 0:
            details += ['', 'ATENCIÓN: la respuesta actual del ERP no trae marcas/proveedores '
                        'en las líneas. Revisar el generador Symfony del JSON.']
        log = self.env['tc.guide.sync.log'].sudo().create({
            'company_id': company_id, 'api_name': 'getguiaslogistica / %s' % title,
            'created_count': counters['private_created'] + counters['lines_repaired'],
            'updated_count': counters['brands_linked'] + counters['suppliers_linked'],
            'error_count': counters['errors'],
            'details': '\n'.join(details)[:50000],
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _('Diagnóstico comercial ERP'),
            'res_model': 'tc.guide.sync.log', 'res_id': log.id,
            'view_mode': 'form', 'target': 'current',
        }
