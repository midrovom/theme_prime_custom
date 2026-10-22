# -*- coding: utf-8 -*-
"""PWA selector de guías, compatible con importaciones ERP parcialmente homologadas.

Sin afectar v5.32: solo permite coincidencias verificables de transportista,
chofer y destino. La falta de una relación res.users/res.partner no oculta una
identidad ERP comprobable, ni autoriza reutilizar una guía ajena.
"""
import re
import unicodedata
from urllib.parse import quote

from odoo import http, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.http import request
from odoo.osv import expression
from odoo.addons.logistica_transcash.controllers.operacion import TranscashOperaciones

MAX_SELECTION = 100
PAGE_SIZE = 250
MAX_SCAN = 6000
MAX_DISPLAY = 400


def _identity(value):
    value = re.sub(r'[^A-Z0-9]', '', str(value or '').strip().upper())
    if value.startswith('EC') and value[2:].isdigit():
        value = value[2:]
    return value


def _fiscal_id(value):
    """Solo documentos fiscales identificables, sin tratar códigos ERP como RUC."""
    normalized = _identity(value)
    return normalized if normalized.isdigit() and len(normalized) in (10, 13) else ''


def _legal_name(value):
    text = unicodedata.normalize('NFKD', str(value or '').upper())
    return ''.join(c for c in text if c.isalnum() and not unicodedata.combining(c))


def _dest_name(value):
    text = unicodedata.normalize('NFKD', str(value or '').casefold())
    return ' '.join(''.join(c for c in text if not unicodedata.combining(c)).split())


