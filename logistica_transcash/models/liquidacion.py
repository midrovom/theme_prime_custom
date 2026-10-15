"""Safe finance-only wizard; no operational guide write access for accounting."""
from odoo import fields, models, _
from odoo.exceptions import UserError


class LiquidacionWizard(models.TransientModel):
    _name = 'transcash.liquidacion.wizard'
    _description = 'Configurar tarifa y cuenta de liquidación'

    guia_id = fields.Many2one('transcash.guia', required=True, readonly=True)
    cuenta_gasto_id = fields.Many2one('account.account', required=True,
                                     domain="[('account_type','in',['expense','expense_direct_cost'])]")
    valor_acordado = fields.Float(required=True, digits=(16, 2))

    def action_confirm(self):
        self.ensure_one()
        user = self.env.user
        if not user.has_group('logistica_transcash.group_transcash_contabilidad'):
            raise UserError(_('Solo Contabilidad puede editar parámetros de liquidación.'))
        guia = self.guia_id
        if guia.embarque_id:
            raise UserError(_('El costo de esta guía se liquida por embarque.'))
        if guia.company_id not in user.company_ids or guia.state not in ('entregada','lista_pago') or guia.factura_id:
            raise UserError(_('La guía no está habilitada para configurar su pago.'))
        if self.valor_acordado <= 0:
            raise UserError(_('El valor de flete debe ser positivo.'))
        if self.cuenta_gasto_id.account_type not in ('expense', 'expense_direct_cost'):
            raise UserError(_('Seleccione una cuenta contable de gasto.'))
        # Odoo accounting usually allows account.company_ids in modern versions;
        # company on guide must belong to the allowed accounting company set.
        if 'company_ids' in self.cuenta_gasto_id._fields and guia.company_id not in self.cuenta_gasto_id.company_ids:
            raise UserError(_('La cuenta no pertenece a la compañía de la guía.'))
        guia.sudo().write({'cuenta_gasto_id':self.cuenta_gasto_id.id,
                           'valor_acordado':self.valor_acordado})
        guia._track_event('Tarifa y cuenta de liquidación configuradas',
                          'Cuenta %s' % self.cuenta_gasto_id.code, publico_cliente=False)
        return {'type':'ir.actions.act_window_close'}
