"""Publica las guías de staging en las guías operativas v5.32, sin tocar embarques."""
import logging
import re
import unicodedata
from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError
from .date_bridge import date_as_odoo_utc

_logger = logging.getLogger(__name__)


def normalized(value):
    raw = unicodedata.normalize('NFKD', (value or '').strip().casefold())
    return ' '.join(''.join(c for c in raw if not unicodedata.combining(c)).split())


def infer_unit(description, sku=''):
    """m2 si el producto es revestimiento por superficie; unidad en otros casos.

    No basta un tamaño (ej. 30x60) porque también aparece en accesorios.
    """
    text = normalized('%s %s' % (description, sku))
    square = bool(re.search(r'\b(?:m2|mt2|m²|metros? cuadrados?)\b', text))
    material = bool(re.search(r'\b(?:ceramica|porcelanato|granito|baldosa|azulejo|revestimiento|marmol|piso|pisos|porcelanico|gres|loseta)\b', text))
    # No clasificar accesorios por la mera aparición de las palabras de material.
    accessory = bool(re.search(r'\b(?:pegamento|adhesivo|boquilla|frag[uü]a|sellador|perfil|separador|nivelador|griferia|lavamanos|inodoro)\b', text))
    return 'm2' if (square or (material and not accessory)) else 'unidad'


