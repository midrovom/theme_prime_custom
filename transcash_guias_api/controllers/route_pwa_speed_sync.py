# -*- coding: utf-8 -*-
"""Transcash v2.23: fast route creation, destination-first guide selection and
manual ERP refresh. Extends controllers only; no changes to v5.32 models.
"""
import logging
from time import perf_counter
from urllib.parse import quote, urlparse

from odoo import http, _
from odoo.exceptions import UserError, AccessError, ValidationError
from odoo.http import request
from odoo.osv import expression

from .route_pwa_strict import TranscashOperacionFiltrada, _fiscal_id

_logger = logging.getLogger(__name__)
# Limit the *ORM* work, not the database universe. Operators can search older
# guide numbers specifically. Route selection still allows at most 100.
DESTINATION_BATCH = 160
DESTINATION_SCAN_LIMIT = 1920
DISPLAY_LIMIT = 180


class TranscashOperacionRapida(TranscashOperacionFiltrada):
    """Override only the slow operations; preserve validation on guide saving."""

    def _new_options(self):
        """Build form choices with SQL GROUP BY through ORM, not 500 full
        guide objects + repeated relational prefetches. Domain and group are
        unchanged from the original controller.
        """
        env = request.env
        companies = env.user.company_ids.ids
        active = env['transcash.chofer'].sudo().search([
            ('company_id', 'in', companies), ('activo', '=', True),
        ], limit=500)
        guide_domain = [
            ('company_id', 'in', companies), ('state', '=', 'registrada'),
            ('embarque_id', '=', False), ('hoja_ruta_id', '=', False),
        ]
        Guide = env['transcash.guia']
        grouped_drivers = Guide.read_group(guide_domain, ['chofer_usuario_id'],
                                           ['chofer_usuario_id'], limit=500, lazy=False)
        grouped_providers = Guide.read_group(guide_domain, ['proveedor_id'],
                                             ['proveedor_id'], limit=500, lazy=False)
        user_ids = {r['chofer_usuario_id'][0] for r in grouped_drivers
                    if r.get('chofer_usuario_id')}
        provider_ids = {r['proveedor_id'][0] for r in grouped_providers
                        if r.get('proveedor_id')}
        user_ids.update(active.mapped('usuario_id').ids)
        provider_ids.update(active.mapped('empresa_transporte_id').ids)
        group = env.ref('logistica_transcash.group_transcash_chofer')
        users = env['res.users'].sudo().browse(list(user_ids)).exists().filtered(
            lambda u: u.active and u.share and group in u.groups_id)
        providers = env['res.partner'].browse(list(provider_ids)).exists()
        destinations = env['transcash.destino'].search([
            ('company_id', 'in', companies), ('active', '=', True),
        ], order='name', limit=500)
        return {'choferes_pwa': users.sorted('name'),
                'proveedores_pwa': providers.sorted('name'),
                'destinos_pwa': destinations}

    @http.route()
    def route_new(self, **post):
        """Never load 500 guides & drivers to validate a single POST."""
        if not self._guard():
            return request.not_found()
        if request.httprequest.method != 'POST':
            return self._page('Nueva hoja de ruta', section='nueva',
                              form_values={}, ok=post.get('ok'),
                              error=post.get('error'), **self._new_options())
        try:
            env = request.env
            company = env.company
            try:
                uid = int(post.get('chofer_id') or 0)
                provider_id = int(post.get('proveedor_id') or 0)
                destination_id = int(post.get('destino_id') or 0)
            except (ValueError, TypeError):
                raise UserError(_('Seleccione transportista, chofer y destino válidos.'))
            plate = (post.get('placa') or '').strip().upper()
            vehicle_type = post.get('tipo_vehiculo')
            if not plate or len(plate) > 20:
                raise UserError(_('Ingrese una placa válida (máximo 20 caracteres).'))
            if vehicle_type not in ('mula', 'camion', 'camioneta', 'furgon', 'otro'):
                raise UserError(_('Seleccione un tipo de vehículo válido.'))
            if not uid or not provider_id or not destination_id:
                raise UserError(_('Seleccione transportista, chofer y destino.'))

            # Use the selected records, not the complete options catalogue.
            driver = env['res.users'].browse(uid).exists()
            provider = env['res.partner'].browse(provider_id).exists()
            dest = env['transcash.destino'].browse(destination_id).exists()
            driver_group = env.ref('logistica_transcash.group_transcash_chofer')
            if not driver or not driver.share or driver_group not in driver.sudo().groups_id:
                raise UserError(_('Seleccione un usuario Portal de chofer activo.'))
            if not driver.active:
                raise UserError(_('El usuario del chofer está desactivado.'))
            if not provider or not provider.active or provider.company_id and provider.company_id != company:
                raise UserError(_('El transportista no está disponible para esta compañía.'))
            if not dest or not dest.active or dest.company_id != company:
                raise UserError(_('El destino no está activo en la compañía seleccionada.'))

            base_guides = [
                ('company_id', '=', company.id), ('state', '=', 'registrada'),
                ('embarque_id', '=', False), ('hoja_ruta_id', '=', False),
            ]
            # Retain the same sources as _new_options() without materializing
            # 500 guide records. A driver/provider may be present in an active
            # driver master OR in a currently free guide.
            driver_allowed = bool(env['transcash.chofer'].sudo().search_count([
                ('company_id', '=', company.id), ('activo', '=', True),
                ('usuario_id', '=', uid),
            ])) or bool(env['transcash.guia'].search_count(
                base_guides + [('chofer_usuario_id', '=', uid)]))
            if not driver_allowed:
                raise UserError(_('El chofer no aparece en los registros disponibles.'))

            provider_allowed = bool(env['transcash.chofer'].sudo().search_count([
                ('company_id', '=', company.id), ('activo', '=', True),
                ('empresa_transporte_id', '=', provider_id),
            ])) or bool(env['transcash.guia'].search_count(
                base_guides + [('proveedor_id', '=', provider_id)]))
            if not provider_allowed:
                raise UserError(_('El transportista no aparece en los registros disponibles.'))

            started_creation = perf_counter()
            route = env['transcash.hoja.ruta'].create({
                'company_id': company.id,
                'chofer_usuario_id': uid,
                'proveedor_id': provider_id,
                'destino_id': destination_id,
                'placa': plate,
                'tipo_vehiculo': vehicle_type,
                'origen': (post.get('origen') or '').strip()[:240],
            })
            _logger.info('PWA creación ruta=%s: %.0f ms', route.id,
                         (perf_counter() - started_creation) * 1000)
            # Only read guides of this destination after creating the record.
            return request.redirect('/transcash/operacion/rutas/%d?ok=creada' % route.id)
        except (UserError, AccessError, ValidationError, ValueError, TypeError) as ex:
            return self._page('Nueva hoja de ruta', section='nueva', error=str(ex),
                              form_values=post, **self._new_options())

    def _destination_page(self, route, last_id=None, search=None):
        """SQL narrows to code ERP before ORM loads the heavyweight records.

        Retain Odoo access checks: IDs go through a normal search with the
        pre-existing eligible domain. SQL does not grant access to anything.
        """
        key = self._normalized_destination_code(route.destino_id.codigo)
        if not key:
            return request.env['transcash.guia'].browse()
        # Exact normalized code, not an approximate match on city or label.
        sql = ("SELECT id FROM transcash_guia "
               "WHERE company_id = %s AND state = 'registrada' "
               "AND embarque_id IS NULL AND hoja_ruta_id IS NULL "
               "AND regexp_replace(upper(coalesce(destino, '')), '[^A-Z0-9]', '', 'g') = %s ")
        args = [route.company_id.id, key]
        if last_id:
            sql += 'AND id < %s '
            args.append(last_id)
        if search:
            sql += ('AND (name ILIKE %s OR numero_documento ILIKE %s '
                    'OR external_id_erp ILIKE %s) ')
            term = '%%%s%%' % search
            args.extend([term, term, term])
        sql += 'ORDER BY id DESC LIMIT %s' 
        args.append(DESTINATION_BATCH)
        request.env.cr.execute(sql, args)
        ids = [row[0] for row in request.env.cr.fetchall()]
        if not ids:
            return request.env['transcash.guia'].browse(), None, 0
        domain = expression.AND([
            route._domain_guias_elegibles(validar_filtros=False), [('id', 'in', ids)]
        ])
        # Return SQL cursor even when record rules hide the whole batch.
        # Otherwise legitimate older guides could disappear from pagination.
        return request.env['transcash.guia'].search(domain, order='id desc'), min(ids), len(ids)

    def _driver_guide_overview(self, ruta, search=''):
        """Single COUNT instead of loading 200 guides + all their ERP sources."""
        user = ruta.chofer_usuario_id
        if not user:
            return {'guias': [], 'total_mostradas': 0, 'mas_resultados': False,
                    'totales': [], 'tiene_criterio': False}
        partner = user.partner_id
        docs = {_fiscal_id(v) for v in (user.login, partner.vat)} - {''}
        ors = [[('chofer_usuario_id', '=', user.id)],
               [('chofer_contacto_id', '=', partner.id)]]
        if docs:
            ors.append([('ruc_chofer', 'in', sorted(docs))])
        domain = expression.AND([
            [('company_id', '=', ruta.company_id.id)], expression.OR(ors)
        ])
        total = request.env['transcash.guia'].search_count(domain)
        return {'guias': [], 'total_mostradas': total, 'mas_resultados': False,
                'totales': [], 'tiene_criterio': True, 'chofer': user.name}

    def _candidates_and_report(self, ruta, search):
        """Destination-first, bounded guide evaluation; never scan 6000 guides
        of unrelated destinations just to open a new route.
        """
        Guia = request.env['transcash.guia']
        default = {'en_compania': 0, 'analizadas': 0, 'destino': 0, 'chofer': 0,
                   'transporte': 0, 'compatible': 0, 'coincide_destino': 0,
                   'coincide_chofer': 0, 'coincide_transporte': 0,
                   'destino_chofer': 0, 'destino_transporte': 0,
                   'chofer_transporte': 0, 'destino_chofer_transporte': 0,
                   'resumen_destino': [], 'sin_chofer_en_destino': 0,
                   'limite': False, 'detalle_busqueda': []}
        if not (ruta.destino_id and ruta.chofer_usuario_id and ruta.proveedor_id):
            return [], default
        base = ruta._domain_guias_elegibles(validar_filtros=False)
        default['en_compania'] = Guia.search_count(base)
        # Counts for cards: independent matches (not necessarily the same guides).
        # They do not affect selection; server-side _match remains authoritative.
        dest_key = self._normalized_destination_code(ruta.destino_id.codigo)
        if dest_key:
            request.env.cr.execute(
                "SELECT count(*) FROM transcash_guia WHERE company_id=%s "
                "AND state='registrada' AND embarque_id IS NULL "
                "AND hoja_ruta_id IS NULL "
                "AND regexp_replace(upper(coalesce(destino,'')), '[^A-Z0-9]', '', 'g')=%s",
                (ruta.company_id.id, dest_key))
            default['coincide_destino'] = request.env.cr.fetchone()[0]
        chosen = ruta.proveedor_id.commercial_partner_id
        if chosen:
            default['coincide_transporte'] = Guia.search_count(expression.AND([
                base, [('proveedor_id.commercial_partner_id', '=', chosen.id)]
            ]))

        started = perf_counter()
        selected = ruta.seleccion_guia_ids
        seen = set()
        entries = []
        sources = self._source_map(selected, ruta.company_id.id)
        for guia in selected:
            eligible, _ = self._match(ruta, guia, sources.get(guia.id))
            entries.append({'guia': guia, 'selected': eligible,
                            'available': eligible, 'reassign': False,
                            'reason': 'Disponible' if eligible else 'La guía dejó de estar disponible'})
            seen.add(guia.id)

        last_id = None
        scanned = 0
        displayed = 0
        while scanned < DESTINATION_SCAN_LIMIT and displayed < DISPLAY_LIMIT:
            batch, next_cursor, raw_count = self._destination_page(ruta, last_id, search)
            if not raw_count:
                break
            last_id = next_cursor
            scanned += raw_count
            filtered = batch
            source_map = self._source_map(filtered, ruta.company_id.id)
            for guide in filtered:
                if guide.id in seen:
                    continue
                source = source_map.get(guide.id)
                # SQL already restricted destination to matching ERP code.
                if not self._driver_matches(ruta, guide, source):
                    default['chofer'] += 1
                    continue
                if not self._transport_matches(ruta, guide, source):
                    default['transporte'] += 1
                    continue
                if not self._destination_matches(ruta, guide, source):
                    continue
                # Old imported guides may be verified by ERP data despite
                # having no operational provider_id yet. The card cannot say
                # '0 transportista' while such a guide is actually accepted.
                default['coincide_transporte'] = max(
                    default['coincide_transporte'], displayed + 1)
                default['compatible'] += 1
                default['destino_chofer_transporte'] += 1
                displayed += 1
                entries.append({'guia': guide, 'selected': False,
                                'available': True, 'reassign': False,
                                'reason': 'Compatible con los tres filtros'})
                seen.add(guide.id)
                if displayed >= DISPLAY_LIMIT:
                    break
            if raw_count < DESTINATION_BATCH:
                break
        default['analizadas'] = scanned
        default['limite'] = (scanned >= DESTINATION_SCAN_LIMIT or displayed >= DISPLAY_LIMIT)
        # Exact search diagnostic is only needed when user actively searches.
        if search and len(search) >= 3:
            default['detalle_busqueda'] = self._diagnostic_for_search(ruta, search)
        _logger.info('PWA ruta=%s candidatos: %s SQL, %s compatibles en %.0f ms',
                     ruta.id, scanned, displayed, (perf_counter() - started) * 1000)
        return entries, default

    @http.route('/transcash/operacion/guias/sincronizar', type='http', auth='user',
                website=True, methods=['POST'], csrf=True)
    def sync_guides_pwa(self, **post):
        """Manual ERP refresh for route planners, with server-side anti-repeat.

        Do not expose ERP credentials to the browser; use api.administrator.
        """
        if not self._guard() or request.env.user.share:
            return request.not_found()
        company_id = request.env.company.id
        raw_return = (post.get('volver') or '/transcash/operacion/rutas/nueva').strip()
        url = urlparse(raw_return)
        allowed_prefixes = ('/transcash/operacion/rutas', '/transcash/operacion')
        return_to = (raw_return if not url.scheme and not url.netloc and
                     raw_return.startswith(allowed_prefixes) and
                     not raw_return.startswith('//') else '/transcash/operacion/rutas/nueva')
        try:
            # Do not allow two manual PWA refreshes to run at the same time
            # for a company. The lock is released with the HTTP transaction.
            request.env.cr.execute('SELECT pg_try_advisory_xact_lock(%s, %s)',
                                   (623481, company_id))
            if not request.env.cr.fetchone()[0]:
                raise UserError(_('Ya hay una sincronización en curso para esta empresa.'))
            result = request.env['transcash.guia']._transcash_run_api_sync(company_id)
            if not isinstance(result, dict):
                raise UserError(_('La sincronización no devolvió un resultado válido.'))
            if result.get('errors'):
                msg = _('Guías creadas: %s, actualizadas: %s; %s con errores. Revise el historial ERP.') % (
                    result.get('created', 0), result.get('updated', 0), len(result['errors']))
            else:
                msg = _('Guías ERP actualizadas. Nuevas: %s; revisadas: %s.') % (
                    result.get('created', 0), result.get('updated', 0))
            _logger.info('Sincronización PWA getguiaslogistica por user=%s empresa=%s: %s',
                         request.env.user.id, company_id, msg)
            return request.redirect('%s%sok=%s' % (
                return_to, '&' if '?' in return_to else '?', quote(msg)))
        except (UserError, AccessError, ValidationError, ValueError, TypeError) as exc:
            return request.redirect('%s%serror=%s' % (
                return_to, '&' if '?' in return_to else '?', quote(str(exc)[:240])))
        except Exception:
            _logger.exception('Error sincronizando getguiaslogistica desde PWA')
            return request.redirect('%s%serror=%s' % (
                return_to, '&' if '?' in return_to else '?',
                quote(_('No se pudo actualizar las guías. Revise el registro del servidor.'))))
