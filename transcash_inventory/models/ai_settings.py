# -*- coding: utf-8 -*-
"""Transcash-specific IA configuration with explicit, verifiable persistence.

Do not use a broad res.config.settings.set_values() operation here: saving
Transcash must never change settings belonging to other Odoo applications.
All credentials remain in ir.config_parameter (server side) and are never
sent to the dashboard.
"""
from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError
from ..services.ai_client import call_responses, AIServiceError
from ..services.ai_config_store import read_ai_settings, save_ai_settings


PARAM_ENABLED = 'transcash_inventory.ai_enabled'
PARAM_KEY = 'transcash_inventory.ai_api_key'
PARAM_MODEL = 'transcash_inventory.ai_model'
DEFAULT_MODEL = 'gpt-5-mini'


class TranscashAIConfiguration(models.TransientModel):
    _name = 'transcash.inventory.ai.configuration'
    _description = 'Configuración de ChatGPT para Inventario Transcash'
    _transient_max_hours = 1

    ai_enabled = fields.Boolean(string='Activar consultas de ChatGPT')
    ai_model = fields.Char(string='Modelo OpenAI', required=True, default=DEFAULT_MODEL)
    # Write-only UI: intentionally never preload/display a saved API Key.
    api_key_new = fields.Char(string='Nueva API Key', copy=False)
    has_api_key = fields.Boolean(string='API Key guardada', readonly=True)
    remove_api_key = fields.Boolean(string='Eliminar API Key guardada', default=False)

    @api.model
    def default_get(self, field_names):
        vals = super().default_get(field_names)
        if not self.env.user.has_group('base.group_system'):
            raise AccessError(_('Solo el administrador puede configurar ChatGPT.'))
        setting = read_ai_settings(self.env)
        current = {
            'ai_enabled': setting['enabled'],
            'ai_model': setting['model'],
            'has_api_key': bool(setting['key']),
            'api_key_new': False,
            'remove_api_key': False,
        }
        vals.update({name: value for name, value in current.items() if name in field_names})
        return vals

    def _check_admin(self):
        self.ensure_one()
        if not self.env.user.has_group('base.group_system'):
            raise AccessError(_('Solo el administrador puede configurar ChatGPT.'))

    def _persist_configuration(self):
        self._check_admin()
        saved = save_ai_settings(self.env, bool(self.ai_enabled), self.ai_model,
                                 (self.api_key_new or '').strip(), bool(self.remove_api_key))
        self.write({'api_key_new': False, 'has_api_key': bool(saved['key']),
                    'remove_api_key': False})
        return saved['key'], saved['model']

    def _new_form_action(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Configuración de ChatGPT'),
            'res_model': 'transcash.inventory.ai.configuration',
            'view_mode': 'form',
            'views': [(self.env.ref('transcash_inventory.view_transcash_ai_settings').id, 'form')],
            'target': 'current',
            'context': {},  # new transient form fetches fresh persisted values
        }

    def action_save_transcash_ai(self):
        self._persist_configuration()
        return self._new_form_action()

    def action_check_saved_ai(self):
        """Confirm database settings without connecting to OpenAI or exposing secrets."""
        self._check_admin()
        settings = read_ai_settings(self.env)
        enabled = settings['enabled']
        has_key = bool(settings['key'])
        model = settings['model']
        msg = (_('Activación: %s. API Key guardada: %s. Modelo: %s. ') %
               (_('Sí') if enabled else _('No'), _('Sí') if has_key else _('No'), model))
        msg += (_('Puede utilizar el botón Consultar desde el panel.') if enabled and has_key else
                _('Active las consultas e ingrese una API Key; después pulse Guardar configuración.'))
        return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
            'title': _('Estado de configuración guardada'), 'message': msg,
            'type': 'success' if enabled and has_key else 'warning', 'sticky': True}}

    def action_test_transcash_ai(self):
        key, model = self._persist_configuration()
        if not self.ai_enabled:
            return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
                'title': _('Configuración guardada'),
                'message': _('La configuración se guardó, pero las consultas de IA están desactivadas.'),
                'type': 'warning', 'sticky': True}}
        try:
            answer = call_responses(key, model,
                'Responde únicamente: CONEXION OK',
                'Confirma la conexión de OpenAI.', max_tokens=350)
        except AIServiceError as exc:
            # A failing external test must NOT roll back a successfully saved key.
            return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
                'title': _('Configuración guardada; prueba fallida'),
                'message': str(exc), 'type': 'danger', 'sticky': True}}
        return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
            'title': _('Conexión OpenAI correcta'),
            'message': _('Configuración guardada. Respuesta: %s') % answer[:120],
            'type': 'success', 'sticky': False}}