class TCGuidePublication(models.Model):
    _inherit = 'tc.guide'

    publication_state = fields.Selection([
        ('pending', 'Pendiente'), ('published', 'Disponible en logística'),
        ('destination', 'Destino por homologar'), ('error', 'Error de publicación'),
        ('assigned', 'En operación'),
    ], default='pending', readonly=True, copy=False, index=True)
    publication_note = fields.Text('Observación de publicación', readonly=True, copy=False)
    operational_guide_id = fields.Many2one('transcash.guia', string='Guía operativa', readonly=True, copy=False)

    def _destination_for_operation(self):
        """Encontrar destino por el CÓDIGO del ERP, nunca por nombre ni alias.

        Reutiliza una ficha con código idéntico tras quitar separadores de
        formato; si hay varias no se adivina el registro correcto.
        """
        self.ensure_one()
        Destination = self.env['transcash.destino'].sudo()
        raw = self.destination_id.external_code if self.destination_id else ''
        code = re.sub(r'[^A-Z0-9]', '', unicodedata.normalize(
            'NFKD', str(raw or '').upper()))
        if not code:
            return False, _('La API ERP no envió destino_codigo. No se asigna destino por nombre.')
        catalog = Destination.search([('company_id', '=', self.company_id.id)])
        matching = catalog.filtered(
            lambda d: re.sub(r'[^A-Z0-9]', '', unicodedata.normalize(
                'NFKD', str(d.codigo or '').upper())) == code)
        if len(matching) == 1:
            return matching, ''
        if len(matching) > 1:
            return False, _('Existen varios destinos con el mismo código normalizado %s.') % code
        # Código ERP nuevo: lo crea el flujo normal del módulo operativo.
        return Destination.obtener_desde_erp(
            raw, self.destination_city or self.destination_address or raw,
            company_id=self.company_id.id), ''

    def _erp_dates_for_operation(self, operational=None, only_missing=False):
        """Map ERP calendar dates to the EXISTING operational fields.

        Odoo fields are Datetime; the ERP only sends dates. Store midnight in
        company local time as UTC for consistent calendar display in Ecuador.
        In assigned/delivered trips do not rewrite any existing value.
        """
        self.ensure_one()
        timezone_name = self.company_id.partner_id.tz or 'America/Guayaquil'
        bindings = (
            ('erp_start_date', 'fecha_inicio_traslado'),
            ('erp_end_date', 'fecha_fin_traslado'),
            ('erp_planned_date', 'fecha_prevista'),
        )
        result = {}
        for source, target in bindings:
            raw = self[source]
            if raw and (not only_missing or not operational or not operational[target]):
                result[target] = date_as_odoo_utc(raw, timezone_name)
        return result

    def _link_private_operational_lines(self, operational):
        """Join each restricted ERP commercial row to its exact operational line.

        No commercial value is written to the public operational line model.
        This link lets private KPI queries aggregate by brand/product supplier
        without exposing those fields to drivers, customers or transporters.
        """
        self.ensure_one()
        Private = self.env['tc.guide.line.private'].sudo().with_company(self.company_id)
        OpLine = self.env['transcash.guia.linea'].sudo().with_company(self.company_id)
        operational_lines = OpLine.search([('guia_id', '=', operational.id)])
        by_external = {ln.external_line_id: ln for ln in operational_lines if ln.external_line_id}
        private_rows = Private.search([('line_id.guide_id', '=', self.id)])
        result = {'linked': 0, 'missing_line': 0}
        for private in private_rows:
            operational_line = by_external.get(private.line_id.external_line_id)
            if not operational_line:
                result['missing_line'] += 1
                continue
            if private.operational_line_id != operational_line:
                # Un enlace nunca debe apuntar a otra guía/compañía.
                private.write({'operational_line_id': operational_line.id})
            result['linked'] += 1
        return result

    def _repair_dates_and_links(self):
        """Backfill historical guides without republishing their operational data."""
        self.ensure_one()
        Guide = self.env['transcash.guia'].sudo().with_company(self.company_id)
        operational = self.operational_guide_id
        if (not operational or operational.company_id != self.company_id or
                operational.external_id_erp != self.external_id):
            operational = Guide.search([
                ('company_id', '=', self.company_id.id),
                ('external_id_erp', '=', self.external_id)], limit=1)
        if not operational:
            return {'guides': 0, 'dates': 0, 'linked': 0, 'missing_line': 0}
        # Only pending/free guides may have their planned dates refreshed.
        assigned = (operational.state != 'registrada' or operational.hoja_ruta_id or
                    operational.embarque_id or operational.aprobacion_global == 'aprobada')
        date_values = self._erp_dates_for_operation(operational, only_missing=bool(assigned))
        updates = {name: value for name, value in date_values.items()
                   if operational[name] != value}
        if updates:
            operational.write(updates)
        links = self._link_private_operational_lines(operational)
        if self.operational_guide_id != operational:
            self.write({'operational_guide_id': operational.id})
        return {'guides': 1, 'dates': len(updates), **links}

    def _publish_one(self):
        self.ensure_one()
        Guide = self.env['transcash.guia'].sudo().with_company(self.company_id)
        existing = Guide.search([('company_id', '=', self.company_id.id),
                                 ('external_id_erp', '=', self.external_id)], limit=1)
        # No tocar datos de carga, transportista, chofer ni estados de una guía
        # en operación. Solo completar remitente/destinatario vacíos y, cuando
        # coincidan EXACTAMENTE con ruta/embarque, asignaciones vacías.
        if existing and (existing.state != 'registrada' or existing.hoja_ruta_id or existing.embarque_id or existing.aprobacion_global == 'aprobada'):
            additions = {}
            if not existing.remitente_id and self.sender_partner_id:
                additions['remitente_id'] = self.sender_partner_id.id
            if not existing.destinatario_id and self.recipient_partner_id:
                additions['destinatario_id'] = self.recipient_partner_id.id
            # El contacto no sustituye al usuario responsable del viaje.
            # En viajes ya iniciados solo se completa cuando no contradice al
            # chofer manual (usuario, o identificación ERP registrada).
            if self.driver_partner_id and not existing.chofer_contacto_id:
                same_document = (not existing.ruc_chofer or
                                 normalized(existing.ruc_chofer) == normalized(self.driver_partner_id.vat))
                same_user = (not existing.chofer_usuario_id or
                             existing.chofer_usuario_id.partner_id == self.driver_partner_id)
                if same_document and same_user:
                    additions['chofer_contacto_id'] = self.driver_partner_id.id
            plan = existing.hoja_ruta_id or existing.embarque_id
            if plan:
                if (not existing.proveedor_id and self.transport_partner_id and
                        plan.proveedor_id == self.transport_partner_id):
                    additions['proveedor_id'] = self.transport_partner_id.id
                if (not existing.chofer_usuario_id and self.driver_user_id and
                        plan.chofer_usuario_id == self.driver_user_id):
                    additions['chofer_usuario_id'] = self.driver_user_id.id
            # Guías en operación: completar solamente fechas ERP faltantes.
            # Nunca se cambia una fecha que ya está registrada en el viaje.
            additions.update(self._erp_dates_for_operation(existing, only_missing=True))
            if additions:
                existing.write(additions)
            self._link_private_operational_lines(existing)
            self.sudo().write({'operational_guide_id': existing.id,
                               'publication_state': 'assigned',
                               'publication_note': '\n'.join(filter(None, (
                                   _('Guía en operación: se respetan chofer, transporte, estado y evidencias.'),
                                   self.master_link_note)))})
            return
        destination, note = self._destination_for_operation()
        values = {
            'name': self.name, 'external_id_erp': self.external_id,
            'company_id': self.company_id.id, 'tipo_documento': self.document_type or False,
            'numero_documento': self.document_number or False,
            'estado_erp': self.erp_state or False,
            'placa': self.vehicle_id.plate if self.vehicle_id else False,
            'ruc_chofer': self.driver_id.identification if self.driver_id else False,
            'origen': self.origin_address or False,
            'destino': self.destination_address or False,
            'destino_ciudad': self.destination_city or False,
            'descripcion_carga': self.cargo_description or False,
            'ultima_sync': fields.Datetime.now(),
            'peso_kg': sum(self.line_ids.mapped('weight_kg')),
        }
        values.update(self._erp_dates_for_operation(existing, only_missing=False))
        if destination:
            values.update({'destino_id': destination.id, 'destino_codigo': (
                self.destination_id.external_code if self.destination_id else False)})
        else:
            # Evitar datos de destino obsoletos si guía permanece sin ruta.
            values.update({'destino_id': False, 'destino_codigo': False})
        # Relaciones operativas res.partner/res.users: resueltas previamente
        # en partner_link.py por VAT/ref o perfil Portal verificado.
        bindings = {
            'remitente_id': self.sender_partner_id,
            'destinatario_id': self.recipient_partner_id,
            'proveedor_id': self.transport_partner_id,
            # El contacto es independiente de la invitación Portal.
            'chofer_contacto_id': self.driver_partner_id,
            'chofer_usuario_id': self.driver_user_id,
        }
        mismatches = []
        for field_name, new_partner in bindings.items():
            if not new_partner:
                continue
            if (field_name == 'chofer_contacto_id' and existing
                    and existing.chofer_usuario_id
                    and existing.chofer_usuario_id.partner_id != new_partner):
                mismatches.append(_('Chofer ERP distinto del usuario del chofer asignado; conservar operación.'))
                continue
            if (field_name == 'chofer_usuario_id' and existing
                    and existing.chofer_contacto_id
                    and existing.chofer_contacto_id != new_partner.partner_id):
                mismatches.append(_('El usuario Portal no coincide con el contacto chofer de la guía.'))
                continue
            current = existing[field_name] if existing else False
            if current and current != new_partner:
                # Las asignaciones manuales solo se cambian desde Logística.
                mismatches.append(_('%s: ya existe una asignación diferente; se conserva.') % field_name)
            else:
                values[field_name] = new_partner.id
        if mismatches:
            note = '\n'.join(([note] if note else []) + mismatches)
        if existing:
            existing.write(values)
            operational = existing
        else:
            operational = Guide.create(values)
        Line = self.env['transcash.guia.linea'].sudo()
        for line in self.line_ids:
            vals = {
                'guia_id': operational.id, 'external_line_id': line.external_line_id,
                'codigo': line.sku, 'producto': line.name,
                'cantidad': line.quantity, 'unidad': infer_unit(line.name, line.sku),
                'precio_unitario': 0.0, 'peso_kg': line.weight_kg,
                'pallets_info': line.pallets, 'cajas_info': line.boxes,
                'vigente_erp': True,
                # No trasladar información comercial de marca/proveedor al modelo operativo.
            }
            old = Line.search([('guia_id', '=', operational.id),
                               ('external_line_id', '=', line.external_line_id)], limit=1)
            if old:
                # Proteger roturas previas y decisiones operativas del usuario.
                if old.rotura_ids:
                    continue
                old.write(vals)
            else:
                Line.create(vals)
        self._link_private_operational_lines(operational)
        self.sudo().write({'operational_guide_id': operational.id,
                           'publication_state': 'published' if destination else 'destination',
                           'publication_note': '\n'.join(filter(None, (note, self.master_link_note))) or False})

    def _publish_safe(self):
        for guide in self:
            try:
                with self.env.cr.savepoint():
                    guide._publish_one()
            except Exception as exc:
                _logger.exception('Error publicando guía %s', guide.external_id)
                guide.sudo().write({'publication_state': 'error', 'publication_note': str(exc)[:1500]})

    def action_publish_to_logistics(self):
        if not (self.env.is_superuser() or self.env.user.has_group('transcash_guias_api.group_tc_sync_admin')
                or self.env.user.has_group('logistica_transcash.group_logistica_manager')):
            raise AccessError(_('Sin permiso para publicar guías.'))
        guides = self or self.search([('company_id', '=', self.env.company.id),
                                      ('publication_state', 'in', ['pending', 'destination', 'error'])])
        guides._publish_safe()
        return {'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {'title': _('Publicación de guías'),
                           'message': _('%s guías verificadas. Revise la columna Publicación para identificar destinos pendientes.') % len(guides),
                           'type': 'success', 'sticky': False}}


class TCGuideSyncPublish(models.Model):
    _inherit = 'tc.guide.sync'

    @api.model
    def _import_one(self, data, company_id):
        created = super()._import_one(data, company_id)
        external = str(data.get('id_externo') or '').strip()
        guide = self.env['tc.guide'].sudo().search([
            ('company_id', '=', company_id), ('external_id', '=', external)], limit=1)
        if guide:
            guide._publish_safe()
        return created
