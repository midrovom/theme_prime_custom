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
        params = self.env['ir.config_parameter'].sudo()
        current = {
            'ai_enabled': params.get_param(PARAM_ENABLED, 'False') in ('True', 'true', '1'),
            'ai_model': (params.get_param(PARAM_MODEL) or DEFAULT_MODEL).strip(),
            'has_api_key': bool((params.get_param(PARAM_KEY) or '').strip()),
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
        params = self.env['ir.config_parameter'].sudo()
        key = (self.api_key_new or '').strip()
        model = (self.ai_model or '').strip()
        if not model or len(model) > 100 or any(ch.isspace() for ch in model):
            raise UserError(_('Indique un modelo de OpenAI válido, sin espacios.'))
        if self.remove_api_key and key:
            raise UserError(_('Para reemplazar la API Key, desmarque «Eliminar API Key guardada».'))
        if key and (len(key) < 15 or not key.startswith('sk-')):
            raise UserError(_('La API Key no tiene el formato esperado (sk-...).'))
        old_key = (params.get_param(PARAM_KEY) or '').strip()
        next_key = '' if self.remove_api_key else (key or old_key)
        if self.ai_enabled and not next_key:
            raise UserError(_('Ingrese una API Key y guarde antes de activar las consultas.'))

        # Do not overwrite an existing key with a blank edit field.
        if self.remove_api_key:
            params.set_param(PARAM_KEY, '')
        elif key:
            params.set_param(PARAM_KEY, key)
        params.set_param(PARAM_MODEL, model)
        params.set_param(PARAM_ENABLED, 'True' if self.ai_enabled else 'False')

        # Read-after-write assertion catches integration/config regressions.
        if (params.get_param(PARAM_ENABLED) != ('True' if self.ai_enabled else 'False') or
                params.get_param(PARAM_MODEL) != model or
                (params.get_param(PARAM_KEY) or '').strip() != next_key):
            raise UserError(_('La configuración no se pudo verificar después de guardarla. Revise el log de Odoo.'))

        # Minimize persistence of the submitted secret in the transient wizard.
        self.write({'api_key_new': False, 'has_api_key': bool(next_key), 'remove_api_key': False})
        return next_key, model

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
        params = self.env['ir.config_parameter'].sudo()
        enabled = (params.get_param(PARAM_ENABLED) or '').strip().lower() in ('true', '1', 'yes', 'on')
        has_key = bool((params.get_param(PARAM_KEY) or '').strip())
        model = (params.get_param(PARAM_MODEL) or DEFAULT_MODEL).strip()
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
