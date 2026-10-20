# -*- coding: utf-8 -*-
from odoo import fields, models, _
from odoo.exceptions import AccessError, UserError
from ..services.ai_client import call_responses, AIServiceError


class TranscashAISettings(models.TransientModel):
    _inherit = 'res.config.settings'

    transcash_ai_enabled = fields.Boolean(string='Activar consultas de IA',
        config_parameter='transcash_inventory.ai_enabled')
    transcash_ai_api_key = fields.Char(string='API Key de OpenAI',
        config_parameter='transcash_inventory.ai_api_key', groups='base.group_system', copy=False)
    transcash_ai_model = fields.Char(string='Modelo de OpenAI',
        config_parameter='transcash_inventory.ai_model', default='gpt-5-mini')

    def action_save_transcash_ai(self):
        self.ensure_one()
        if not self.env.user.has_group('base.group_system'):
            raise AccessError(_('Solo el administrador puede guardar la API Key.'))
        self.set_values()
        return {'type': 'ir.actions.act_window', 'name': 'Configuración de ChatGPT',
                'res_model': 'res.config.settings', 'view_mode': 'form',
                'views': [(self.env.ref('transcash_inventory.view_transcash_ai_settings').id, 'form')],
                'target': 'current'}

    def action_test_transcash_ai(self):
        self.ensure_one()
        if not self.env.user.has_group('base.group_system'):
            raise AccessError(_('Solo el administrador puede probar la conexión.'))
        self.set_values()
        params = self.env['ir.config_parameter'].sudo()
        key = (params.get_param('transcash_inventory.ai_api_key') or '').strip()
        model = (params.get_param('transcash_inventory.ai_model') or 'gpt-5-mini').strip()
        try:
            answer = call_responses(key, model, 'Responde únicamente: CONEXION OK',
                                    'Confirma la conexión con la API de OpenAI.', max_tokens=50)
        except AIServiceError as exc:
            raise UserError(str(exc)) from None
        return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
            'title': 'Conexión OpenAI', 'message': answer[:150], 'type': 'success', 'sticky': False}}
