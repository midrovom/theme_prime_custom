import logging
import re
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


def clean(v):
    return str(v).strip() if v is not None and v is not False else ''


def number(v):
    try:
        return float(v) if v is not None and v != '' else 0.0
    except (ValueError, TypeError):
        raise ValidationError('Número inválido: %s' % v)


def date_value(v):
    s = clean(v)
    if not s:
        return False
    match = re.match(r'^(\d{4})[./-](\d{1,2})[./-](\d{1,2})', s)
    if match:
        y, m, d = map(int, match.groups())
    else:
        match = re.match(r'^(\d{1,2})[./-](\d{1,2})[./-](\d{4})', s)
        if not match:
            raise ValidationError('Fecha inválida: %s' % s)
        d, m, y = map(int, match.groups())
    from datetime import date
    try:
        return date(y, m, d).isoformat()
    except ValueError:
        raise ValidationError('Fecha inválida: %s' % s)


class TCGuideSync(models.Model):
    _name = 'tc.guide.sync'
    _description = 'Servicio de integración de guías ERP'

    @api.model
    def _master(self, model, domain, values):
        rec = self.env[model].sudo().search(domain, limit=1)
        if rec:
            changed = {k: v for k, v in values.items() if rec[k] != v and v not in ('', None, False)}
            if changed:
                rec.write(changed)
        else:
            rec = self.env[model].sudo().create(values)
        return rec

    @api.model
    def _import_one(self, data, company_id):
        if not isinstance(data, dict):
            raise ValidationError('Cada guía debe ser un objeto JSON.')
        external = clean(data.get('id_externo'))
        name = clean(data.get('numero_guia'))
        if not external or not name:
            raise ValidationError('Se exige id_externo y numero_guia.')
        common = [('company_id', '=', company_id)]
        transport = data.get('transportista') or {}
        driver = data.get('chofer') or {}
        vehicle = data.get('vehiculo') or {}
        sender = data.get('remitente') or {}
        recipient = data.get('destinatario') or {}
        route = data.get('ruta') or {}
        dates = data.get('fechas') or {}
        lines = data.get('detalle', data.get('lineas', []))
        if not isinstance(lines, list):
            raise ValidationError('detalle debe ser una lista.')
        line_ids = [clean(x.get('id_linea')) for x in lines if isinstance(x, dict)]
        if len(line_ids) != len(lines) or not all(line_ids) or len(set(line_ids)) != len(line_ids):
            raise ValidationError('Líneas sin id_linea o id_linea duplicados.')

        transport_id = False
        if clean(transport.get('ruc')):
            ruc = clean(transport['ruc']).replace(' ', '')
            transport_id = self._master('tc.transport', common + [('ruc', '=', ruc)], {
                'ruc': ruc, 'name': clean(transport.get('nombre')) or ruc, 'company_id': company_id,
            }).id
        driver_id = False
        if clean(driver.get('identificacion')):
            ident = clean(driver['identificacion'])
            driver_id = self._master('tc.driver', common + [('identification', '=', ident)], {
                'identification': ident, 'name': clean(driver.get('nombre')) or ident, 'company_id': company_id,
            }).id
        vehicle_id = False
        if clean(vehicle.get('placa')):
            plate = clean(vehicle['placa']).upper()
            vehicle_id = self._master('tc.vehicle', common + [('plate', '=', plate)], {
                'plate': plate, 'company_id': company_id,
            }).id

        def address(kind, code, name, address='', city=''):
            code = clean(code)
            if not code:
                return False
            return self._master('tc.address', common + [('kind', '=', kind), ('external_code', '=', code)], {
                'kind': kind, 'external_code': code, 'name': clean(name) or code,
                'address': clean(address), 'city': clean(city), 'company_id': company_id,
            }).id

        sender_id = address('sender', sender.get('codigo'), sender.get('nombre'), route.get('direccion_origen'))
        recipient_id = address('recipient', recipient.get('codigo'), recipient.get('nombre'), route.get('direccion_destino'))
        destination_id = address('destination', route.get('destino_codigo'), route.get('destino_ciudad') or route.get('direccion_destino'), route.get('direccion_destino'), route.get('destino_ciudad'))

        vals = {
            'company_id': company_id, 'external_id': external, 'name': name,
            'document_type': clean(data.get('tipo_documento')),
            'document_number': clean(data.get('numero_documento')),
            'erp_state': clean(data.get('estado_erp')),
            'transport_id': transport_id,
            'transport_tax_raw': clean(transport.get('ruc')),
            'recipient_tax_raw': clean(recipient.get('identificacion') or recipient.get('ruc')),
            'transport_name': clean(transport.get('nombre')),
            'driver_id': driver_id, 'vehicle_id': vehicle_id,
            'sender_id': sender_id, 'recipient_id': recipient_id, 'destination_id': destination_id,
            'origin_address': clean(route.get('direccion_origen')),
            'destination_address': clean(route.get('direccion_destino')),
            'destination_city': clean(route.get('destino_ciudad')),
            'erp_start_date': date_value(dates.get('inicio_traslado')),
            'erp_end_date': date_value(dates.get('fin_traslado')),
            'erp_planned_date': date_value(dates.get('prevista')),
            'cargo_description': clean(data.get('descripcion_carga')),
            'last_sync': fields.Datetime.now(),
        }
        Guide = self.env['tc.guide'].sudo()
        guide = Guide.search(common + [('external_id', '=', external)], limit=1)
        created = not bool(guide)
        if guide:
            guide.write(vals)
        else:
            guide = Guide.create(vals)

        for item in lines:
            sku = clean(item.get('sku'))
            line_ext = clean(item.get('id_linea'))
            if not sku:
                raise ValidationError('SKU vacío en guía %s línea %s' % (external, line_ext))
            product = self._master('tc.product', common + [('sku', '=', sku)], {
                'sku': sku, 'name': clean(item.get('descripcion')) or sku, 'company_id': company_id,
            })
            line_vals = {
                'guide_id': guide.id, 'external_line_id': line_ext, 'product_id': product.id,
                'sku': sku, 'name': clean(item.get('descripcion')) or sku,
                'quantity': number(item.get('cantidad')),
                'weight_kg': number(item.get('peso_kg')),
                'pallets': number(item.get('pallets')),
                'boxes': number(item.get('cajas')),
            }
            Line = self.env['tc.guide.line'].sudo()
            line = Line.search([('guide_id', '=', guide.id), ('external_line_id', '=', line_ext)], limit=1)
            if line:
                line.write(line_vals)
            else:
                line = Line.create(line_vals)

            brand = item.get('marca') or {}
            supplier = item.get('proveedor_producto') or {}
            brand_id = False
            code = clean(brand.get('codigo'))
            if code:
                brand_id = self._master('tc.product.brand', common + [('code', '=', code)], {
                    'code': code, 'name': clean(brand.get('nombre')) or code, 'company_id': company_id,
                }).id
            supplier_id = False
            tax_id = clean(supplier.get('identificacion_fiscal') or supplier.get('ruc'))
            if tax_id:
                supplier_id = self._master('tc.product.supplier', common + [('tax_id', '=', tax_id)], {
                    'tax_id': tax_id, 'name': clean(supplier.get('nombre')) or tax_id,
                    'external_code': clean(supplier.get('codigo')), 'company_id': company_id,
                }).id
            private_vals = {
                'line_id': line.id, 'brand_id': brand_id, 'supplier_id': supplier_id,
                'supplier_code_raw': clean(supplier.get('codigo')),
                'supplier_reference_raw': clean(supplier.get('referencia_erp')),
                'supplier_name_raw': clean(supplier.get('nombre')),
                'supplier_tax_raw': tax_id,
                'brand_code_raw': code, 'brand_name_raw': clean(brand.get('nombre')),
            }
            Private = self.env['tc.guide.line.private'].sudo()
            private = Private.search([('line_id', '=', line.id)], limit=1)
            if private:
                private.write(private_vals)
            else:
                Private.create(private_vals)
        # Nunca se eliminan líneas ausentes: podría haber cambios operativos posteriores.
        return created

    @api.model
    def sync_from_api(self, company_id):
        company = self.env['res.company'].browse(company_id).exists()
        if not company:
            raise UserError(_('Empresa no válida.'))
        administrator = self.env['api.administrator'].sudo()
        config = administrator.search([
            ('name', '=', 'getguiaslogistica'), ('type', '=', 'get'),
            ('company_id', '=', company_id), ('status', '=', 'A'),
        ], limit=1)
        if not config:
            raise UserError(_('Configure y active GET getguiaslogistica en api.administrator.'))
        result = administrator.call_api('getguiaslogistica', method='get', company_id=company_id)
        if not isinstance(result, dict) or result.get('success') is False:
            raise UserError(_('La API devolvió un error: %s') % (result,))
        data = result.get('data')
        if not isinstance(data, list):
            raise UserError(_('La API no devolvió data como lista.'))
        created = updated = pending_links = 0
        errors = []
        for row in data:
            try:
                # Aísla escrituras parcialmente fallidas de una guía.
                with self.env.cr.savepoint():
                    was_created = self._import_one(row, company_id)
                    staged = self.env['tc.guide'].sudo().search([
                        ('company_id', '=', company_id),
                        ('external_id', '=', clean(row.get('id_externo')))], limit=1)
                    if staged:
                        pending_links += int(staged.master_link_state == 'pending')
                        if staged.publication_state == 'error':
                            errors.append('%s: error publicando: %s' % (
                                staged.external_id, staged.publication_note or 'Ver historial'))
                    created += int(was_created)
                    updated += int(not was_created)
            except Exception as exc:
                _logger.exception('Error importando guía ERP')
                external = clean(row.get('id_externo')) if isinstance(row, dict) else '?'
                errors.append('%s: %s' % (external, str(exc)))
        self.env['tc.guide.sync.log'].sudo().create({
            'company_id': company_id, 'api_name': 'getguiaslogistica',
            'created_count': created, 'updated_count': updated,
            'error_count': len(errors), 'details': ('Vínculos Portal pendientes: %s\n' % pending_links + '\n'.join(errors))[:20000],
        })
        return {'created': created, 'updated': updated, 'pending_links': pending_links, 'errors': errors}


class APIAdministrator(models.Model):
    _inherit = 'api.administrator'

    def button_run_sync(self):
        logistics = self.filtered(lambda r: r.name == 'getguiaslogistica')
        if logistics:
            if len(self) != 1:
                raise UserError(_('Ejecute la sincronización de una API por vez.'))
            if not self.env.user.has_group('transcash_guias_api.group_tc_sync_admin'):
                raise UserError(_('No tiene permiso para sincronizar guías.'))
            if self.type != 'get' or self.status != 'A':
                raise UserError(_('La API debe estar activa y ser GET.'))
            counts = self.env['tc.guide.sync'].sync_from_api(self.company_id.id)
            return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
                'title': _('Guías ERP sincronizadas'),
                'message': _('Creadas: %(new)s, actualizadas: %(updated)s, pendientes de Portal: %(pending)s, errores: %(bad)s') % {
                    'new': counts['created'], 'updated': counts['updated'], 'pending': counts['pending_links'], 'bad': len(counts['errors'])},
                'type': 'warning' if counts['errors'] else 'success', 'sticky': bool(counts['errors']),
            }}
        return super().button_run_sync()
