"""Driver directory and explicit activation of existing portal accounts.

Drivers are external portal users, not Odoo backoffice users. No credentials are
created here: the normal Contacts > Grant Portal Access invitation is used.
"""
from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError, UserError


class TranscashChofer(models.Model):
    _name = 'transcash.chofer'
    _description = 'Chofer habilitado para Transcash'
    _rec_name = 'usuario_id'
    _order = 'id desc'

    usuario_id = fields.Many2one(
        'res.users', string='Usuario de portal', required=True, ondelete='restrict',
        domain=[('share', '=', True)],
        help='Primero cree el contacto y otórguele acceso Portal. Luego seleccione aquí la cuenta.')
    nombre = fields.Char(related='usuario_id.name', string='Chofer', readonly=True)
    correo = fields.Char(related='usuario_id.login', string='Inicio de sesión', readonly=True)
    telefono = fields.Char(related='usuario_id.partner_id.mobile', string='Celular', readonly=True)
    empresa_transporte_id = fields.Many2one('res.partner', string='Empresa de transporte',
                                            domain=[('is_company', '=', True)])
    company_id = fields.Many2one('res.company', string='Compañía', required=True,
                                 default=lambda self: self.env.company)
    activo = fields.Boolean(default=True, string='Registro activo')
    carga_autonoma = fields.Boolean(
        string='Permitir finalizar carga sin aprobación previa de bodega',
        default=False, copy=False,
        help='Permite cerrar la carga de guías asignadas aunque sus evidencias estén pendientes. '
             'Exige evidencia de carga y no permite cerrar evidencias objetadas. '
             'No autoriza la salida del vehículo.')
    acceso_activado = fields.Boolean(string='Acceso chofer habilitado', compute='_compute_acceso_activado')

    _sql_constraints = [
        ('unique_usuario_chofer', 'unique(usuario_id)',
         'La cuenta de portal ya está registrada como chofer.')
    ]

    @api.depends('usuario_id', 'usuario_id.groups_id')
    def _compute_acceso_activado(self):
        group = self.env.ref('logistica_transcash.group_transcash_chofer', raise_if_not_found=False)
        for rec in self:
            rec.acceso_activado = bool(group and rec.usuario_id and
                                      group in rec.usuario_id.sudo().groups_id)

    @api.model_create_multi
    def create(self, vals_list):
        if any(vals.get('carga_autonoma') for vals in vals_list) and not self.env.user.has_group('logistica_transcash.group_logistica_manager'):
            raise AccessError(_('Solo Administración de logística puede habilitar la carga autónoma.'))
        return super().create(vals_list)

    @api.constrains('usuario_id')
    def _check_portal(self):
        for rec in self:
            if rec.usuario_id and not rec.usuario_id.has_group('base.group_portal'):
                raise ValidationError(_(
                    'El chofer debe ser una cuenta Portal. Abra Contactos, otorgue acceso al portal '
                    'al conductor y seleccione ese usuario. No utilice una cuenta interna ni pública.'))

    def action_activar_acceso(self):
        if not self.env.user.has_group('logistica_transcash.group_logistica_manager'):
            raise AccessError(_('Solo Administración de logística puede habilitar choferes.'))
        group = self.env.ref('logistica_transcash.group_transcash_chofer')
        for rec in self:
            if not rec.activo:
                raise UserError(_('Active primero el registro del chofer.'))
            if not rec.usuario_id.has_group('base.group_portal'):
                raise UserError(_('La cuenta seleccionada no es un usuario Portal.'))
            rec.usuario_id.sudo().write({'groups_id': [(4, group.id)]})
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def action_desactivar_acceso(self):
        if not self.env.user.has_group('logistica_transcash.group_logistica_manager'):
            raise AccessError(_('Solo Administración de logística puede deshabilitar choferes.'))
        group = self.env.ref('logistica_transcash.group_transcash_chofer')
        for rec in self:
            rec.usuario_id.sudo().write({'groups_id': [(3, group.id)]})
            rec.activo = False
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def write(self, vals):
        if 'carga_autonoma' in vals and not self.env.user.has_group('logistica_transcash.group_logistica_manager'):
            raise AccessError(_('Solo Administración de logística puede habilitar la carga autónoma.'))
        # Al desactivar desde la casilla también se revoca efectivamente el grupo.
        result = super().write(vals)
        if vals.get('activo') is False:
            group = self.env.ref('logistica_transcash.group_transcash_chofer')
            for rec in self:
                rec.usuario_id.sudo().write({'groups_id': [(3, group.id)]})
        return result

    def action_abrir_webapp(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_url', 'url': '/transcash/guias', 'target': 'new'}
