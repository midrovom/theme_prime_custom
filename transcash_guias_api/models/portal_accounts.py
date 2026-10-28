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
        # El alta AUTOMATICA no debe pasar por el permiso interactivo de
        # Contabilidad, que solo se exige para habilitar o revocar acceso.
        # Esta autorización técnica se limita al contexto + sudo y a fichas
        # pendientes: jamás se añade un grupo de proveedor aquí.
        Directory = (self.env[model].sudo().with_company(company)
                     .with_context(tc_portal_prepare_pending=True))
        self.env.cr.execute(
            'SELECT pg_advisory_xact_lock(hashtext(%s), hashtext(%s))',
            ('tc.portal.pending.access', '%s:%s:%s' % (model, user.id, company.id)))
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
    _order = 'activo asc, id desc'  # Pendientes primero; no se ocultan los habilitados.

    @api.model_create_multi
    def create(self, vals_list):
        if self.env.su and self.env.context.get('tc_portal_prepare_pending'):
            # El create() original exige pertenecer al grupo de Contabilidad Y
            # a la compañía. El importador técnico no debe necesitar esos
            # permisos: salta solo esa capa interactiva al crear solicitudes
            # pendientes. La validación del usuario Portal se conserva.
            allowed = {'usuario_id', 'company_id', 'activo', 'observaciones'}
            for vals in vals_list:
                if set(vals) - allowed or vals.get('activo') is not False or (
                        not vals.get('usuario_id') or not vals.get('company_id')):
                    raise AccessError(_('El importador solo puede preparar accesos Portal inactivos.'))
            records = models.Model.create(self, vals_list)
            records._check_portal_user()
            return records
        return super().create(vals_list)

    @api.model
    def _tc_reconcile_existing_supplier_accounts(self):
        """Reconstruye solicitudes ausentes para cuentas Portal ya creadas.

        Solo cruza transportistas de guías ERP y usuarios Portal vinculados
        al MISMO contacto; no añade todos los portales de la compañía ni
        reclasifica choferes, destinatarios o transportes del propio cliente.
        """
        operator = self.env.user
        if not self.env.su and (operator.share or not operator.has_group(
                'logistica_transcash.group_transcash_contabilidad')):
            raise AccessError(_('Solo Contabilidad puede actualizar los accesos de proveedores.'))
        company_ids = (self.env['res.company'].sudo().search([]).ids if self.env.su
                       else operator.company_ids.ids)
        if not company_ids:
            return {'reviewed': 0, 'created': 0, 'skipped': 0}
        grouped = self.env['tc.guide'].sudo().read_group(
            [('transport_partner_id', '!=', False), ('company_id', 'in', company_ids)],
            ['transport_partner_id', 'company_id'],
            ['transport_partner_id', 'company_id'], lazy=False)
        pairs = set()
        for item in grouped:
            partner = item.get('transport_partner_id')
            company = item.get('company_id')
            if partner and company:
                pairs.add((partner[0], company[0]))
        if not pairs:
            return {'reviewed': 0, 'created': 0, 'skipped': 0}
        partner_ids = list({partner_id for partner_id, _ in pairs})
        partners = {p.id: p for p in self.env['res.partner'].sudo().with_context(
            active_test=False).browse(partner_ids)}
        users = self.env['res.users'].sudo().with_context(active_test=False).search([
            ('partner_id', 'in', partner_ids), ('share', '=', True)])
        by_partner = {}
        for user in users:
            by_partner.setdefault(user.partner_id.id, []).append(user)
        created = reviewed = skipped = 0
        for partner_id, company_id in sorted(pairs):
            partner = partners.get(partner_id)
            linked = by_partner.get(partner_id) or []
            if not partner or not partner.active or len(linked) != 1:
                skipped += 1
                continue
            name = ' '.join((partner.name or '').upper().split())
            if name in ('TRANSPORTE PROPORCIONADO POR CLIENTE',
                        'TRANSPORTE PROPORCIONADO POR EL CLIENTE'):
                skipped += 1
                continue
            user = linked[0]
            if not user.active or not user.has_group('base.group_portal') or any(
                    user.has_group('logistica_transcash.%s' % g)
                    for g in ('group_transcash_chofer', 'group_transcash_cliente')):
                skipped += 1
                continue
            company = self.env['res.company'].sudo().browse(company_id)
            with self.env.cr.savepoint():
                directory = self.sudo().with_company(company)
                existing = directory.search([
                    ('usuario_id', '=', user.id), ('company_id', '=', company.id)], limit=1)
                entry, reason = self.env['tc.guide'].sudo()._tc_register_pending_access(
                    user, company, 'supplier')
                if reason:
                    _logger.warning('Pendiente proveedor no creado para uid=%s: %s',
                                    user.id, reason)
                    skipped += 1
                elif entry:
                    reviewed += 1
                    if not existing:
                        created += 1
        return {'reviewed': reviewed, 'created': created, 'skipped': skipped}

    @api.model
    def action_tc_refresh_supplier_accesses(self):
        # Ejecutable por Contabilidad desde el menú de la misma bandeja.
        result = self._tc_reconcile_existing_supplier_accounts()
        _logger.info('Revisión de proveedores Portal: %s', result)
        action = self.env.ref('logistica_transcash.action_transcash_acceso_proveedores').read()[0]
        action['context'] = {'search_default_tc_pendientes_proveedor_v230': 1}
        return action

    def action_activar_acceso(self):
        for rec in self:
            if self.env['tc.portal.password.state'].sudo().search_count([
                    ('user_id', '=', rec.usuario_id.id), ('pending', '=', True)]):
                raise UserError(_('Antes de habilitar al transportista, debe ingresar con su identificación y cambiar la contraseña inicial desde Mi cuenta.'))
        return super().action_activar_acceso()


class TranscashRecipientActivatePassword(models.Model):
    _inherit = 'transcash.acceso.cliente'

    @api.model_create_multi
    def create(self, vals_list):
        if self.env.su and self.env.context.get('tc_portal_prepare_pending'):
            allowed = {'usuario_id', 'company_id', 'activo', 'observaciones'}
            for vals in vals_list:
                if set(vals) - allowed or vals.get('activo') is not False or (
                        not vals.get('usuario_id') or not vals.get('company_id')):
                    raise AccessError(_('El importador solo puede preparar accesos Portal inactivos.'))
            records = models.Model.create(self, vals_list)
            records._check_portal_user()
            return records
        return super().create(vals_list)

    def action_activar_acceso(self):
        for rec in self:
            if self.env['tc.portal.password.state'].sudo().search_count([
                    ('user_id', '=', rec.usuario_id.id), ('pending', '=', True)]):
                raise UserError(_('Antes de habilitar al destinatario, debe ingresar con su identificación y cambiar la contraseña inicial desde Mi cuenta.'))
        return super().action_activar_acceso()
