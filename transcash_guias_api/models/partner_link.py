"""Homologación segura de terceros del ERP con Contactos y los perfiles Portal v5.32.

No crea usuarios ni otorga grupos Portal: se mantienen las activaciones auditadas
por Logística Transcash. La importación es repetible (upsert por identidad).
"""
import logging
import re

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)


def _clean(value):
    return str(value).strip() if value not in (None, False) else ''


def _identifier(value):
    """Normalización para cotejar identificaciones, NO validación tributaria."""
    return re.sub(r'[^A-Z0-9]', '', _clean(value).upper())


def _is_tax(value):
    # Los códigos logísticos como -NAJ y PRS3339 NO son documentos fiscales.
    return bool(re.fullmatch(r'[A-Z0-9]{10,15}', _identifier(value))) and bool(
        re.fullmatch(r'[A-Z0-9]{10,15}', _clean(value).upper().replace(' ', ''))
        or re.fullmatch(r'[0-9][0-9.\- ]{9,19}', _clean(value)))


class TCGuidePartnerLink(models.Model):
    _inherit = 'tc.guide'

    transport_partner_id = fields.Many2one('res.partner', string='Transportista Odoo', readonly=True, copy=False)
    driver_partner_id = fields.Many2one('res.partner', string='Contacto del chofer', readonly=True, copy=False)
    sender_partner_id = fields.Many2one('res.partner', string='Remitente Odoo', readonly=True, copy=False)
    recipient_partner_id = fields.Many2one('res.partner', string='Destinatario Odoo', readonly=True, copy=False)
    driver_user_id = fields.Many2one('res.users', string='Portal chofer autorizado', readonly=True, copy=False)
    transport_tax_raw = fields.Char(string='Identificación de transportista ERP', readonly=True)
    recipient_tax_raw = fields.Char(string='Identificación del destinatario ERP', readonly=True)
    master_link_state = fields.Selection([
        ('complete', 'Vínculos verificados'),
        ('pending', 'Pendiente de vinculación'),
    ], string='Vínculos con el portal', default='pending', readonly=True, copy=False, index=True)
    master_link_note = fields.Text(string='Pendientes / observaciones de accesos', readonly=True, copy=False)

    def _partner_by_tax(self, tax):
        """Coteja RUC/cédula con o sin separadores; no mezcla compañías restringidas."""
        self.ensure_one()
        normalized = _identifier(tax)
        if not normalized:
            return self.env['res.partner'].browse(), ''
        variants = {normalized}
        if normalized.startswith('EC') and normalized[2:].isdigit():
            variants.add(normalized[2:])
        if normalized.isdigit():
            variants.add('EC' + normalized)
        # Consulta parametrizada para limitar candidatos por identificación normalizada.
        self.env.cr.execute('''
            SELECT id FROM res_partner
             WHERE (company_id IS NULL OR company_id = %s)
               AND UPPER(REGEXP_REPLACE(COALESCE(vat, ''), '[^A-Za-z0-9]', '', 'g')) = ANY(%s)
             ORDER BY id LIMIT 3
        ''', (self.company_id.id, list(variants)))
        ids = [row[0] for row in self.env.cr.fetchall()]
        if len(ids) > 1:
            return False, _('Hay varios contactos con la misma identificación %s; revisar duplicados.') % tax
        return (self.env['res.partner'].sudo().browse(ids[0]), '') if ids else (False, '')

    def _partner_by_ref(self, code):
        self.ensure_one()
        Partner = self.env['res.partner'].sudo().with_context(active_test=False)
        matches = Partner.search([
            ('ref', '=', code), '|', ('company_id', '=', False),
            ('company_id', '=', self.company_id.id),
        ], limit=3)
        if len(matches) > 1:
            return False, _('Código ERP %s duplicado en Contactos.') % code
        return (matches, '') if matches else (False, '')

    def _upsert_contact(self, kind, name, tax='', code='', street='', company=False):
        """VAT prioritario, luego referencia ERP; no relaciona terceros por nombre."""
        self.ensure_one()
        name, tax, code = _clean(name), _clean(tax), _clean(code)
        if kind == 'transport' and not tax:
            return False, _('Falta RUC del transportista %s. Envíe transportista.ruc desde ERP.') % (name or '-')
        if tax and not _is_tax(tax):
            return False, _('Identificación de %s inválida o insuficiente: %s.') % (kind, tax)
        partner = False
        message = ''
        if tax:
            partner, message = self._partner_by_tax(tax)
            if message:
                return False, message
        if not partner and code:
            partner, message = self._partner_by_ref(code)
            if message:
                return False, message
            if partner and tax and partner.vat and _identifier(partner.vat) != _identifier(tax):
                return False, _('El código %s pertenece a otro documento fiscal (%s).') % (code, kind)
        if not partner:
            if not tax and not code:
                return False, _('Falta documento o código ERP de %s: %s.') % (kind, name or '-')
            if not name:
                return False, _('Falta nombre de %s para crear contacto.') % kind
            vals = {'name': name, 'is_company': company, 'company_id': False}
            if tax:
                vals['vat'] = tax
            if code:
                vals['ref'] = code
            if street:
                vals['street'] = street
            partner = self.env['res.partner'].sudo().create(vals)
        else:
            if tax and partner.vat and _identifier(partner.vat) != _identifier(tax):
                return False, _('Identificación incompatible para %s en res.partner (%s).') % (kind, partner.id)
            # Nunca pisar datos gestionados manualmente ni relaciones padre.
            vals = {}
            if tax and not partner.vat:
                vals['vat'] = tax
            if code and not partner.ref:
                vals['ref'] = code
            if street and not partner.street:
                vals['street'] = street
            if vals:
                partner.sudo().write(vals)
        return partner, message

    def _resolve_driver_user(self, partner, transport=False):
        """Solo cuenta Portal ya habilitada; nunca inventa un login ni permisos."""
        self.ensure_one()
        if not partner:
            return False, _('Sin contacto del chofer para enlazar con cuenta Portal.')
        users = self.env['res.users'].sudo().with_context(active_test=False).search([
            ('partner_id', '=', partner.id), ('share', '=', True), ('active', '=', True),
        ], limit=4)
        users = users.filtered(lambda u: u.has_group('base.group_portal'))
        if len(users) != 1:
            return False, (_('Hay varias cuentas Portal para el chofer; revisar.') if len(users) > 1
                           else _('Chofer sin usuario Portal existente; invite el contacto desde Odoo.'))
        user = users[0]
        if not user.has_group('logistica_transcash.group_transcash_chofer'):
            return False, _('Usuario Portal del chofer no tiene activado el perfil Chofer Transcash.')
        registrations = self.env['transcash.chofer'].sudo().search([('usuario_id', '=', user.id)])
        if registrations and not any(r.activo and r.company_id.id == self.company_id.id for r in registrations):
            return False, _('El registro del chofer existe, pero no está activo para esta empresa.')
        # Usuario autorizado anteriormente, pero sin ficha en el directorio:
        # registrar ficha SIN asignar grupos ni crear credenciales.
        if not registrations:
            self.env['transcash.chofer'].sudo().create({
                'usuario_id': user.id,
                'company_id': self.company_id.id,
                'activo': True,
                'carga_autonoma': False,
                'empresa_transporte_id': transport.id if transport else False,
            })
        return user, ''

    def _has_role_portal(self, partner, role):
        """Verifica acceso existente; no crea permisos ni cuentas nuevas."""
        self.ensure_one()
        if not partner:
            return False
        group = ('logistica_transcash.group_transcash_cliente' if role == 'recipient'
                 else 'logistica_transcash.group_transcash_transportista')
        directory = ('transcash.acceso.cliente' if role == 'recipient'
                     else 'transcash.acceso.proveedor')
        # Portal del contacto o de algún empleado/hijo de su compañía comercial.
        users = self.env['res.users'].sudo().search([
            ('partner_id', 'child_of', partner.commercial_partner_id.id),
            ('share', '=', True), ('active', '=', True),
        ], limit=200)
        for user in users:
            if not user.has_group('base.group_portal') or not user.has_group(group):
                continue
            access = self.env[directory].sudo().search([('usuario_id', '=', user.id)])
            if not access or any(a.activo and a.company_id.id == self.company_id.id for a in access):
                return True
        return False

    def _link_master_partners(self):
        self.ensure_one()
        # Serializa el alta de terceros por empresa durante esta transacción.
        # Evita que dos sincronizaciones simultáneas creen duplicados.
        self.env.cr.execute('SELECT id FROM res_company WHERE id = %s FOR UPDATE', (self.company_id.id,))
        notes = []
        transport_name = self.transport_name or (self.transport_id.name if self.transport_id else '')
        transport_tax = self.transport_tax_raw or (self.transport_id.ruc if self.transport_id else '')
        transport, message = self._upsert_contact('transport', transport_name, tax=transport_tax, company=True)
        if message:
            notes.append(message)
        if transport and not self._has_role_portal(transport, 'transport'):
            notes.append(_('Transportista sin perfil Portal de proveedor habilitado en esta empresa.'))
        driver_tax = self.driver_id.identification if self.driver_id else ''
        driver, message = self._upsert_contact('driver', self.driver_id.name if self.driver_id else '',
                                                tax=driver_tax)
        if message:
            notes.append(message)
        user, message = self._resolve_driver_user(driver, transport)
        if message:
            notes.append(message)
        sender = False
        if self.sender_id:
            sender_code = _clean(self.sender_id.external_code)
            sender_tax = sender_code if sender_code.isdigit() and len(sender_code) in (10, 13) else ''
            sender, message = self._upsert_contact('sender', self.sender_id.name,
                tax=sender_tax, code=sender_code, street=self.origin_address, company=True)
            if message:
                notes.append(message)
        else:
            notes.append(_('Sin remitente identificado en el ERP.'))
        recipient = False
        if self.recipient_id:
            code = self.recipient_id.external_code
            tax = self.recipient_tax_raw or (code if code.isdigit() and len(code) in (10, 13) else '')
            recipient, message = self._upsert_contact('recipient', self.recipient_id.name,
                tax=tax, code=code, street=self.destination_address)
            if message:
                notes.append(message)
            if recipient and not self._has_role_portal(recipient, 'recipient'):
                notes.append(_('Destinatario sin perfil Portal de cliente habilitado en esta empresa.'))
        else:
            notes.append(_('Sin código identificador de destinatario en el ERP.'))
        vals = {
            'transport_partner_id': transport.id if transport else False,
            'driver_partner_id': driver.id if driver else False,
            'driver_user_id': user.id if user else False,
            'sender_partner_id': sender.id if sender else False,
            'recipient_partner_id': recipient.id if recipient else False,
            'master_link_state': 'pending' if notes else 'complete',
            'master_link_note': '\n'.join(notes)[:4000] if notes else False,
        }
        self.sudo().write(vals)

    def _publish_one(self):
        # Se ejecuta también para guías ya importadas cuando se concilian manualmente.
        self.ensure_one()
        self._link_master_partners()
        return super()._publish_one()

    def action_reconcile_related_partners(self):
        user = self.env.user
        if user.share or not (self.env.su or user.has_group('transcash_guias_api.group_tc_sync_admin')
                              or user.has_group('logistica_transcash.group_logistica_manager')):
            raise AccessError(_('Solo la administración de Logística puede conciliar terceros.'))
        success = failed = 0
        for rec in self:
            if rec.company_id not in user.company_ids and not self.env.su:
                raise AccessError(_('No tiene acceso a la compañía de esta guía.'))
            try:
                with self.env.cr.savepoint():
                    rec.sudo()._publish_one()
                    success += 1
            except Exception:
                failed += 1
                _logger.exception('Conciliación fallida para guía ERP %s', rec.external_id)
        return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
            'title': _('Conciliación de terceros'),
            'message': _('Revisadas: %s; errores: %s. Las pendientes se muestran en Vínculos con el portal.') % (success, failed),
            'type': 'warning' if failed else 'success', 'sticky': bool(failed),
        }}

    @api.model
    def action_reconcile_company(self):
        user = self.env.user
        if user.share or not (self.env.su or user.has_group('transcash_guias_api.group_tc_sync_admin')
                              or user.has_group('logistica_transcash.group_logistica_manager')):
            raise AccessError(_('Sin permiso para conciliar terceros.'))
        guides = self.search([('company_id', '=', self.env.company.id)])
        return guides.action_reconcile_related_partners()
