# -*- coding: utf-8 -*-
"""Fuente única de los parámetros de la integración OpenAI.

Las lecturas de verificación van a la tabla real, evitando confundir un
valor cacheado por un worker con el valor persistido en Odoo.
El servicio NO envía secretos a las respuestas HTTP.
"""
from odoo.exceptions import UserError

P_ENABLED = 'transcash_inventory.ai_enabled'
P_KEY = 'transcash_inventory.ai_api_key'
P_MODEL = 'transcash_inventory.ai_model'
KEYS = (P_ENABLED, P_KEY, P_MODEL)
DEFAULT_MODEL = 'gpt-5-mini'


def read_ai_settings(env):
    """Solo uso del servidor; el diccionario incluye el secreto."""
    # En Odoo 18, los cambios ORM se reflejan en SQL tras un flush.
    env['ir.config_parameter'].sudo().flush_model(['key', 'value'])
    env.cr.execute('SELECT key, value FROM ir_config_parameter WHERE key IN %s', (KEYS,))
    values = dict(env.cr.fetchall())
    enabled = (values.get(P_ENABLED) or '').strip().lower() in ('1', 'true', 'yes', 'on')
    return {'enabled': enabled, 'key': (values.get(P_KEY) or '').strip(),
            'model': (values.get(P_MODEL) or DEFAULT_MODEL).strip() or DEFAULT_MODEL}


def public_ai_settings(data):
    return {'enabled': bool(data['enabled']), 'key_saved': bool(data['key']),
            'model': data['model'],
            'ready': bool(data['enabled'] and data['key'] and data['model'])}


def save_ai_settings(env, enabled, model, new_key='', clear_key=False):
    """Valida antes de escribir; conserva la clave anterior si el campo llega vacío."""
    model = (model or '').strip()
    new_key = (new_key or '').strip()
    if not model or len(model) > 100 or any(ch.isspace() for ch in model):
        raise UserError('El modelo de OpenAI es obligatorio y no debe contener espacios.')
    if new_key and (not new_key.startswith('sk-') or len(new_key) < 15 or len(new_key) > 1024):
        raise UserError('La API Key no tiene el formato esperado (sk-...).')
    if clear_key and new_key:
        raise UserError('No se puede eliminar y reemplazar la clave en una sola operación.')
    previous = read_ai_settings(env)
    desired_key = '' if clear_key else (new_key or previous['key'])
    if enabled and not desired_key:
        raise UserError('Ingrese la API Key antes de activar ChatGPT.')
    params = env['ir.config_parameter'].sudo()
    if clear_key:
        params.set_param(P_KEY, '')
    elif new_key:
        params.set_param(P_KEY, new_key)
    params.set_param(P_MODEL, model)
    params.set_param(P_ENABLED, 'True' if enabled else 'False')
    current = read_ai_settings(env)
    if (current['enabled'] != enabled or current['model'] != model or
            current['key'] != desired_key):
        raise UserError('Odoo no pudo confirmar el guardado. Revise permisos y logs.')
    return current
