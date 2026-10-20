import logging
import re
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from .commercial_parser import extract_commercial, guide_lines

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
    def _commercial_brand(self, company_id, code, name):
        """Maestro privado de marca, localizado por código ERP (empresa)."""
        code = clean(code).upper()
        name = clean(name)
        if not code:
            return False
        Brand = self.env['tc.product.brand'].sudo()
        rec = Brand.search([('company_id', '=', company_id), ('code', '=', code)], limit=1)
        if rec:
            if name and name != rec.name:
                rec.write({'name': name})
        else:
            rec = Brand.create({'company_id': company_id, 'code': code, 'name': name or code})
        return rec

    @api.model
    def _commercial_supplier(self, company_id, code, name, tax_id):
        """Proveedor privado: RUC/identificación fiscal primero, código ERP si no hay RUC.

        Nunca usa referencia_erp como RUC: en los ejemplos esa referencia
        tiene valores ambiguos y algunos son códigos de otro tipo.
        """
        code = clean(code).upper()
        name = clean(name)
        tax_id = re.sub(r'[^A-Za-z0-9]', '', clean(tax_id)).upper()
        if not code and not tax_id:
            return False
        Supplier = self.env['tc.product.supplier'].sudo()
        base = [('company_id', '=', company_id)]
        by_tax = Supplier.search(base + [('tax_id', '=', tax_id)], limit=1) if tax_id else Supplier.browse()
        by_code = Supplier.search(base + [('external_code', '=', code)], limit=1) if code else Supplier.browse()
        if by_tax and by_code and by_tax != by_code:
            # Nunca fusionar ni reasignar RUC/codigo silenciosamente.
            _logger.warning('Proveedor producto: conflicto RUC=%s código=%s; revisar maestros %s y %s.',
                            tax_id, code, by_tax.id, by_code.id)
            return by_tax
        rec = by_tax or by_code
        if not rec:
            return Supplier.create({
                'company_id': company_id, 'tax_id': tax_id or False,
                'external_code': code or False, 'name': name or code or tax_id,
            })
        changes = {}
        if name and rec.name != name:
            changes['name'] = name
        if tax_id and not rec.tax_id:
            changes['tax_id'] = tax_id
        elif tax_id and rec.tax_id and re.sub(r'[^A-Za-z0-9]', '', rec.tax_id).upper() != tax_id:
            _logger.warning('Proveedor producto: código %s tiene RUC diferente. Se conserva RUC del maestro.', code)
        if code and not rec.external_code:
            changes['external_code'] = code
        elif code and rec.external_code and rec.external_code != code:
            _logger.warning('Proveedor producto: RUC %s tiene otro código ERP. Se conserva código previo.', tax_id)
        if changes:
            rec.write(changes)
        return rec

    @api.model
    def _commercial_line_payload(self, line, item, company_id):
        """Persistir y relacionar marca/proveedor en el modelo privado, nunca en transcash.guia.

        Permite volver a sincronizar líneas ya existentes y recupera los
        campos crudos de las versiones anteriores cuando el ERP omite datos.
        """
        Private = self.env['tc.guide.line.private'].sudo()
        private = Private.search([('line_id', '=', line.id)], limit=1)
        extracted = extract_commercial(item)

        def previous(field):
            return clean(private[field]) if private else ''

        # Se privilegia el valor no vacío del ERP; si omite una clave se
        # conserva el último valor conocido de la misma línea.
        brand_code = extracted['brand_code'] or previous('brand_code_raw')
        brand_name = extracted['brand_name'] or previous('brand_name_raw')
        supplier_code = extracted['supplier_code'] or previous('supplier_code_raw')
        supplier_name = extracted['supplier_name'] or previous('supplier_name_raw')
        supplier_tax = extracted['supplier_tax'] or previous('supplier_tax_raw')
        supplier_reference = extracted['supplier_reference'] or previous('supplier_reference_raw')
        # Se preserva el dato crudo para auditoría aunque no haya RUC.
        brand_rec = self._commercial_brand(company_id, brand_code, brand_name)
        supplier_rec = self._commercial_supplier(company_id, supplier_code, supplier_name, supplier_tax)
        values = {
            'line_id': line.id,
            'brand_id': brand_rec.id if brand_rec else (private.brand_id.id if private else False),
            'supplier_id': supplier_rec.id if supplier_rec else (private.supplier_id.id if private else False),
            'brand_code_raw': brand_code,
            'brand_name_raw': brand_name,
            'supplier_code_raw': supplier_code,
            'supplier_name_raw': supplier_name,
            'supplier_reference_raw': supplier_reference,
            'supplier_tax_raw': supplier_tax,
        }
        if private:
            delta = {}
            for key, value in values.items():
                old_value = private[key]
                old = getattr(old_value, 'id', old_value) if key in ('line_id', 'brand_id', 'supplier_id') else old_value
                if old != value:
                    delta[key] = value
            if delta:
                private.write(delta)
        else:
            private = Private.create(values)
        return private

    @api.model
    def reconcile_private_data(self, company_id):
        """Reparar vínculos comerciales a partir de datos crudos ya guardados, sin API."""
        if not (self.env.user.has_group('transcash_guias_api.group_tc_sync_admin') or
                self.env.user.has_group('base.group_system')):
            raise UserError(_('Solo administradores autorizados pueden consultar datos comerciales.'))
        company = self.env['res.company'].browse(company_id).exists()
        if not company:
            raise UserError(_('Empresa no válida.'))
        records = self.env['tc.guide.line.private'].sudo().search([('company_id', '=', company_id)])
        processed = brands = suppliers = 0
        errors = []
        for private in records:
            try:
                with self.env.cr.savepoint():
                    had_brand, had_supplier = bool(private.brand_id), bool(private.supplier_id)
                    updated = self._commercial_line_payload(private.line_id, {}, company_id)
                    brands += int(not had_brand and bool(updated.brand_id))
                    suppliers += int(not had_supplier and bool(updated.supplier_id))
                    processed += 1
            except Exception as exc:
                _logger.exception('Error reconciliando datos comerciales de línea %s', private.line_id.id)
                errors.append('%s: %s' % (private.line_id.id, str(exc)))
        return {'processed': processed, 'brands_linked': brands,
                'suppliers_linked': suppliers, 'errors': errors}

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
        lines = guide_lines(data)
        if not isinstance(lines, list):
            raise ValidationError('detalle debe ser una lista.')
        line_ids = [clean(x.get('id_linea')) for x in lines if isinstance(x, dict)]
        if len(line_ids) != len(lines) or not all(line_ids) or len(set(line_ids)) != len(line_ids):
            raise ValidationError('Líneas sin id_linea o id_linea duplicados.')

        transport_id = False
        if clean(transport.get('ruc')):
            # Normalizar el RUC ANTES de buscar el maestro; no duplicar por
            # guiones/espacios o por registros históricos sin normalizar.
            ruc = re.sub(r'[^A-Za-z0-9]', '', clean(transport['ruc']).upper())
            Transport = self.env['tc.transport'].sudo()
            matches = Transport.search(common).filtered(
                lambda x: re.sub(r'[^A-Za-z0-9]', '', (x.ruc or '').upper()) == ruc)
            if matches:
                transport_record = matches.sorted('id')[0]
                if len(matches) > 1:
                    _logger.warning('Maestros de transporte duplicados con RUC normalizado; RUC=%s', ruc)
                if clean(transport.get('nombre')) and transport_record.name != clean(transport.get('nombre')):
                    transport_record.write({'name': clean(transport.get('nombre'))})
            else:
                transport_record = Transport.create({
                    'ruc': ruc, 'name': clean(transport.get('nombre')) or ruc,
                    'company_id': company_id,
                })
            transport_id = transport_record.id
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

            self._commercial_line_payload(line, item, company_id)
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
        commercial_lines = commercial_brands = commercial_suppliers = 0
        incoming_brands = incoming_suppliers = 0
        unexpected_sample = []
        errors = []
        for row in data:
            try:
                # Aísla escrituras parcialmente fallidas de una guía.
                with self.env.cr.savepoint():
                    incoming = guide_lines(row)
                    for payload in incoming:
                        commercial = extract_commercial(payload)
                        incoming_brands += int(bool(commercial['brand_code'] or commercial['brand_name']))
                        incoming_suppliers += int(bool(commercial['supplier_code'] or commercial['supplier_name']))
                        if (not commercial['brand_code'] and not commercial['supplier_code']
                                and len(unexpected_sample) < 3):
                            unexpected_sample.append('%s: línea %s sin claves comerciales; claves recibidas: %s' % (
                                clean(row.get('id_externo')), clean(payload.get('id_linea')),
                                ', '.join(sorted(str(k) for k in payload.keys())[:20])))
                    was_created = self._import_one(row, company_id)
                    staged = self.env['tc.guide'].sudo().search([
                        ('company_id', '=', company_id),
                        ('external_id', '=', clean(row.get('id_externo')))], limit=1)
                    if staged:
                        privates = self.env['tc.guide.line.private'].sudo().search([
                            ('line_id', 'in', staged.line_ids.ids)])
                        commercial_lines += len(privates)
                        commercial_brands += len(privates.filtered(lambda p: p.brand_code_raw or p.brand_name_raw))
                        commercial_suppliers += len(privates.filtered(lambda p: p.supplier_code_raw or p.supplier_name_raw))
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
            'error_count': len(errors), 'details': (
                'Vínculos Portal pendientes: %s\n'
                'Líneas ERP con marca: %s; con proveedor de producto: %s\n'
                'Registros privados en guías procesadas: %s; con marca: %s; con proveedor: %s\n'
                'Posibles problemas de estructura JSON:\n%s\n'
                'Errores:\n%s' % (
                    pending_links, incoming_brands, incoming_suppliers,
                    commercial_lines, commercial_brands, commercial_suppliers,
                    '\n'.join(unexpected_sample), '\n'.join(errors)))[:20000],
        })
        return {'created': created, 'updated': updated, 'pending_links': pending_links,
                'incoming_brands': incoming_brands, 'incoming_suppliers': incoming_suppliers,
                'stored_brands': commercial_brands, 'stored_suppliers': commercial_suppliers,
                'errors': errors}


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
                'message': _('Guías creadas: %(new)s, actualizadas: %(updated)s. Líneas con marca desde ERP: %(bm)s; con proveedor de producto: %(sp)s. Pendientes Portal: %(pending)s; errores: %(bad)s') % {
                    'new': counts['created'], 'updated': counts['updated'],
                    'bm': counts['incoming_brands'], 'sp': counts['incoming_suppliers'],
                    'pending': counts['pending_links'], 'bad': len(counts['errors'])},
                'type': 'warning' if (counts['errors'] or not counts['incoming_brands'] or not counts['incoming_suppliers']) else 'success',
                'sticky': bool(counts['errors'] or not counts['incoming_brands'] or not counts['incoming_suppliers']),
            }}
        return super().button_run_sync()
