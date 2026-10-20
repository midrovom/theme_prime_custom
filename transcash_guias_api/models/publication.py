"""Publica las guías de staging en las guías operativas v5.32, sin tocar embarques."""
import logging
import re
import unicodedata
from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError

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
        self.ensure_one()
        Destination = self.env['transcash.destino'].sudo()
        route = self.destination_id
        if route and route.external_code:
            found = Destination.search([('company_id', '=', self.company_id.id),
                                        ('codigo', '=', route.external_code.strip().upper())], limit=1)
            if found:
                return found, ''
            # El código del ERP es inequívoco y tiene prioridad al crear el maestro.
            return Destination.obtener_desde_erp(route.external_code, route.city or route.name,
                                                  company_id=self.company_id.id), ''
        # Sin código: comparar exactamente por nombre de destino o ciudad; jamás inventar códigos.
        terms = [x for x in (self.destination_city, self.destination_address) if (x or '').strip()]
        catalog = Destination.search([('company_id', '=', self.company_id.id), ('active', '=', True)])
        for term in terms:
            matches = catalog.filtered(lambda d: normalized(d.name) == normalized(term) or
                                       (d.ciudad and normalized(d.ciudad) == normalized(term)))
            if len(matches) == 1:
                return matches, ''
            if len(matches) > 1:
                return False, _('Destino ambiguo: %s coincide con varios destinos.') % term
        return False, _('No existe código de destino y no hay coincidencia exacta en el catálogo: %s') % (', '.join(terms) or '(vacío)')

    def _partner(self, code, name, as_company=False):
        """Vincular por código ERP conocido; nunca inferir RUC a partir del nombre."""
        if not code:
            return False
        Partner = self.env['res.partner'].sudo()
        partner = Partner.search([('ref', '=', code)], limit=1)
        if partner:
            return partner
        return Partner.create({'name': name or code, 'ref': code,
                               'is_company': bool(as_company)})

    def _publish_one(self):
        self.ensure_one()
        Guide = self.env['transcash.guia'].sudo().with_company(self.company_id)
        existing = Guide.search([('company_id', '=', self.company_id.id),
                                 ('external_id_erp', '=', self.external_id)], limit=1)
        # Nunca tocar información de una guía con proceso logístico iniciado.
        if existing and (existing.state != 'registrada' or existing.hoja_ruta_id or existing.embarque_id or existing.aprobacion_global == 'aprobada'):
            self.sudo().write({'operational_guide_id': existing.id,
                               'publication_state': 'assigned',
                               'publication_note': _('Guía ya asignada o cerrada; no se modifica.')})
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
        if destination:
            values.update({'destino_id': destination.id, 'destino_codigo': destination.codigo})
        else:
            # Evitar datos de destino obsoletos si guía permanece sin ruta.
            values.update({'destino_id': False, 'destino_codigo': False})
        if self.sender_id:
            sender = self._partner(self.sender_id.external_code, self.sender_id.name)
            if sender:
                values['remitente_id'] = sender.id
        if self.recipient_id:
            receiver = self._partner(self.recipient_id.external_code, self.recipient_id.name)
            if receiver:
                values['destinatario_id'] = receiver.id
        if self.transport_id:
            partner = self._partner(self.transport_id.ruc, self.transport_id.name, as_company=True)
            if partner:
                values['proveedor_id'] = partner.id
        # No asignar chofer_usuario_id: no hay login de usuario en el JSON.
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
                # Nunca copiar marca ni proveedor de producto a modelo operativo.
                'marca_codigo': False, 'marca_nombre': False,
                'proveedor_producto_codigo': False, 'proveedor_producto_nombre': False,
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
        self.sudo().write({'operational_guide_id': operational.id,
                           'publication_state': 'published' if destination else 'destination',
                           'publication_note': note or False})

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
