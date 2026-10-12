from odoo import fields, models, _
from odoo.exceptions import UserError


class TranscashObjectWizard(models.TransientModel):
    _name = 'transcash.object.wizard'
    _description = 'Objetar evidencia de carga'

    evidencia_id = fields.Many2one('transcash.evidencia', string='Evidencia', required=True, readonly=True)
    motivo = fields.Text('Motivo de objeción', required=True)

    def action_confirm(self):
        self.ensure_one()
        if not self.evidencia_id:
            raise UserError(_('No seleccionó evidencia.'))
        self.evidencia_id.object_evidence(self.motivo)
        return {'type': 'ir.actions.act_window_close'}
