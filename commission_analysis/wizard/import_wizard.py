import base64
import hashlib
import io
import logging
import os
import struct
import unicodedata
import zipfile
from datetime import date, datetime

from odoo import fields, models, _
from odoo.exceptions import UserError


MONTHS = {
    'ene': 1, 'feb': 2, 'mar': 3, 'abr': 4, 'may': 5, 'jun': 6,
    'jul': 7, 'ago': 8, 'sept': 9, 'sep': 9, 'oct': 10, 'nov': 11, 'dic': 12,
}
CHUNK = 2000
MAX_ARCHIVE_MEMBER_SIZE = 512 * 1024 * 1024
MAX_ARCHIVE_TOTAL_SIZE = 1024 * 1024 * 1024
_logger = logging.getLogger(__name__)


def normalize_text(value):
    text = str(value or '').strip()
    text = unicodedata.normalize('NFKD', text)
    return ''.join(ch for ch in text if not unicodedata.combining(ch)).casefold()


def make_icc_key(value, length=18):
    digits = ''.join(ch for ch in str(value or '').strip() if ch.isdigit())
    # Una clave más corta que la longitud configurada no es segura para conciliación.
    return digits[:length] if len(digits) >= length else ''


def normalize_percentage(value):
    """Return (source_value, percent_points). Claro exports 20% as numeric 0.20."""
    if value in (None, ''):
        return 0.0, 0.0
    try:
        if isinstance(value, str):
            clean = value.strip().replace('%', '').replace(',', '.')
            numeric = float(clean or 0)
            if '%' in value:
                return numeric / 100.0, numeric
        else:
            numeric = float(value)
        return numeric, numeric * 100.0 if abs(numeric) <= 1.0 and numeric != 0 else numeric
    except (TypeError, ValueError):
        return 0.0, 0.0


def parse_date(value):
    if not value:
        return False
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip().lower().replace(',', '')
    for key, month in MONTHS.items():
        if text.startswith(key + ' '):
            parts = text.split()
            if len(parts) >= 3:
                try:
                    return datetime(int(parts[-1]), month, int(parts[-2])).date()
                except (ValueError, TypeError):
                    return False
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y'):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    return False


