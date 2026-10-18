"""Bitácora de discrepancias PRE-SALIDA. Nunca se publica al destinatario."""
from odoo import api, fields, models, _
from odoo.exceptions import AccessError


class ObjecionEmbarque(models.Model):
    _name = 'transcash.embarque.objecion'
    _description = 'Incidencia interna de aceptación de carga'
    _order = 'fecha desc, id desc'

    embarque_id = fields.Many2one('transcash.embarque', required=True, index=True, readonly=True, ondelete='restrict')
    company_id = fields.Many2one('res.company', related='embarque_id.company_id', store=True, readonly=True)
    chofer_id = fields.Many2one('res.users', string='Chofer que objetó', readonly=True, required=True)
    fecha = fields.Datetime('Fecha de objeción', readonly=True, required=True, default=fields.Datetime.now)
    motivo = fields.Text('Explicación del chofer', readonly=True, required=True)
    estado = fields.Selection([('abierta','Abierta'),('resuelta','Resuelta por Logística')], required=True,
                               default='abierta', readonly=True)
    responsable_id = fields.Many2one('res.users', 'Responsable de corrección', readonly=True)
    fecha_resolucion = fields.Datetime('Fecha de corrección', readonly=True)
    explicacion_resolucion = fields.Text('Acción correctiva', readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su:
            raise AccessError(_('Las objeciones se crean exclusivamente desde el flujo de aceptación.'))
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.su:
            raise AccessError(_('El historial de objeciones no se edita manualmente.'))
        return super().write(vals)

    def unlink(self):
        raise AccessError(_('No se elimina el historial de objeciones de embarque.'))


class ResolverObjecionWizard(models.TransientModel):
    _name = 'transcash.resolver.objecion.wizard'
    _description = 'Explicación de corrección de carga'

    embarque_id = fields.Many2one('transcash.embarque', required=True, readonly=True)
    solucion = fields.Text('Qué se corrigió', required=True)

    def action_confirm(self):
        self.ensure_one()
        self.embarque_id.action_resolve_discrepancy(self.solucion)
        return {'type':'ir.actions.act_window_close'}
