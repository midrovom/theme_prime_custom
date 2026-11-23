import base64
from collections import defaultdict
from hashlib import sha256
import html
import math
import re
import unicodedata

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from .xlsx_reader import read_first_sheet


HEADERS = {
    'sku': {'sku', 'codigo sku', 'codigo erp', 'codigo_erp', 'referencia interna', 'default_code', 'internal reference'},
    'discount': {'descuento', 'descuento %', 'descuento_pct', 'discount', 'discount_percent', 'porcentaje descuento', 'porcentaje de descuento'},
    'fixed': {'precio', 'precio fijo', 'precio_fijo', 'fixed_price', 'precio venta'},
    'minimum_qty': {'cantidad minima', 'cantidad_minima', 'min_quantity', 'minimo'},
}


def _norm(text):
    return ' '.join(''.join(ch for ch in unicodedata.normalize('NFKD', str(text or ''))
                           if not unicodedata.combining(ch)).lower().replace('_', ' ').split())


def _number(value, row_num, label, required=False):
    value = str(value or '').strip().replace('%', '')
    if not value:
        if required:
            raise ValueError('Fila %s: falta %s.' % (row_num, label))
        return None
    if ',' in value and '.' in value:
        raise ValueError('Fila %s: formato ambiguo en %s (use decimal con punto).' % (row_num, label))
    try:
        result = float(value.replace(',', '.'))
    except ValueError as exc:
        raise ValueError('Fila %s: %s debe ser numérico.' % (row_num, label)) from exc
    if not math.isfinite(result):
        raise ValueError('Fila %s: %s no es un número finito.' % (row_num, label))
    return result


def _parse_rows(matrix, kind):
    header = [_norm(s) for s in matrix[0]]
    indexes = {}
    for column, aliases in HEADERS.items():
        found = [i for i, label in enumerate(header) if label in {_norm(a) for a in aliases}]
        if len(found) > 1:
            raise ValueError('Hay dos columnas para %s; use una sola.' % column)
        if found:
            indexes[column] = found[0]
    if 'sku' not in indexes:
        raise ValueError('Falta columna SKU / Referencia interna.')
    if kind in ('reward', 'policy') and 'discount' not in indexes:
        raise ValueError('Falta columna descuento_pct. Use 15 para 15 %, no 0.15.')
    if kind == 'pricelist' and not any(c in indexes for c in ('fixed', 'discount')):
        raise ValueError('Incluya precio_fijo o descuento_pct para cada SKU.')
    result = []
    seen = {}
    for rowno, values in enumerate(matrix[1:], 2):
        def cell(column):
            i = indexes.get(column)
            return values[i] if i is not None and i < len(values) else ''
        if not any(str(v).strip() for v in values):
            continue
        sku = str(cell('sku')).strip()
        if not sku:
            raise ValueError('Fila %s: SKU vacío.' % rowno)
        if sku in seen:
            raise ValueError('SKU %s repetido en filas %s y %s.' % (sku, seen[sku], rowno))
        seen[sku] = rowno
        disc = _number(cell('discount'), rowno, 'descuento_pct')
        price = _number(cell('fixed'), rowno, 'precio_fijo')
        minqty = _number(cell('minimum_qty'), rowno, 'cantidad_minima')
        if disc is not None and not 0 <= disc <= 100:
            raise ValueError('Fila %s: el descuento debe estar entre 0 y 100.' % rowno)
        if kind in ('reward', 'policy') and (disc is None or disc <= 0):
            raise ValueError('Fila %s: la recompensa requiere descuento mayor que cero.' % rowno)
        if kind == 'pricelist':
            if (disc is None) == (price is None):
                raise ValueError('Fila %s: ingrese solo precio_fijo o descuento_pct.' % rowno)
            if price is not None and price < 0:
                raise ValueError('Fila %s: el precio no puede ser negativo.' % rowno)
        if minqty is not None and minqty < 0:
            raise ValueError('Fila %s: cantidad mínima inválida.' % rowno)
        result.append({'row': rowno, 'sku': sku, 'discount': disc,
                       'fixed': price, 'minimum_qty': minqty or 0})
    if not result:
        raise ValueError('El Excel no contiene productos debajo de las cabeceras.')
    return result