class TranscashOperacionFiltrada(TranscashOperaciones):
    """Usa únicamente datos operativos y una homologación privada controlada."""

    def _source_map(self, guias, company_id):
        if not guias:
            return {}
        Source = request.env['tc.guide'].sudo()
        records = Source.search([
            ('company_id', '=', company_id),
            ('operational_guide_id', 'in', guias.ids),
        ])
        result, ambiguous = {}, set()
        for record in records:
            key = record.operational_guide_id.id
            if key in result:
                ambiguous.add(key)
            else:
                result[key] = record
        # Guías anteriores: el enlace operacional puede faltar, pero el ID
        # externo único por empresa sigue permitiendo una unión inequívoca.
        missing = guias.filtered(lambda g: g.id not in result and g.id not in ambiguous
                                 and bool(g.external_id_erp))
        if missing:
            codes = list(set(missing.mapped('external_id_erp')))
            found = Source.search([
                ('company_id', '=', company_id), ('external_id', 'in', codes),
            ])
            by_external, duplicate_codes = {}, set()
            for source in found:
                if source.external_id in by_external:
                    duplicate_codes.add(source.external_id)
                else:
                    by_external[source.external_id] = source
            for guide in missing:
                if guide.external_id_erp not in duplicate_codes and guide.external_id_erp in by_external:
                    candidate = by_external[guide.external_id_erp]
                    if not candidate.operational_guide_id or candidate.operational_guide_id.id == guide.id:
                        result[guide.id] = candidate
        return {key: value for key, value in result.items() if key not in ambiguous}

    def _same_driver_identity(self, first, second, guia):
        """Same human, even if Odoo has duplicate users. Never match by name.

        A shared partner ID is authoritative only when its fiscal document does
        not contradict the document already recorded on the guide.
        Distinct partner records require equal nonempty, normalized documents.
        """
        if not first or not second:
            return False
        first_partner, second_partner = first.partner_id, second.partner_id
        guide_doc = _fiscal_id(guia.ruc_chofer)
        first_doc = _fiscal_id(first_partner.vat) or _fiscal_id(first.login)
        second_doc = _fiscal_id(second_partner.vat) or _fiscal_id(second.login)
        if first_partner.id == second_partner.id:
            return bool(not guide_doc or not first_doc or guide_doc == first_doc) and bool(
                not guide_doc or not second_doc or guide_doc == second_doc)
        return bool(first_doc and second_doc and first_doc == second_doc and
                    (not guide_doc or guide_doc == first_doc))

    def _driver_matches(self, ruta, guia, source):
        """Compare user identity, then national ID if two user records exist.

        Merely equal display names never suffice to treat drivers as identical.
        """
        user = ruta.chofer_usuario_id
        if not user:
            return False
        if guia.chofer_usuario_id:
            if (guia.chofer_usuario_id != user and
                    not self._same_driver_identity(guia.chofer_usuario_id, user, guia)):
                return False
            target = {_fiscal_id(v) for v in (user.partner_id.vat, user.login)} - {''}
            guide_docs = {_fiscal_id(v) for v in (
                guia.ruc_chofer,
                guia.chofer_contacto_id.vat if guia.chofer_contacto_id else '',
            )} - {''}
            if len(guide_docs) > 1:
                return False
            if target and guide_docs and not guide_docs.intersection(target):
                return False
            return True

        erp_contact = guia.chofer_contacto_id or (source.driver_partner_id if source else False)
        source_doc = _fiscal_id(source.driver_id.identification) if source and source.driver_id else ''
        guide_doc = _fiscal_id(guia.ruc_chofer)
        contact_doc = _fiscal_id(erp_contact.vat) if erp_contact else ''
        if guide_doc and contact_doc and guide_doc != contact_doc:
            return False
        expected = {_fiscal_id(v) for v in (user.partner_id.vat, user.login)} - {''}
        strong = guide_doc or contact_doc
        if strong and source_doc and source_doc != strong:
            return False
        if strong:
            return strong in expected
        if source_doc:
            return source_doc in expected
        return bool(erp_contact and erp_contact.id == user.partner_id.id)

    def _transport_matches(self, ruta, guia, source):
        """La empresa asignada en la GUÍA OPERATIVA tiene prioridad.

        El selector de rutas trabaja con `transcash.guia.proveedor_id`, no con
        `tc.guide.transport_partner_id`. Este último solo sirve para rescatar
        guías antiguas SIN proveedor_id. Un vínculo ERP desactualizado nunca
        debe ocultar una guía ya homologada en la operación.
        """
        if not ruta.proveedor_id:
            return False
        chosen = ruta.proveedor_id.commercial_partner_id
        if not chosen:
            return False
        linked = guia.proveedor_id.commercial_partner_id if guia.proveedor_id else False
        if linked:
            # Verificación por registro: incluye contactos hijos de la empresa.
            if linked.id == chosen.id:
                return True
            # Resuelve duplicados históricos de res.partner con el mismo RUC.
            linked_vat, chosen_vat = _fiscal_id(linked.vat), _fiscal_id(chosen.vat)
            return bool(linked_vat and chosen_vat and linked_vat == chosen_vat)

        # Solo si la guía NO tiene proveedor operativo, intentar homologación
        # desde la API; jamás sustituir otro proveedor asignado por nombre.
        if not source:
            return False
        src_partner = (source.transport_partner_id.commercial_partner_id
                       if source.transport_partner_id else False)
        if src_partner:
            if src_partner.id == chosen.id:
                return True
            src_vat, chosen_vat = _fiscal_id(src_partner.vat), _fiscal_id(chosen.vat)
            if src_vat and chosen_vat:
                return src_vat == chosen_vat
            # Si existe un contacto fuente no homologado, seguir únicamente
            # con un RUC explícito o solicitar conciliación administrativa.
            return False

        src_tax = _fiscal_id(source.transport_tax_raw)
        if src_tax:
            return bool(_fiscal_id(chosen.vat) == src_tax)

        # Sin identificación fiscal, únicamente nombre LEGAL exacto, único,
        # sin RUC contradictorios. Nunca seleccionar por coincidencia parcial.
        name = _legal_name(source.transport_name)
        if not name or name != _legal_name(chosen.name):
            return False
        words = re.findall(r'[A-Za-zÀ-ÿ0-9]{4,}', source.transport_name or '')
        anchor = max(words, key=len) if words else source.transport_name
        Partner = request.env['res.partner'].sudo().with_context(active_test=False)
        domain = [
            ('is_company', '=', True), ('name', 'ilike', anchor),
            '|', ('company_id', '=', False), ('company_id', '=', ruta.company_id.id),
        ]
        if Partner.search_count(domain) > 500:
            return False
        partners = Partner.search(domain, limit=500)
        matching = partners.filtered(lambda p: _legal_name(p.name) == name)
        taxes = {_fiscal_id(p.vat) for p in matching if _fiscal_id(p.vat)}
        return bool(chosen in matching and len(taxes) <= 1 and
                    (not taxes or not chosen.vat or _fiscal_id(chosen.vat) in taxes))

    def _same_destination_code(self, first, second):
        """ERP codes '-NAJ' and 'NAJ' denote the same controlled code.

        An empty code or a matching display name is not sufficient. This does
        not rewrite the destination catalogue, used by historical routes.
        """
        if not first or not second or first.company_id != second.company_id:
            return False
        left, right = _identity(first.codigo), _identity(second.codigo)
        return bool(left and right and left == right)

    def _destination_matches(self, ruta, guia, source):
        master = ruta.destino_id
        if not master:
            return False
        if guia.destino_id:
            return (guia.destino_id.id == master.id or
                    self._same_destination_code(guia.destino_id, master))
        if ruta._coincide_destino(guia):
            return True
        erp_code = (_identity(source.destination_id.external_code)
                    if source and source.destination_id else '')
        route_code = _identity(master.codigo)
        if erp_code and route_code:
            return erp_code == route_code
        guide_code = _identity(guia.destino_codigo)
        if guide_code and route_code:
            return guide_code == route_code
        if not source:
            return False
        valid = {_dest_name(master.name), _dest_name(master.ciudad)} - {''}
        stated = {_dest_name(source.destination_city), _dest_name(source.destination_address)} - {''}
        return bool(valid.intersection(stated))

    def _match(self, ruta, guia, source):
        """Devuelve (válida, motivo), evaluando cada dimensión por separado."""
        if (not ruta.company_id or not ruta.destino_id or not ruta.chofer_usuario_id or
                not ruta.proveedor_id or guia.company_id != ruta.company_id or
                guia.state != 'registrada' or guia.embarque_id or guia.hoja_ruta_id):
            return False, 'estado'
        if not self._destination_matches(ruta, guia, source):
            return False, 'destino'
        if not self._driver_matches(ruta, guia, source):
            return False, 'chofer'
        if not self._transport_matches(ruta, guia, source):
            return False, 'transporte'
        return True, 'compatible'

    def _guide_diagnostic(self, ruta, guia, source):
        """Factual reason a specific guide does not appear in the PWA."""
        dest_ok = self._destination_matches(ruta, guia, source)
        driver_ok = self._driver_matches(ruta, guia, source)
        provider_ok = self._transport_matches(ruta, guia, source)
        matched, reason = self._match(ruta, guia, source)
        reasons = []
        if guia.company_id != ruta.company_id:
            reasons.append('Otra empresa')
        if guia.state != 'registrada':
            reasons.append('Estado ' + str(guia.state))
        if guia.hoja_ruta_id:
            reasons.append('Asignada a ' + (guia.hoja_ruta_id.name or 'otra ruta'))
        if guia.embarque_id:
            reasons.append('Asignada a un embarque')
        if not dest_ok:
            reasons.append('Destino no equivalente')
        if not driver_ok:
            reasons.append('Cédula o usuario del chofer diferente')
        if not provider_ok:
            reasons.append('Proveedor distinto o RUC sin homologar')
        return {
            'guia': guia.name,
            'documento': guia.numero_documento or '',
            'erp': guia.external_id_erp or '',
            'compatible': matched,
            'motivo': '; '.join(reasons) if reasons else 'Compatible',
            'guia_destino': '%s (#%s, %s)' % (
                guia.destino_id.name or guia.destino or 'Sin destino',
                guia.destino_id.id if guia.destino_id else '-',
                guia.destino_id.codigo if guia.destino_id else guia.destino_codigo or '-'),
            'ruta_destino': '%s (#%s, %s)' % (
                ruta.destino_id.name, ruta.destino_id.id, ruta.destino_id.codigo),
            'guia_chofer': '%s (#%s)' % (
                guia.chofer_usuario_id.name if guia.chofer_usuario_id else
                guia.chofer_contacto_id.name if guia.chofer_contacto_id else 'Sin usuario',
                guia.chofer_usuario_id.id if guia.chofer_usuario_id else '-'),
            'ruta_chofer': '%s (#%s)' % (ruta.chofer_usuario_id.name,
                                            ruta.chofer_usuario_id.id),
            'cedula_guia': _fiscal_id(guia.ruc_chofer) or '(vacía)',
            'cedula_contacto': (_fiscal_id(guia.chofer_contacto_id.vat)
                                if guia.chofer_contacto_id else '') or '(vacía)',
            'cedula_ruta': (_fiscal_id(ruta.chofer_usuario_id.partner_id.vat) or
                            _fiscal_id(ruta.chofer_usuario_id.login) or '(vacía)'),
            'guia_proveedor': '%s (#%s)' % (
                guia.proveedor_id.name if guia.proveedor_id else 'Sin proveedor',
                guia.proveedor_id.id if guia.proveedor_id else '-'),
            'ruta_proveedor': '%s (#%s)' % (ruta.proveedor_id.name,
                                               ruta.proveedor_id.id),
            'ruc_guia': (_fiscal_id(guia.proveedor_id.commercial_partner_id.vat)
                         if guia.proveedor_id else '') or '(vacío)',
            'ruc_ruta': _fiscal_id(ruta.proveedor_id.commercial_partner_id.vat) or '(vacío)',
        }

    def _diagnostic_for_search(self, ruta, search):
        """Diagnose an exact/partial guide ID, including state/routing blockers."""
        if not search or len(search) < 3:
            return []
        Guide = request.env['transcash.guia']
        guides = Guide.search([
            ('company_id', '=', ruta.company_id.id),
            '|', '|', ('name', 'ilike', search),
            ('numero_documento', 'ilike', search),
            ('external_id_erp', 'ilike', search),
        ], limit=8, order='id desc')
        sources = self._source_map(guides, ruta.company_id.id)
        return [self._guide_diagnostic(ruta, g, sources.get(g.id)) for g in guides]

    def _candidates_and_report(self, ruta, search):
        Guia = request.env['transcash.guia']
        # NO filtrar por chofer_usuario_id ni proveedor_id en SQL: durante la
        # importación pueden venir sin enlazar, pero con identidad ERP verificable.
        # El servidor valida ambos antes de mostrar/guardar.
        base = ruta._domain_guias_elegibles(validar_filtros=False)
        if search:
            base = expression.AND([base, [
                '|', '|', ('name', 'ilike', search), ('numero_documento', 'ilike', search),
                ('external_id_erp', 'ilike', search),
            ]])
        report = {'en_compania': Guia.search_count(base), 'analizadas': 0,
                  'destino': 0, 'chofer': 0, 'transporte': 0,
                  'compatible': 0, 'coincide_destino': 0, 'coincide_chofer': 0,
                  'coincide_transporte': 0, 'destino_chofer': 0,
                  'destino_transporte': 0, 'chofer_transporte': 0,
                  'destino_chofer_transporte': 0, 'resumen_destino': [],
                  'sin_chofer_en_destino': 0, 'limite': False,
                  'detalle_busqueda': self._diagnostic_for_search(ruta, search)}
        if not (ruta.proveedor_id and ruta.chofer_usuario_id and ruta.destino_id):
            return [], report
        selected = ruta.seleccion_guia_ids
        selected_map = self._source_map(selected, ruta.company_id.id)
        entries, seen = [], set()
        destination_breakdown = {}
        for guide in selected:
            match, why = self._match(ruta, guide, selected_map.get(guide.id))
            entries.append({'guia': guide, 'selected': bool(match),
                            'available': bool(match), 'reassign': False,
                            'reason': ('Disponible' if match else
                                       'La selección anterior dejó de coincidir con los filtros')})
            seen.add(guide.id)

        before = None
        while report['analizadas'] < MAX_SCAN and report['compatible'] < MAX_DISPLAY:
            domain = list(base)
            if before:
                domain = expression.AND([domain, [('id', '<', before)]])
            candidates = Guia.search(domain, order='id desc', limit=PAGE_SIZE)
            if not candidates:
                break
            before = min(candidates.ids)
            source_map = self._source_map(candidates, ruta.company_id.id)
            report['analizadas'] += len(candidates)
            for guide in candidates:
                source = source_map.get(guide.id)
                # Registrar coincidencias por separado Y sus intersecciones.
                destino_ok = self._destination_matches(ruta, guide, source)
                chofer_ok = self._driver_matches(ruta, guide, source)
                transporte_ok = self._transport_matches(ruta, guide, source)
                report['coincide_destino'] += int(destino_ok)
                report['coincide_chofer'] += int(chofer_ok)
                report['coincide_transporte'] += int(transporte_ok)
                report['destino_chofer'] += int(destino_ok and chofer_ok)
                report['destino_transporte'] += int(destino_ok and transporte_ok)
                report['chofer_transporte'] += int(chofer_ok and transporte_ok)
                report['destino_chofer_transporte'] += int(
                    destino_ok and chofer_ok and transporte_ok)
                if destino_ok and not chofer_ok:
                    report['sin_chofer_en_destino'] += 1
                    driver = (guide.chofer_usuario_id.name if guide.chofer_usuario_id else
                              guide.chofer_contacto_id.name if guide.chofer_contacto_id else
                              source.driver_id.name if source and source.driver_id else
                              'Chofer sin identificar')
                    transporter = (guide.proveedor_id.display_name if guide.proveedor_id else
                                   source.transport_name if source else 'Transporte sin identificar')
                    key = (driver, transporter)
                    current = destination_breakdown.setdefault(key, {
                        'chofer': driver, 'transportista': transporter,
                        'cantidad': 0, 'guias': [],
                    })
                    current['cantidad'] += 1
                    if len(current['guias']) < 3:
                        current['guias'].append(guide.name)
                match, why = self._match(ruta, guide, source)
                if why == 'destino':
                    report['destino'] += 1
                elif why == 'chofer':
                    report['chofer'] += 1
                elif why == 'transporte':
                    report['transporte'] += 1
                if not match:
                    continue
                report['compatible'] += 1
                if guide.id not in seen:
                    seen.add(guide.id)
                    entries.append({'guia': guide, 'selected': guide in selected,
                                    'available': True, 'reassign': False,
                                    'reason': 'Compatible con los tres filtros'})
            if len(candidates) < PAGE_SIZE:
                break
        report['resumen_destino'] = sorted(destination_breakdown.values(),
            key=lambda item: (-item['cantidad'], item['chofer'], item['transportista']))[:10]
        report['limite'] = (report['analizadas'] >= MAX_SCAN or report['compatible'] >= MAX_DISPLAY)
        return entries[:MAX_DISPLAY + len(selected)], report

    def _candidates(self, route, search):
        return self._candidates_and_report(route, search)[0]

    @http.route('/transcash/operacion/rutas/<int:route_id>', type='http',
                auth='user', website=True, methods=['GET'])
    def route_detail(self, route_id, **kw):
        if not self._guard():
            return request.not_found()
        ruta = self._route(route_id)
        if not ruta:
            return request.not_found()
        search = (kw.get('buscar') or '').strip()[:90]
        rows, report = self._candidates_and_report(ruta, search) if ruta.state == 'borrador' else ([], {})
        return self._page('Hoja de ruta ' + ruta.name, section='ruta_detalle', ruta=ruta,
                          filas=rows, tc_filtro_reporte=report, buscar=search,
                          ok=kw.get('ok'), error=kw.get('error'),
                          seleccion_actual=','.join(str(i) for i in sorted(ruta.seleccion_guia_ids.ids)))

    @http.route('/transcash/operacion/rutas/<int:route_id>/guias', type='http',
                auth='user', website=True, methods=['POST'], csrf=True)
    def route_select(self, route_id, **post):
        if not self._guard():
            return request.not_found()
        ruta = self._route(route_id)
        if not ruta:
            return request.not_found()
        try:
            ruta._check_operator()
            with request.env.cr.savepoint():
                request.env.cr.execute(
                    'SELECT id FROM transcash_hoja_ruta WHERE id = %s FOR UPDATE', (ruta.id,))
                ruta.invalidate_recordset(['state', 'seleccion_guia_ids',
                                           'proveedor_id', 'chofer_usuario_id', 'destino_id'])
                if ruta.state != 'borrador':
                    raise UserError(_('La ruta ya fue confirmada.'))
                previous = ','.join(str(i) for i in sorted(ruta.seleccion_guia_ids.ids))
                if post.get('seleccion_actual') != previous:
                    raise UserError(_('Otro operador cambió la selección. Recargue la página.'))
                raw = request.httprequest.form.getlist('guias')
                try:
                    ids = list(dict.fromkeys(int(v) for v in raw))
                except (ValueError, TypeError):
                    raise UserError(_('Se recibieron identificadores de guía inválidos.'))
                if len(ids) > MAX_SELECTION:
                    raise UserError(_('Solo puede agregar hasta 100 guías a la ruta.'))
                if any(n <= 0 for n in ids):
                    raise UserError(_('Se recibió un identificador inválido.'))
                if ids:
                    request.env.cr.execute(
                        'SELECT id FROM transcash_guia WHERE id = ANY(%s) ORDER BY id FOR UPDATE',
                        (ids,))
                selected = request.env['transcash.guia'].browse(ids).exists()
                if len(selected) != len(ids):
                    raise UserError(_('Una o más guías no existen o no están disponibles.'))
                selected.invalidate_recordset([
                    'state', 'company_id', 'hoja_ruta_id', 'embarque_id',
                    'destino_id', 'destino_codigo', 'destino_ciudad', 'destino',
                    'chofer_contacto_id', 'chofer_usuario_id', 'ruc_chofer', 'proveedor_id'])
                source_map = self._source_map(selected, ruta.company_id.id)
                for guia in selected:
                    compatible, reason = self._match(ruta, guia, source_map.get(guia.id))
                    if not compatible:
                        raise UserError(_('La guía %s no cumple el filtro de %s. '
                                          'Revise los datos importados.') % (guia.name, reason))
                # Guardar siempre mediante la acción autorizada de la ruta.
                ruta.write({'seleccion_guia_ids': [(6, 0, ids)]})
                # Completar relaciones técnicamente ausentes SOLO en guías
                # seleccionadas y validadas, antes de confirmar la ruta.
                for guia in selected:
                    source = source_map.get(guia.id)
                    changes = {}
                    if not guia.chofer_usuario_id:
                        changes['chofer_usuario_id'] = ruta.chofer_usuario_id.id
                    elif guia.chofer_usuario_id != ruta.chofer_usuario_id:
                        # Only normalize duplicate accounts verified as the
                        # SAME individual (partner or fiscal identification).
                        if not self._same_driver_identity(
                                guia.chofer_usuario_id, ruta.chofer_usuario_id, guia):
                            raise UserError(_('La guía %s pertenece a otro chofer.') % guia.name)
                        changes['chofer_usuario_id'] = ruta.chofer_usuario_id.id
                    if not guia.chofer_contacto_id:
                        changes['chofer_contacto_id'] = ruta.chofer_usuario_id.partner_id.id
                    if not guia.proveedor_id:
                        changes['proveedor_id'] = ruta.proveedor_id.id
                    elif (guia.proveedor_id.commercial_partner_id.id !=
                          ruta.proveedor_id.commercial_partner_id.id):
                        # Odoo's core confirmation compares partner record IDs.
                        # Only canonicalize duplicates if both VATs are verified.
                        guide_vat = _fiscal_id(guia.proveedor_id.commercial_partner_id.vat)
                        route_vat = _fiscal_id(ruta.proveedor_id.commercial_partner_id.vat)
                        if not guide_vat or guide_vat != route_vat:
                            raise UserError(_('La guía %s pertenece a otro transportista.') % guia.name)
                        changes['proveedor_id'] = ruta.proveedor_id.id
                    if guia.destino_id != ruta.destino_id:
                        if not self._destination_matches(ruta, guia, source):
                            raise UserError(_('La guía %s tiene otro destino.') % guia.name)
                        # Change ONLY the guide's alias to the chosen canonical
                        # destination; never mutate its catalog or historical docs.
                        changes['destino_id'] = ruta.destino_id.id
                        changes['destino_codigo'] = ruta.destino_id.codigo
                    if changes:
                        guia.sudo().write(changes)
                        if ('destino_id' in changes or
                                ('chofer_usuario_id' in changes and source) or
                                'proveedor_id' in changes):
                            guia.sudo().message_post(body=(
                                'PWA: homologación de identidad comprobada al seleccionar '
                                'guía para hoja de ruta %s. Campos: %s.' %
                                (ruta.name, ', '.join(sorted(changes)))))
                # Esta PWA jamás autoriza un cambio de chofer/transportista.
                ruta.sudo().write({'reasignacion_autorizada': False,
                                   'reasignacion_autorizada_por_id': False})
            return request.redirect('/transcash/operacion/rutas/%d?ok=guardadas' % ruta.id)
        except (UserError, AccessError, ValidationError, ValueError, TypeError) as exc:
            return request.redirect('/transcash/operacion/rutas/%d?error=%s' %
                                    (ruta.id, quote(str(exc)[:320])))
