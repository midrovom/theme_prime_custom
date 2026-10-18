"""Control explícito de perfiles Portal para clientes y transportistas.

Las cuentas Portal se invitan con la herramienta nativa de Odoo, desde Contactos.
Este directorio SOLO habilita/revoca el perfil funcional Transcash, sin crear
contraseñas y sin conferir derechos de acceso al backoffice.
"""
from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


class TranscashAccesoPortalBase(models.AbstractModel):
    _name = 'transcash.acceso.portal.base'
    _description = 'Acceso Portal Transcash (base)'

    usuario_id = fields.Many2one(
        'res.users', string='Usuario Portal', required=True, ondelete='restrict',
        domain=[('share', '=', True)], index=True,
        help='Debe existir primero como usuario Portal de Odoo, vinculado al contacto correcto.')
    contacto_id = fields.Many2one(
        'res.partner', string='Contacto vinculado', related='usuario_id.partner_id', readonly=True)
    empresa_contacto_id = fields.Many2one(
        'res.partner', string='Empresa / cliente principal',
        related='usuario_id.partner_id.commercial_partner_id', readonly=True)
    correo = fields.Char(related='usuario_id.login', string='Correo de acceso', readonly=True)
    company_id = fields.Many2one('res.company', string='Compañía autorizada',
                                 required=True, default=lambda self: self.env.company, index=True)
    activo = fields.Boolean(string='Permiso vigente en esta compañía', default=False, copy=False)
    acceso_habilitado = fields.Boolean(string='Perfil PWA habilitado',
                                       compute='_compute_acceso_habilitado')
    observaciones = fields.Text(string='Notas administrativas')

    @api.depends('usuario_id', 'usuario_id.groups_id', 'activo')
    def _compute_acceso_habilitado(self):
        grupo = self.env.ref(self._perfil_group_xmlid(), raise_if_not_found=False)
        for rec in self:
            rec.acceso_habilitado = bool(rec.activo and grupo and rec.usuario_id and
                                        grupo in rec.usuario_id.sudo().groups_id)

    def _perfil_group_xmlid(self):
        raise NotImplementedError()

    def _administrador_group_xmlid(self):
        raise NotImplementedError()

    def _check_administrator(self):
        user = self.env.user
        if user.share or not user.has_group(self._administrador_group_xmlid()):
            raise AccessError(_('No tiene permiso para administrar este tipo de acceso Portal.'))
        for rec in self:
            if rec.company_id and rec.company_id not in user.company_ids:
                raise AccessError(_('Solo puede administrar accesos de sus compañías autorizadas.'))

    @api.model_create_multi
    def create(self, vals_list):
        self._check_administrator()
        for vals in vals_list:
            company_id = int(vals.get('company_id') or self.env.company.id)
            if company_id not in self.env.user.company_ids.ids:
                raise AccessError(_('No puede registrar usuarios de una compañía no autorizada.'))
        records = super().create(vals_list)
        records._check_administrator()
        return records

    def write(self, vals):
        self._check_administrator()
        if 'company_id' in vals and vals['company_id'] not in self.env.user.company_ids.ids:
            raise AccessError(_('No puede trasladar accesos a una compañía no autorizada.'))
        if 'usuario_id' in vals or 'company_id' in vals:
            raise AccessError(_('No cambie el usuario o la compañía de un acceso existente; registre uno nuevo.'))
        # La habilitación/deshabilitación se hace exclusivamente con las acciones
        # auditadas, nunca editando una casilla en masa.
        if 'activo' in vals and not self.env.context.get('transcash_change_portal_state'):
            raise AccessError(_('Utilice los botones Habilitar acceso / Deshabilitar acceso.'))
        return super().write(vals)

    def unlink(self):
        raise UserError(_('Los accesos Portal no se borran: deshabilítelos para conservar la bitácora.'))

    @api.constrains('usuario_id')
    def _check_portal_user(self):
        for rec in self:
            if not rec.usuario_id or not rec.usuario_id.has_group('base.group_portal') or not rec.usuario_id.share:
                raise ValidationError(_('El usuario debe tener tipo Portal de Odoo, no ser interno ni público.'))
            if not rec.usuario_id.partner_id:
                raise ValidationError(_('El usuario Portal debe estar vinculado a un contacto.'))

    def _check_other_roles(self):
        prohibited = ('group_transcash_chofer', 'group_transcash_cliente',
                      'group_transcash_transportista')
        own = self._perfil_group_xmlid().split('.')[-1]
        for rec in self:
            for role in prohibited:
                if role != own and rec.usuario_id.has_group('logistica_transcash.' + role):
                    raise UserError(_(
                        'La cuenta %s ya tiene otro perfil Portal Transcash (%s). '
                        'Utilice usuarios distintos para cliente, chofer y transportista.') %
                        (rec.usuario_id.login, role.replace('group_transcash_', '')))

    def action_activar_acceso(self):
        self._check_administrator()
        group = self.env.ref(self._perfil_group_xmlid())
        for rec in self:
            rec._check_portal_user()
            rec._check_other_roles()
            rec.with_context(transcash_change_portal_state=True).write({'activo': True})
            rec.usuario_id.sudo().write({'groups_id': [(4, group.id)]})
            rec.message_post(body=_('Acceso a Transcash habilitado por %s para %s.') %
                             (self.env.user.name, rec.company_id.name))
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def action_desactivar_acceso(self):
        self._check_administrator()
        group = self.env.ref(self._perfil_group_xmlid())
        for rec in self:
            rec.with_context(transcash_change_portal_state=True).write({'activo': False})
            # El grupo es global a res.users; no se retira mientras otro registro
            # de la misma clase conserve un acceso activo en otra compañía.
            other_active = self.sudo().search_count([
                ('usuario_id', '=', rec.usuario_id.id), ('activo', '=', True),
                ('id', '!=', rec.id)])
            if not other_active:
                rec.usuario_id.sudo().write({'groups_id': [(3, group.id)]})
            rec.message_post(body=_('Acceso a Transcash deshabilitado por %s para %s.') %
                             (self.env.user.name, rec.company_id.name))
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def action_ver_contacto(self):
        self.ensure_one()
        self._check_administrator()
        return {'type': 'ir.actions.act_window', 'name': _('Contacto Portal'),
                'res_model': 'res.partner', 'res_id': self.contacto_id.id,
                'view_mode': 'form', 'target': 'current'}

    @api.model
    def _allowed_companies_for(self, user):
        """IDs autorizados, [] si todo fue revocado, None si es cuenta heredada.

        La ausencia de registros conserva compatibilidad para usuarios existentes
        que recibieron su grupo manualmente antes de la V5.28.
        """
        access = self.sudo().search([('usuario_id', '=', user.id)])
        return access.filtered('activo').mapped('company_id').ids if access else None