def dbf_rows(data):
    """Minimal dBase/FoxBase reader for the supplier purchase export."""
    if len(data) < 64:
        raise UserError(_('El archivo de compras no tiene una estructura DBF válida.'))
    header_len = struct.unpack('<H', data[8:10])[0]
    record_len = struct.unpack('<H', data[10:12])[0]
    record_count = struct.unpack('<I', data[4:8])[0]
    if header_len <= 32 or record_len <= 1 or header_len > len(data):
        raise UserError(_('Cabecera DBF inválida en el archivo de compras.'))

    field_specs = []
    pos = 32
    while pos + 32 <= header_len and data[pos] != 0x0D:
        descriptor = data[pos:pos + 32]
        field_name = descriptor[:11].split(b'\x00')[0].decode('latin1').strip()
        field_type = chr(descriptor[11])
        field_len = descriptor[16]
        decimals = descriptor[17]
        field_specs.append((field_name, field_type, field_len, decimals))
        pos += 32

    max_records = max(0, (len(data) - header_len) // record_len)
    record_count = min(record_count, max_records)
    for idx in range(record_count):
        record = data[header_len + idx * record_len:header_len + (idx + 1) * record_len]
        if not record or record[:1] == b'*':
            continue
        values = {}
        cursor = 1
        for field_name, field_type, field_len, _decimals in field_specs:
            raw = record[cursor:cursor + field_len]
            cursor += field_len
            text = raw.decode('latin1', 'ignore').strip()
            if field_type in 'NF':
                try:
                    if not text:
                        values[field_name] = 0 if _decimals == 0 else 0.0
                    elif _decimals == 0:
                        values[field_name] = int(float(text))
                    else:
                        values[field_name] = float(text)
                except ValueError:
                    values[field_name] = 0 if _decimals == 0 else 0.0
            elif field_type == 'D' and len(text) == 8:
                try:
                    values[field_name] = datetime.strptime(text, '%Y%m%d').date()
                except ValueError:
                    values[field_name] = False
            else:
                values[field_name] = text
        yield idx + 1, values


class CommissionImportWizard(models.TransientModel):
    _name = 'commission.import.wizard'
    _description = 'Importar Compras / Liquidaciones'

    import_type = fields.Selection(
        [('purchase', 'Compras'), ('settlement', 'Liquidación Claro')],
        required=True, default='settlement',
    )
    purchase_batch_id = fields.Many2one('commission.purchase.batch')
    settlement_batch_id = fields.Many2one('commission.settlement.batch')
    file_ids = fields.Many2many('ir.attachment', string='Archivos', required=True)

    def _decode_attachment(self, attachment):
        """Decode an ir.attachment once and return raw bytes with a clear user error."""
        if not attachment.datas:
            raise UserError(_('El archivo %s no contiene datos.') % attachment.name)
        try:
            return base64.b64decode(attachment.datas)
        except Exception as exc:
            raise UserError(_('No se pudo decodificar el archivo %s: %s') % (attachment.name, exc)) from exc

    def _iter_attachment_payloads(self, attachment):
        """Yield logical source files from a direct attachment or a ZIP container.

        The purchase export used by Telecity is a ~110 MB DBF with an .XLS extension but
        compresses to around 1 MB. Supporting ZIP avoids browser/proxy upload limits while
        preserving the original file bytes and audit traceability. XLSX files are ZIP-based
        internally, so only an explicit .zip extension is treated as a container.
        """
        raw = self._decode_attachment(attachment)
        attachment_name = attachment.name or 'archivo'
        extension = os.path.splitext(attachment_name)[1].lower()
        if extension != '.zip':
            yield {
                'source_name': attachment_name,
                'display_name': attachment_name,
                'archive_name': False,
                'archive_member': False,
                'data': raw,
            }
            return

        try:
            archive = zipfile.ZipFile(io.BytesIO(raw))
        except (zipfile.BadZipFile, OSError) as exc:
            raise UserError(_('El archivo %s no es un ZIP válido: %s') % (attachment_name, exc)) from exc

        total_size = 0
        yielded = 0
        with archive:
            for info in archive.infolist():
                if info.is_dir():
                    continue
                member = info.filename
                # Ignore common metadata files from macOS/Windows archives.
                base = os.path.basename(member)
                if not base or member.startswith('__MACOSX/') or base in ('.DS_Store', 'Thumbs.db'):
                    continue
                if info.flag_bits & 0x1:
                    raise UserError(_('El ZIP %s contiene un archivo cifrado (%s), no soportado.') % (attachment_name, member))
                if info.file_size > MAX_ARCHIVE_MEMBER_SIZE:
                    raise UserError(_(
                        'El archivo %s dentro de %s supera el límite de seguridad de %s MB.'
                    ) % (member, attachment_name, MAX_ARCHIVE_MEMBER_SIZE // (1024 * 1024)))
                total_size += info.file_size
                if total_size > MAX_ARCHIVE_TOTAL_SIZE:
                    raise UserError(_(
                        'El contenido descomprimido de %s supera el límite de seguridad de %s MB.'
                    ) % (attachment_name, MAX_ARCHIVE_TOTAL_SIZE // (1024 * 1024)))
                try:
                    payload = archive.read(info)
                except Exception as exc:
                    raise UserError(_('No se pudo leer %s dentro de %s: %s') % (member, attachment_name, exc)) from exc
                source_name = '%s::%s' % (attachment_name, member)
                yield {
                    'source_name': source_name,
                    'display_name': base,
                    'archive_name': attachment_name,
                    'archive_member': member,
                    'data': payload,
                }
                yielded += 1
        if not yielded:
            raise UserError(_('El ZIP %s no contiene archivos para importar.') % attachment_name)

    def _validate_payload_type(self, payload):
        name = payload['display_name']
        ext = os.path.splitext(name)[1].lower()
        if self.import_type == 'purchase':
            # Claro/Telecity supplies a DBF/FoxBase file with an .XLS extension.
            if ext not in ('.xls', '.dbf', ''):
                raise UserError(_(
                    'El archivo %s no corresponde a Compras. Use .XLS/.DBF o un ZIP que los contenga.'
                ) % name)
        else:
            if ext not in ('.xlsx', '.xlsm'):
                raise UserError(_(
                    'El archivo %s no corresponde a una liquidación XLSX de Claro.'
                ) % name)

    def action_import(self):
        self.ensure_one()
        if self.import_type == 'purchase':
            if not self.purchase_batch_id:
                raise UserError(_('Seleccione un lote de compras.'))
            if self.purchase_batch_id.state == 'closed':
                raise UserError(_('No se puede importar en un lote de compras cerrado.'))
        else:
            if not self.settlement_batch_id:
                raise UserError(_('Seleccione una liquidación.'))
            if self.settlement_batch_id.state == 'closed':
                raise UserError(_('No se puede importar en una liquidación cerrada.'))

        ImportFile = self.env['commission.import.file']
        imported_files = 0
        for attachment in self.file_ids:
            for payload in self._iter_attachment_payloads(attachment):
                self._validate_payload_type(payload)
                data = payload['data']
                sha256 = hashlib.sha256(data).hexdigest()
                existing = ImportFile.search([('sha256', '=', sha256)], limit=1)
                if existing:
                    raise UserError(_(
                        'El archivo %s ya fue importado anteriormente como %s.'
                    ) % (payload['display_name'], existing.name))

                try:
                    with self.env.cr.savepoint():
                        # El hash corto hace único el identificador de fila incluso si dos
                        # archivos distintos llegan con el mismo nombre visible.
                        logical_source = '%s [%s]' % (payload['source_name'], sha256[:12])
                        if self.import_type == 'purchase':
                            count = self._import_purchase(logical_source, data)
                        else:
                            count = self._import_settlement(logical_source, data)

                        # Compatibilidad de esquema: la trazabilidad ZIP se conserva en
                        # el campo name, que existe desde la primera versión del módulo. Esto
                        # evita depender de columnas añadidas posteriormente (archive_member,
                        # archive_name, byte_size) en bases que quedaron con un esquema previo.
                        source_display_name = payload['display_name']
                        if payload['archive_name'] and payload['archive_member']:
                            source_display_name = '%s :: %s' % (
                                payload['archive_name'], payload['archive_member']
                            )
                        import_file = ImportFile.create({
                            'name': source_display_name,
                            'sha256': sha256,
                            'attachment_id': attachment.id,
                            'purchase_batch_id': self.purchase_batch_id.id if self.import_type == 'purchase' else False,
                            'settlement_batch_id': self.settlement_batch_id.id if self.import_type == 'settlement' else False,
                            'row_count': count,
                        })
                        # El many2many_binary crea adjuntos ligados al wizard transitorio.
                        # Reasignamos el contenedor original al lote para que no dependa de la
                        # limpieza periódica de TransientModel y siga disponible para auditoría.
                        target_batch = self.purchase_batch_id if self.import_type == 'purchase' else self.settlement_batch_id
                        if attachment.res_model == self._name and attachment.res_id == self.id:
                            attachment.write({
                                'res_model': target_batch._name,
                                'res_id': target_batch.id,
                                'res_field': False,
                            })
                        # Mantener una referencia explícita en el registro fuente.
                        if import_file.attachment_id != attachment:
                            import_file.attachment_id = attachment.id
                        imported_files += 1
                except UserError:
                    raise
                except MemoryError as exc:
                    _logger.exception('Memoria insuficiente importando %s', payload['source_name'])
                    raise UserError(_(
                        'Memoria insuficiente al procesar %s. Para Compras, comprima el .XLS/.DBF en ZIP y vuelva a intentar.'
                    ) % payload['display_name']) from exc
                except Exception as exc:
                    _logger.exception('Error importando %s', payload['source_name'])
                    raise UserError(_(
                        'No se pudo importar %s. Detalle técnico: %s'
                    ) % (payload['display_name'], str(exc))) from exc

        if not imported_files:
            raise UserError(_('No se encontró ningún archivo válido para importar.'))
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def _warehouse_mapping(self, code, name):
        Mapping = self.env['commission.warehouse.mapping']
        code = str(code or '').strip()
        name = str(name or '').strip()
        if not code and not name:
            return Mapping.browse()
        # El código de bodega es más estable que el nombre: se prioriza para evitar
        # resultados ambiguos cuando existen nombres similares.
        if code:
            mapping = Mapping.search([
                ('active', '=', True), ('warehouse_code', '=ilike', code)
            ], order='id', limit=1)
            if mapping:
                return mapping
        if name:
            return Mapping.search([
                ('active', '=', True), ('warehouse_name', '=ilike', name)
            ], order='id', limit=1)
        return Mapping.browse()

    def _import_purchase(self, name, data):
        batch = self.purchase_batch_id
        operator = batch.operator_id
        key_length = operator.icc_match_length or 18
        Sim = self.env['commission.sim']
        Line = self.env['commission.purchase.line']
        SettlementLine = self.env['commission.settlement.line']
        count = 0
        buffer = []
        mapping_cache = {}
        affected_sim_ids = set()

        def get_mapping(code, warehouse_name):
            key = (normalize_text(code), normalize_text(warehouse_name))
            if key not in mapping_cache:
                mapping_cache[key] = self._warehouse_mapping(code, warehouse_name)
            return mapping_cache[key]

        def flush(rows):
            nonlocal count
            if not rows:
                return
            keys = list({vals['icc_key'] for vals in rows if vals['icc_key']})
            existing = {
                sim.icc_key: sim
                for sim in Sim.search([
                    ('operator_id', '=', operator.id),
                    ('icc_key', 'in', keys),
                ])
            }
            new_values = []
            seen_new = set()
            for vals in rows:
                key = vals['icc_key']
                if not key:
                    continue
                if key not in existing and key not in seen_new:
                    seen_new.add(key)
                    mapping = get_mapping(vals['warehouse_code'], vals['warehouse_name'])
                    new_values.append({
                        'icc': vals['icc'],
                        'icc_key': key,
                        'operator_id': operator.id,
                        'purchase_date': vals['date'],
                        'invoice': vals['invoice'],
                        'warehouse': vals['warehouse_name'],
                        'product': vals['product_name'],
                        'purchase_cost': operator._roi_cost_value(
                            vals['cost'], vals['discount'], vals['tax']
                        ),
                        'region_id': mapping.region_id.id if mapping else False,
                        'zone_id': mapping.zone_id.id if mapping else False,
                    })
            if new_values:
                for sim in Sim.create(new_values):
                    existing[sim.icc_key] = sim

            line_values = []
            for vals in rows:
                sim = existing.get(vals['icc_key'])
                if not sim:
                    continue
                mapping = get_mapping(vals['warehouse_code'], vals['warehouse_name'])
                vals.update({
                    'sim_id': sim.id,
                    'region_id': mapping.region_id.id if mapping else sim.region_id.id,
                    'zone_id': mapping.zone_id.id if mapping else sim.zone_id.id,
                })
                line_values.append(vals)
                affected_sim_ids.add(sim.id)
            if line_values:
                Line.create(line_values)
                count += len(line_values)

        for row_number, row in dbf_rows(data):
            icc = str(row.get('CHIP') or '').strip()
            key = make_icc_key(icc, key_length)
            if not icc or not key:
                continue
            buffer.append({
                'icc': icc,
                'icc_key': key,
                'date': row.get('FECHA'),
                'document_type': str(row.get('TIPO') or '').strip(),
                'number': str(row.get('NUMERO') or '').strip(),
                'supplier_code': str(row.get('PROVEEDOR') or '').strip(),
                'supplier_name': str(row.get('NPROVEEDOR') or '').strip(),
                'invoice': str(row.get('FACTURA') or '').strip(),
                'warehouse_code': str(row.get('BODEGA') or '').strip(),
                'warehouse_name': str(row.get('NBODEGA') or '').strip(),
                'product_code': str(row.get('PRODUCTO') or '').strip(),
                'product_name': str(row.get('NPRODUCTO') or '').strip(),
                'quantity': row.get('CANTIDAD') if row.get('CANTIDAD') not in (None, '') else 1,
                'cost': row.get('COSTO') or 0,
                'discount': row.get('DESCUENTO') or 0,
                'tax': row.get('IMPUESTO') or 0,
                'source_file': name,
                'source_row': row_number,
                'batch_id': batch.id,
            })
            if len(buffer) >= CHUNK:
                flush(buffer)
                buffer = []
        flush(buffer)

        sim_ids = list(affected_sim_ids)
        for start in range(0, len(sim_ids), 10000):
            chunk = sim_ids[start:start + 10000]
            batch._refresh_purchase_master_for_sims(chunk)
            batch._recalculate_roi_cost_for_sims(chunk)

            # Si las liquidaciones se cargaron antes que las compras, vincular ahora los ICC
            # recién incorporados y recalcular solamente esas líneas.
            matched_line_ids, matched_sim_ids = SettlementLine._match_sims_bulk(
                operator_id=operator.id, sim_ids=chunk
            )
            for line_start in range(0, len(matched_line_ids), 5000):
                SettlementLine.browse(
                    matched_line_ids[line_start:line_start + 5000]
                )._recalculate_expected_bulk()
            Sim._refresh_kpis(list(set(chunk) | set(matched_sim_ids)))
        batch.state = 'processed'
        return count

    @staticmethod
    def _build_header_map(top, second):
        # Claro uses two header rows: descriptive columns in row 2 and Measures in row 1.
        size = max(len(top), len(second))
        headers = []
        for idx in range(size):
            second_value = second[idx] if idx < len(second) else None
            top_value = top[idx] if idx < len(top) else None
            headers.append(second_value or top_value)
        return {normalize_text(value): idx for idx, value in enumerate(headers) if value not in (None, '')}

    def _import_settlement(self, name, data):
        try:
            from openpyxl import load_workbook
        except ImportError as exc:
            raise UserError(_('Se requiere la librería Python openpyxl.')) from exc

        batch = self.settlement_batch_id
        operator = batch.operator_id
        key_length = operator.icc_match_length or 18
        workbook = None
        try:
            workbook = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
            worksheet = workbook.active
            header_rows = list(worksheet.iter_rows(min_row=1, max_row=2, values_only=True))
            if len(header_rows) < 2:
                raise UserError(_('El archivo %s no contiene las dos filas de encabezado esperadas.') % name)
            top = list(header_rows[0])
            second = list(header_rows[1])
            header_map = self._build_header_map(top, second)
        except UserError:
            if workbook:
                workbook.close()
            raise
        except Exception as exc:
            if workbook:
                workbook.close()
            raise UserError(_('No se pudo leer %s como XLSX: %s') % (name, exc)) from exc

        aliases = {
            'compensation_date': ['compensation date'],
            'region': ['region', 'región'],
            'customer': ['cliente'],
            'product': ['producto'],
            'concept': ['concepto'],
            'service_number': ['numero servicio', 'número servicio'],
            'activation_date': ['fecha activacion', 'fecha activación'],
            'regularization_date': ['fecha regularizacion', 'fecha regularización'],
            'high_date': ['fecha alta'],
            'distributor_type': ['tipo distribuidor'],
            'invoice': ['no. factura', 'no factura'],
            'simcard': ['simcard'],
            'pvp': ['pvp'],
            'percentage': ['porcentaje'],
            'recharges': ['recargas'],
            'consumptions': ['consumos'],
            'base_tariff': ['tarifa basica', 'tarifa básica'],
            'evaluated_consumption': ['consumo evaluado'],
            'value': ['valor'],
            'discounted_base_tariff': ['tarifa basica descontada', 'tarifa básica descontada'],
            'advance_value': ['valor anticipo'],
        }

        indexes = {}
        for logical, names in aliases.items():
            found = None
            for alias in names:
                key = normalize_text(alias)
                if key in header_map:
                    found = header_map[key]
                    break
            indexes[logical] = found

        required = ['compensation_date', 'region', 'concept', 'simcard', 'percentage', 'evaluated_consumption', 'value']
        missing = [field for field in required if indexes.get(field) is None]
        if missing:
            if workbook:
                workbook.close()
            raise UserError(_(
                'Faltan columnas requeridas en %s: %s'
            ) % (name, ', '.join(missing)))

        Line = self.env['commission.settlement.line']
        Sim = self.env['commission.sim']
        Region = self.env['commission.region']
        count = 0
        buffer = []
        region_cache = {}
        affected_sim_ids = set()
        rules = Line._rules_for_operator(operator.id)

        def get(row, logical):
            idx = indexes.get(logical)
            return row[idx] if idx is not None and idx < len(row) else None

        def get_region(region_name):
            key = str(region_name or '').strip()
            if not key:
                return Region.browse()
            cache_key = normalize_text(key)
            if cache_key not in region_cache:
                region_cache[cache_key] = (
                    Region.search([('name', '=ilike', key)], limit=1)
                    or Region.create({'name': key})
                )
            return region_cache[cache_key]

        def flush(rows):
            nonlocal count
            if not rows:
                return
            keys = list({vals['icc_key'] for vals in rows if vals['icc_key']})
            sims = {
                sim.icc_key: sim
                for sim in Sim.search([
                    ('operator_id', '=', operator.id),
                    ('icc_key', 'in', keys),
                ])
            }
            fallback_region_updates = {}
            for vals in rows:
                sim = sims.get(vals['icc_key'])
                if sim:
                    vals['sim_id'] = sim.id
                    affected_sim_ids.add(sim.id)
                    # Telecity's analytical region/zone from purchase mapping has priority.
                    source_region_id = vals.get('region_id')
                    vals['region_id'] = sim.region_id.id or source_region_id
                    vals['zone_id'] = sim.zone_id.id
                    # If the purchase master has no region yet, use Claro's source Region as a
                    # fallback. A later Bodega -> Región/Zona mapping is allowed to overwrite it.
                    if not sim.region_id and source_region_id:
                        fallback_region_updates.setdefault(source_region_id, []).append(sim.id)
                vals.update(Line._expected_values_from_dict(vals, operator.id, rules=rules))
            Line.create(rows)
            for region_id, sim_ids in fallback_region_updates.items():
                self.env.cr.execute(
                    "UPDATE commission_sim SET region_id=%s WHERE id = ANY(%s) AND region_id IS NULL",
                    (region_id, list(set(sim_ids))),
                )
            if fallback_region_updates:
                Sim.invalidate_model(['region_id'])
            count += len(rows)

        try:
            for row_number, row in enumerate(worksheet.iter_rows(min_row=3, values_only=True), 3):
                icc = str(get(row, 'simcard') or '').strip()
                key = make_icc_key(icc, key_length)
                if not icc or not key:
                    continue
                source_percentage, normalized_percentage = normalize_percentage(get(row, 'percentage'))
                source_region = get(row, 'region')
                region = get_region(source_region)
                buffer.append({
                    'batch_id': batch.id,
                    'icc': icc,
                    'icc_key': key,
                    'compensation_date': parse_date(get(row, 'compensation_date')),
                    'region_text': source_region,
                    'region_id': region.id if region else False,
                    'customer': get(row, 'customer'),
                    'product': get(row, 'product'),
                    'concept': get(row, 'concept'),
                    'service_number': get(row, 'service_number'),
                    'activation_date': parse_date(get(row, 'activation_date')),
                    'regularization_date': parse_date(get(row, 'regularization_date')),
                    'high_date': parse_date(get(row, 'high_date')),
                    'distributor_type': get(row, 'distributor_type'),
                    'invoice': get(row, 'invoice'),
                    'pvp': get(row, 'pvp') or 0,
                    'reported_percentage_source': source_percentage,
                    'reported_percentage': normalized_percentage,
                    'recharges': get(row, 'recharges') or 0,
                    'consumptions': get(row, 'consumptions') or 0,
                    'base_tariff': get(row, 'base_tariff') or 0,
                    'evaluated_consumption': get(row, 'evaluated_consumption') or 0,
                    'reported_value': get(row, 'value') or 0,
                    'discounted_base_tariff': get(row, 'discounted_base_tariff') or 0,
                    'advance_value': get(row, 'advance_value') or 0,
                    'source_file': name,
                    'source_row': row_number,
                })
                if len(buffer) >= CHUNK:
                    flush(buffer)
                    buffer = []
            flush(buffer)
        finally:
            if workbook:
                workbook.close()

        sim_ids = list(affected_sim_ids)
        for start in range(0, len(sim_ids), 10000):
            Sim._refresh_kpis(sim_ids[start:start + 10000])
        batch.state = 'processed'
        return count
