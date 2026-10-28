# -*- coding: utf-8 -*-
"""Cuentas Portal preparadas por el ERP; activación funcional siempre manual.

El vínculo del contacto se construye en partner_link. Este archivo no toca
las contraseñas ni grupos de usuarios existentes y nunca habilita perfiles.
"""
import logging

from odoo import api, fields, models, _, SUPERUSER_ID
from odoo.exceptions import AccessError, ValidationError, UserError

from .fiscal_identity import fiscal_document

_logger = logging.getLogger(__name__)


class TcPortalPasswordState(models.Model):
    _name = 'tc.portal.password.state'
    _description = 'Cambio requerido de contraseña inicial Portal Transcash'
    _rec_name = 'user_id'

    user_id = fields.Many2one('res.users', required=True, ondelete='cascade', index=True)
    pending = fields.Boolean(default=True, required=True)

    _sql_constraints = [
        ('user_unique', 'unique(user_id)', 'Solo puede existir un estado inicial por cuenta Portal.'),
    ]




class TcGuidePortalAccounts(models.Model):
    _inherit = 'tc.guide'

    @api.model
    def _tc_existing_or_new_user(self, partner, company, role):
        """Devuelve el usuario Portal de un contacto, sin elevar sus privilegios.

        Identidad principal = res.partner. No se apropia de un login vinculado
        a otra ficha. Si el contacto es una compañía se permite usarla como
        cuenta Portal empresarial, siempre que no tenga otro usuario incompatible.
        """
        if not partner or not company:
            return False, _('Falta contacto o empresa para preparar la cuenta Portal.')
        if not partner.active:
            return False, _('Contacto archivado: no se prepara una cuenta nueva.')

        document = fiscal_document(partner.vat or '')
        if not document or len(document) < 5:
            return False, _('El contacto %s no tiene identificación suficiente para iniciar sesión.') % partner.display_name

        Users = self.env['res.users'].with_user(SUPERUSER_ID).with_context(active_test=False)
        self.env.cr.execute('SELECT pg_advisory_xact_lock(hashtext(%s), hashtext(%s))',
                            ('tc.portal.login', document))
        # Por contacto, aunque el usuario esté archivado.
        linked = Users.search([('partner_id', '=', partner.id)])
        if len(linked) > 1:
            return False, _('El contacto %s tiene varias cuentas. Revisión manual.') % partner.display_name
        if linked:
            user = linked[0]
            if not user.active:
                return False, _('Usuario archivado de %s. No se crea otro.') % partner.display_name
            if not user.share or not user.has_group('base.group_portal'):
                return False, _('El contacto %s tiene una cuenta interna. No se convierte a Portal.') % partner.display_name
            if user.has_group('logistica_transcash.group_transcash_chofer') or (
                role == 'supplier' and user.has_group('logistica_transcash.group_transcash_cliente')) or (
                role == 'recipient' and user.has_group('logistica_transcash.group_transcash_transportista')):
                return False, _('La cuenta del contacto ya tiene un perfil Portal incompatible; revisar permisos.')
            return user, ''

        # Los logins son globales en la base, no por compañía.
        same_login = Users.search([('login', '=', document)])
        if not same_login:
            # También considerar logins históricos con puntos o guiones.
            self.env.cr.execute(
                "SELECT id FROM res_users WHERE UPPER(REGEXP_REPLACE(COALESCE(login, ''), '[^A-Za-z0-9]', '', 'g')) = %s LIMIT 2",
                (document,))
            ids = [row[0] for row in self.env.cr.fetchall()]
            if ids:
                same_login = Users.browse(ids)
        if same_login:
            return False, _('La identificación %s ya se utiliza como login de otro contacto; no se duplica.') % document

        group = self.env.ref('base.group_portal')
        values = {
            'name': partner.name, 'login': document, 'partner_id': partner.id,
            'password': document, # Solicitud explícita; cambio inmediato requerido.
            'groups_id': [(6, 0, [group.id])], 'active': True,
            'company_id': company.id,
            'company_ids': [(6, 0, [company.id])],
        }
        user = Users.with_context(no_reset_password=True, mail_create_nosubscribe=True,
                                  tracking_disable=True).create(values)
        self.env['tc.portal.password.state'].with_user(SUPERUSER_ID).create({
            'user_id': user.id, 'pending': True,
        })
        _logger.info('Cuenta Portal Transcash preparada: uid=%s perfil=%s compañía=%s',
                     user.id, role, company.id)
        return user, _('Cuenta Portal preparada; contraseña inicial debe modificarse.')

    @api.model
    def _tc_register_pending_access(self, user, company, role):
        """Crear únicamente la entrada administrativa inactiva, sin grupo funcional."""
        if not user:
            return False, ''
        model = 'transcash.acceso.proveedor' if role == 'supplier' else 'transcash.acceso.cliente'
        Directory = self.env[model].with_user(SUPERUSER_ID).with_company(company)
        # El directorio base requiere usuario Portal y contiene unique(usuario_id, company_id).
        entries = Directory.search([('usuario_id', '=', user.id), ('company_id', '=', company.id)])
        if len(entries) > 1:
            return False, _('Accesos duplicados de %s; revisión requerida.') % user.login
        other_model = ('transcash.acceso.cliente' if role == 'supplier'
                       else 'transcash.acceso.proveedor')
        conflicting = self.env[other_model].with_user(SUPERUSER_ID).search([
            ('usuario_id', '=', user.id)], limit=1)
        if conflicting:
            return False, _('El usuario ya figura como otro perfil Portal. Revisión administrativa.')
        if entries:
            return entries[0], ''
        # Si ya tiene el rol (por configuración histórica), el directorio se crea
        # en estado pendiente, nunca autorizar silenciosamente un vínculo nuevo.
        try:
            with self.env.cr.savepoint():
                entry = Directory.create({
                    'usuario_id': user.id, 'company_id': company.id,
                    'activo': False,
                    'observaciones': _('Cuenta creada o localizada durante sincronización ERP. '
                                       'Revisar identidad y habilitar el acceso expresamente.'),
                })
            return entry, ''
        except (ValidationError, UserError, AccessError) as exc:
            _logger.warning('No se creó acceso pendiente Portal: perfil=%s usuario=%s causa=%s',
                            role, user.id, exc)
            return False, _('No se creó acceso pendiente de %s: %s') % (role, exc)

    def _link_master_partners(self):
        result = super()._link_master_partners()
        for guide in self:
            warnings = []
            company = guide.company_id
            for partner, role in ((guide.transport_partner_id, 'supplier'),
                                  (guide.recipient_partner_id, 'recipient')):
                if not partner:
                    continue
                # Un transporte provisto por el propio cliente no es un flete
                # pagadero ni necesita una cuenta de proveedor de liquidaciones.
                name = ' '.join((partner.name or '').upper().split())
                if role == 'supplier' and name in (
                    'TRANSPORTE PROPORCIONADO POR CLIENTE',
                    'TRANSPORTE PROPORCIONADO POR EL CLIENTE',
                ):
                    continue
                # Nunca reutilizar automáticamente una cuenta activa de otro perfil.
                user, note = guide._tc_existing_or_new_user(partner, company, role)
                if note:
                    warnings.append(note)
                if user:
                    entry, entry_note = guide._tc_register_pending_access(user, company, role)
                    if entry_note:
                        warnings.append(entry_note)
            if warnings:
                current = guide.master_link_note or ''
                fresh = '\n'.join(w for w in warnings if w not in current)
                if fresh:
                    guide.sudo().write({
                        'master_link_note': (current + '\n' + fresh).strip()[:4000],
                        'master_link_state': 'pending',
                    })
        return result


class TranscashSupplierActivatePassword(models.Model):
    _inherit = 'transcash.acceso.proveedor'

    def action_activar_acceso(self):
        for rec in self:
            if self.env['tc.portal.password.state'].sudo().search_count([
                    ('user_id', '=', rec.usuario_id.id), ('pending', '=', True)]):
                raise UserError(_('Antes de habilitar al transportista, debe ingresar con su identificación y cambiar la contraseña inicial desde Mi cuenta.'))
        return super().action_activar_acceso()


class TranscashRecipientActivatePassword(models.Model):
    _inherit = 'transcash.acceso.cliente'

    def action_activar_acceso(self):
        for rec in self:
            if self.env['tc.portal.password.state'].sudo().search_count([
                    ('user_id', '=', rec.usuario_id.id), ('pending', '=', True)]):
                raise UserError(_('Antes de habilitar al destinatario, debe ingresar con su identificación y cambiar la contraseña inicial desde Mi cuenta.'))
        return super().action_activar_acceso()