class TranscashAccesoCliente(models.Model):
    _name = 'transcash.acceso.cliente'
    _inherit = ['transcash.acceso.portal.base', 'mail.thread']
    _description = 'Clientes con acceso a la PWA Transcash'
    _rec_name = 'usuario_id'
    _order = 'id desc'

    _sql_constraints = [
        ('usuario_company_unique', 'unique(usuario_id, company_id)',
         'El usuario ya está registrado para esta compañía como Cliente.'),
    ]

    def _perfil_group_xmlid(self):
        return 'logistica_transcash.group_transcash_cliente'

    def _administrador_group_xmlid(self):
        return 'logistica_transcash.group_logistica_manager'

    def action_ver_guias(self):
        self.ensure_one()
        self._check_administrator()
        partner = self.empresa_contacto_id
        return {'type': 'ir.actions.act_window', 'name': _('Guías del cliente'),
                'res_model': 'transcash.guia', 'view_mode': 'list,form',
                'domain': [('destinatario_id', 'child_of', partner.id),
                           ('company_id', '=', self.company_id.id)],
                'context': {'create': False, 'edit': False, 'delete': False}}


class TranscashAccesoProveedor(models.Model):
    _name = 'transcash.acceso.proveedor'
    _inherit = ['transcash.acceso.portal.base', 'mail.thread']
    _description = 'Proveedores transportistas con acceso a la PWA'
    _rec_name = 'usuario_id'
    _order = 'id desc'

    _sql_constraints = [
        ('usuario_company_unique', 'unique(usuario_id, company_id)',
         'El usuario ya está registrado para esta compañía como Proveedor.'),
    ]

    def _perfil_group_xmlid(self):
        return 'logistica_transcash.group_transcash_transportista'

    def _administrador_group_xmlid(self):
        return 'logistica_transcash.group_transcash_contabilidad'

    def action_ver_viajes(self):
        self.ensure_one()
        self._check_administrator()
        return {'type': 'ir.actions.act_window', 'name': _('Viajes del proveedor'),
                'res_model': 'transcash.embarque', 'view_mode': 'list,form',
                'domain': [('proveedor_id.commercial_partner_id', '=', self.empresa_contacto_id.id),
                           ('company_id', '=', self.company_id.id)],
                'context': {'create': False, 'edit': False, 'delete': False}}

    def action_ver_liquidaciones(self):
        self.ensure_one()
        self._check_administrator()
        return {'type': 'ir.actions.act_window', 'name': _('Liquidaciones del proveedor'),
                'res_model': 'transcash.pago.liquidacion', 'view_mode': 'list,form',
                'domain': [('proveedor_id.commercial_partner_id', '=', self.empresa_contacto_id.id),
                           ('company_id', '=', self.company_id.id)],
                'context': {'create': False, 'edit': False, 'delete': False}}