class CatastroERPExcelImportWizard(models.TransientModel):
    _name = 'catastro.erp.excel.import.wizard'
    _description = 'Importador Excel SKU ERP (Loyalty y listas de precios)'

    import_kind = fields.Selection([
        ('policy', 'Política completa: SKU y porcentaje'),
        ('rule', 'SKU para regla Loyalty'),
        ('reward', 'SKU y descuento para recompensa Loyalty'),
        ('pricelist', 'SKU y precio para lista de precios'),
    ], required=True, default='policy')
    company_id = fields.Many2one('res.company', required=True,
                                  default=lambda self: self.env.company)
    program_id = fields.Many2one('loyalty.program', string='Programa Loyalty existente')
    rule_id = fields.Many2one('loyalty.rule', string='Regla a actualizar')
    reward_id = fields.Many2one('loyalty.reward', string='Recompensa a actualizar')
    campaign_name = fields.Char(string='Nombre de política ERP')
    campaign_key = fields.Char(string='Código de política ERP',
                               help='Identificador estable para actualizar la misma política en futuras importaciones.')
    pricelist_id = fields.Many2one('product.pricelist', string='Lista de precios existente')
    new_pricelist = fields.Boolean(string='Crear lista de precios nueva')
    pricelist_name = fields.Char(string='Nombre de la lista nueva')
    currency_id = fields.Many2one('res.currency', string='Moneda',
                                  default=lambda self: self.env.company.currency_id)
    restrict_users = fields.Boolean(string='Solo usuarios autorizados')
    allowed_user_ids = fields.Many2many('res.users', string='Usuarios autorizados',
                                       domain=[('share', '=', False)])
    update_mode = fields.Selection([
        ('append', 'Añadir/actualizar sin quitar productos anteriores'),
        ('replace', 'Reemplazar productos gestionados desde Excel'),
    ], required=True, default='append')
    file_data = fields.Binary(string='Archivo Excel (.xlsx)', required=True, attachment=False)
    filename = fields.Char(string='Nombre del archivo')
    preview_html = fields.Html(string='Resultado de validación', readonly=True, sanitize=True)
    preview_hash = fields.Char(readonly=True)
    preview_ok = fields.Boolean(readonly=True)
    imported_summary = fields.Text(readonly=True)

    @api.onchange('program_id')
    def _onchange_program(self):
        if self.program_id:
            self.company_id = self.program_id.company_id or self.env.company

    @api.onchange('pricelist_id')
    def _onchange_pricelist(self):
        if self.pricelist_id:
            self.company_id = self.pricelist_id.company_id or self.env.company
            self.currency_id = self.pricelist_id.currency_id
            self.restrict_users = self.pricelist_id.catastro_access_restricted
            self.allowed_user_ids = self.pricelist_id.catastro_allowed_user_ids

    def _check_manager(self):
        if not (self.env.user.has_group('sales_team.group_sale_manager')
                or self.env.user.has_group('base.group_system')):
            raise AccessError('Solo Gerentes de Ventas o administradores pueden importar políticas ERP.')

    def _get_payload(self):
        self.ensure_one()
        self._check_manager()
        if self.company_id not in self.env.user.company_ids:
            raise AccessError('La empresa no está autorizada para este usuario.')
        if not self.filename or not self.filename.lower().endswith('.xlsx'):
            raise ValidationError('Seleccione un archivo .xlsx (Excel moderno).')
        try:
            payload = base64.b64decode(self.file_data, validate=True)
        except (ValueError, TypeError) as exc:
            raise ValidationError('No se pudo leer el archivo Excel.') from exc
        return payload

    def _load_rows(self):
        payload = self._get_payload()
        try:
            rows = _parse_rows(read_first_sheet(payload), self.import_kind)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        return rows, payload

    def _resolve_skus(self, rows):
        codes = [r['sku'] for r in rows]
        products = self.env['product.product'].with_company(self.company_id).search([
            ('default_code', 'in', codes), ('active', '=', True), ('sale_ok', '=', True),
            ('company_id', 'in', [False, self.company_id.id]),
        ])
        by_sku = defaultdict(list)
        for product in products:
            by_sku[product.default_code].append(product)
        mistakes = []
        for row in rows:
            matches = by_sku.get(row['sku'], [])
            if len(matches) == 0:
                mistakes.append('Fila %s: SKU %s inexistente, inactivo o no vendible.' % (row['row'], row['sku']))
            elif len(matches) > 1:
                mistakes.append('Fila %s: SKU %s ambiguo (%s productos).' % (row['row'], row['sku'], len(matches)))
            else:
                row['product'] = matches[0]
        if mistakes:
            raise ValidationError('No se importó ningún producto.\n' + '\n'.join(mistakes[:60]) +
                                  ('\n… y más errores.' if len(mistakes) > 60 else ''))
        return rows

    def _check_context(self, rows):
        if self.import_kind in ('rule', 'reward'):
            if not self.program_id:
                raise ValidationError('Seleccione un programa Loyalty existente.')
            if self.program_id.company_id and self.program_id.company_id != self.company_id:
                raise ValidationError('El programa pertenece a otra empresa.')
            if self.rule_id and self.rule_id.program_id != self.program_id:
                raise ValidationError('La regla seleccionada pertenece a otro programa.')
            if self.reward_id and self.reward_id.program_id != self.program_id:
                raise ValidationError('La recompensa seleccionada pertenece a otro programa.')
            if self.import_kind == 'reward':
                rates = {r['discount'] for r in rows}
                if len(rates) != 1:
                    raise ValidationError('Una recompensa nativa solo tiene un porcentaje. '
                                          'Use «Política completa» para SKU con porcentajes diferentes.')
        elif self.import_kind == 'policy':
            if not self.campaign_name or not self.campaign_key:
                raise ValidationError('Indique nombre y código estable de la política ERP.')
            if not re.fullmatch(r'[A-Za-z0-9_.-]{1,64}', self.campaign_key.strip()):
                raise ValidationError('El código de política admite 1-64 letras, números, guiones, punto o _.')
            if self.program_id and self.program_id.company_id and self.program_id.company_id != self.company_id:
                raise ValidationError('La política seleccionada pertenece a otra empresa.')
        elif self.import_kind == 'pricelist':
            if self.new_pricelist:
                if not self.pricelist_name or not self.currency_id:
                    raise ValidationError('Indique nombre y moneda para crear la lista de precios.')
            elif not self.pricelist_id:
                raise ValidationError('Elija una lista existente o marque Crear lista nueva.')
            if self.pricelist_id and not self.new_pricelist:
                if self.pricelist_id.company_id and self.pricelist_id.company_id != self.company_id:
                    raise ValidationError('La lista de precios pertenece a otra compañía.')
            if self.restrict_users and not self.allowed_user_ids:
                raise ValidationError('Seleccione al menos un usuario autorizado para la lista restringida.')
            if self.allowed_user_ids and any(self.company_id not in user.company_ids for user in self.allowed_user_ids):
                raise ValidationError('Los usuarios autorizados deben tener acceso a la empresa de la lista.')
        return rows

    def _validated(self):
        rows, payload = self._load_rows()
        self._check_context(rows)
        rows = self._resolve_skus(rows)
        if self.import_kind == 'pricelist' and self.pricelist_id and not self.new_pricelist:
            items = self.env['product.pricelist.item'].search([
                ('pricelist_id', '=', self.pricelist_id.id),
                ('applied_on', '=', '0_product_variant'),
                ('product_id', 'in', [r['product'].id for r in rows]),
            ])
            wanted = {(r['product'].id, round(r['minimum_qty'], 6)): r['sku'] for r in rows}
            hits = defaultdict(list)
            for item in items:
                key = (item.product_id.id, round(item.min_quantity, 6))
                if key in wanted:
                    hits[key].append(item)
            for key, found in hits.items():
                if len(found) > 1 or any(not it.catastro_excel_managed for it in found):
                    raise ValidationError('SKU %s: ya existe una regla manual o duplicada. '
                                          'No se sobrescribirá.' % wanted[key])
        if self.import_kind == 'policy':
            prefix = '%s:%s:' % (self.company_id.id, self.campaign_key.strip())
            existing = self.env['loyalty.program'].with_context(active_test=False).search([
                ('company_id', '=', self.company_id.id), ('catastro_erp_batch_key', '!=', False)
            ]).filtered(lambda p: (p.catastro_erp_batch_key or '').startswith(prefix))
            for program in existing:
                if len(program.rule_ids) != 1 or len(program.reward_ids) != 1:
                    raise ValidationError('El programa ERP %s fue modificado manualmente. Revíselo.' % program.name)
        return rows, payload

    def _reopen(self):
        return {'type': 'ir.actions.act_window', 'res_model': self._name,
                'res_id': self.id, 'view_mode': 'form', 'target': 'new'}

    def _preview_signature(self, payload):
        controls = (self.import_kind, self.company_id.id, self.program_id.id,
                    self.rule_id.id, self.reward_id.id, self.campaign_name,
                    self.campaign_key, self.pricelist_id.id, self.new_pricelist,
                    self.pricelist_name, self.currency_id.id, self.restrict_users,
                    tuple(sorted(self.allowed_user_ids.ids)), self.update_mode)
        return sha256(payload + repr(controls).encode('utf-8')).hexdigest()

    def action_preview(self):
        self.ensure_one()
        rows, payload = self._validated()
        preview_lines = []
        for r in rows[:20]:
            info = ('%s %%' % r['discount'] if r['discount'] is not None else
                    ('Precio: %s' % r['fixed'] if r['fixed'] is not None else 'SKU asociado'))
            preview_lines.append('<tr><td>%s</td><td>%s</td><td>%s</td></tr>' %
                                 (html.escape(r['sku']), html.escape(r['product'].display_name), html.escape(info)))
        rates = len({r['discount'] for r in rows if r['discount'] is not None})
        self.write({
            'preview_hash': self._preview_signature(payload), 'preview_ok': True,
            'preview_html': '<p><strong>Válido: %d SKU, %d porcentajes diferentes.</strong> '
                            'Muestra de las primeras 20 filas. Ningún dato ha cambiado aún.</p>'
                            '<table class="table table-sm"><thead><tr><th>SKU</th><th>Producto</th><th>Valor</th></tr></thead>'
                            '<tbody>%s</tbody></table>' % (len(rows), rates, ''.join(preview_lines)),
        })
        return self._reopen()

    def _upsert_policy(self, rows):
        by_rate = defaultdict(list)
        for row in rows:
            by_rate[row['discount']].append(row['product'])
        Program = self.env['loyalty.program'].with_company(self.company_id)
        prefix = '%s:%s:' % (self.company_id.id, self.campaign_key.strip())
        existing = Program.with_context(active_test=False).search([
            ('company_id', '=', self.company_id.id), ('catastro_erp_batch_key', '!=', False)
        ]).filtered(lambda p: (p.catastro_erp_batch_key or '').startswith(prefix))
        current_keys = set()
        for percent, products in sorted(by_rate.items()):
            key = prefix + ('%.6f' % percent)
            current_keys.add(key)
            program = existing.filtered(lambda p: p.catastro_erp_batch_key == key)
            if len(program) > 1:
                raise ValidationError('Existen programas duplicados para la política %s.' % key)
            prod_ids = list({p.id for p in products})
            rule_vals = {'product_ids': [(6, 0, prod_ids)], 'minimum_qty': 1,
                         'minimum_amount': 0, 'reward_point_amount': 1,
                         'reward_point_mode': 'order'}
            reward_vals = {'reward_type': 'discount', 'discount_mode': 'percent',
                           'discount': percent, 'discount_applicability': 'specific',
                           'discount_product_ids': [(6, 0, prod_ids)], 'required_points': 1,
                           'description': '%s: %s%%' % (self.campaign_name, percent)}
            label = '%s | %s%%' % (self.campaign_name.strip(), percent)
            if program:
                program.write({'name': label, 'active': True})
                if not program.rule_ids or not program.reward_ids:
                    raise ValidationError('La política %s fue alterada manualmente. Revísela antes de importar.' % key)
                program.rule_ids[:1].write(rule_vals)
                program.reward_ids[:1].write(reward_vals)
                if len(program.rule_ids) != 1 or len(program.reward_ids) != 1:
                    raise ValidationError('La política %s tiene reglas o recompensas adicionales: no se sobrescribirá.' % key)
            else:
                created = Program.create({
                    'name': label, 'company_id': self.company_id.id,
                    'currency_id': self.company_id.currency_id.id,
                    'program_type': 'promotion', 'trigger': 'auto', 'applies_on': 'current',
                    'catastro_erp_batch_key': key,
                    'rule_ids': [(0, 0, rule_vals)],
                    'reward_ids': [(0, 0, reward_vals)],
                })
                if len(created.rule_ids) != 1 or len(created.reward_ids) != 1:
                    raise ValidationError('Odoo generó más de una regla/recompensa al crear %s. '
                                          'No se importará parcialmente.' % label)
                created.rule_ids.write(rule_vals)
                created.reward_ids.write(reward_vals)
        if self.update_mode == 'replace':
            (existing.filtered(lambda p: p.catastro_erp_batch_key not in current_keys)).write({'active': False})
        return 'Política %s: %d productos, %d programas por porcentaje.' % (
            self.campaign_name, len(rows), len(by_rate))

    def _import_rule(self, rows):
        rule = self.rule_id or self.program_id.rule_ids[:1]
        if not rule:
            rule = self.env['loyalty.rule'].create({'program_id': self.program_id.id})
        ids = set(row['product'].id for row in rows)
        if self.update_mode == 'append':
            ids.update(rule.product_ids.ids)
        rule.write({'product_ids': [(6, 0, list(ids))]})
        return 'Regla %s: %s SKU importados.' % (rule.id, len(rows))

    def _import_reward(self, rows):
        reward = self.reward_id or self.program_id.reward_ids[:1]
        if not reward:
            reward = self.env['loyalty.reward'].create({'program_id': self.program_id.id})
        if reward.reward_type != 'discount':
            raise ValidationError('La recompensa seleccionada no es de tipo descuento. No se sustituirán productos gratis ni regalos.')
        percent = rows[0]['discount']
        ids = set(row['product'].id for row in rows)
        if self.update_mode == 'append' and reward.discount_applicability == 'specific' and reward.discount == percent:
            ids.update(reward.discount_product_ids.ids)
        reward.write({'reward_type': 'discount', 'discount_mode': 'percent',
                      'discount_applicability': 'specific', 'discount': percent,
                      'discount_product_ids': [(6, 0, list(ids))]})
        return 'Recompensa %s: %d SKU, descuento %s %%.' % (reward.id, len(rows), percent)

    def _import_pricelist(self, rows):
        pl = self.pricelist_id
        if self.new_pricelist:
            # Restrict the list only after creating its items. Otherwise an
            # importing manager not in allowed_user_ids loses access mid-import.
            pl = self.env['product.pricelist'].create({
                'name': self.pricelist_name.strip(), 'company_id': self.company_id.id,
                'currency_id': self.currency_id.id,
                'catastro_access_restricted': False,
            })
        Item = self.env['product.pricelist.item'].with_company(self.company_id)
        existing = Item.search([('pricelist_id', '=', pl.id)])
        # Avoid competing Odoo rules at exactly the same product/quantity scope.
        # Other manual rules (category/global/dates) are intentionally preserved.
        by_key = defaultdict(list)
        for item in existing.filtered(lambda it: it.applied_on == '0_product_variant'):
            by_key[(item.product_id.id, round(item.min_quantity, 6))].append(item)
        imported_keys = set()
        for row in rows:
            product = row['product']
            key = (product.id, round(row['minimum_qty'], 6))
            imported_keys.add(key)
            found = by_key.get(key, [])
            if len(found) > 1 or any(not item.catastro_excel_managed for item in found):
                raise ValidationError('SKU %s ya tiene una regla manual o duplicada en la lista. '
                                      'No se sobrescribirá.' % row['sku'])
            vals = {
                'pricelist_id': pl.id,
                'applied_on': '0_product_variant',
                'product_id': product.id,
                'product_tmpl_id': product.product_tmpl_id.id,
                'min_quantity': row['minimum_qty'],
                'catastro_excel_managed': True,
                'base': 'list_price',
                'compute_price': 'fixed' if row['fixed'] is not None else 'percentage',
                'fixed_price': row['fixed'] if row['fixed'] is not None else 0,
                'percent_price': row['discount'] if row['discount'] is not None else 0,
            }
            if found:
                found[0].write(vals)
            else:
                Item.create(vals)
        if self.update_mode == 'replace':
            stale = existing.filtered(lambda i: i.catastro_excel_managed and i.applied_on == '0_product_variant'
                                        and (i.product_id.id, round(i.min_quantity, 6)) not in imported_keys)
            stale.unlink()
        pl.write({'catastro_allowed_user_ids': [(6, 0, self.allowed_user_ids.ids)],
                  'catastro_access_restricted': self.restrict_users})
        return 'Lista %s: %d reglas SKU importadas. Acceso restringido: %s.' % (
            pl.name, len(rows), 'Sí' if self.restrict_users else 'No')

    def action_import(self):
        self.ensure_one()
        rows, payload = self._validated()
        if not self.preview_ok or self.preview_hash != self._preview_signature(payload):
            raise ValidationError('Valide nuevamente el Excel antes de aplicar cambios.')
        if self.import_kind == 'policy':
            summary = self._upsert_policy(rows)
        elif self.import_kind == 'rule':
            summary = self._import_rule(rows)
        elif self.import_kind == 'reward':
            summary = self._import_reward(rows)
        else:
            summary = self._import_pricelist(rows)
        self.write({'imported_summary': summary, 'preview_ok': False})
        return {'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {'title': _('Importación completada'), 'message': summary,
                           'type': 'success', 'sticky': True}}
