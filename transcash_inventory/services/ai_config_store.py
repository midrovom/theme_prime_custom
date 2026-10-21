# -*- coding: utf-8 -*-
"""Company-specific OpenAI settings.  No secrets are sent to the web client.

Legacy global values are migrated only when there is exactly ONE company with
snapshots, preventing a company added later from inheriting another company's
API key or activation flag.
"""
from odoo.exceptions import UserError

P_ENABLED = 'transcash_inventory.ai_enabled'
P_KEY = 'transcash_inventory.ai_api_key'
P_MODEL = 'transcash_inventory.ai_model'
DEFAULT_MODEL = 'gpt-5-mini'


def _company_keys(env):
    cid = env.company.id
    return (f'{P_ENABLED}.company_{cid}', f'{P_KEY}.company_{cid}',
            f'{P_MODEL}.company_{cid}')


def _get_persisted(env, keys):
    params = env['ir.config_parameter'].sudo()
    params.flush_model(['key', 'value'])
    env.cr.execute('SELECT key, value FROM ir_config_parameter WHERE key IN %s',
                   (tuple(keys),))
    return dict(env.cr.fetchall())


def _legacy_migration(env, keys, current):
    """Keep the pre-1.28 deployment configured, but never clone it to peers."""
    if any(k in current for k in keys):
        return current
    env.cr.execute('SELECT DISTINCT company_id FROM transcash_inventory_snapshot LIMIT 2')
    owners = [c for (c,) in env.cr.fetchall()]
    if owners != [env.company.id]:
        return current
    old = _get_persisted(env, (P_ENABLED, P_KEY, P_MODEL))
    if not any(old.get(k) for k in (P_ENABLED, P_KEY, P_MODEL)):
        return current
    params = env['ir.config_parameter'].sudo()
    for new, old_key in zip(keys, (P_ENABLED, P_KEY, P_MODEL)):
        params.set_param(new, old.get(old_key, ''))
    return _get_persisted(env, keys)


def read_ai_settings(env):
    """Server side ONLY; `key` must never be serialized to the browser."""
    keys = _company_keys(env)
    values = _get_persisted(env, keys)
    if not values:
        values = _legacy_migration(env, keys, values)
    enabled = (values.get(keys[0]) or '').strip().lower() in ('1','true','yes','on')
    return {'enabled': enabled, 'key': (values.get(keys[1]) or '').strip(),
            'model': (values.get(keys[2]) or DEFAULT_MODEL).strip() or DEFAULT_MODEL}


def public_ai_settings(data):
    return {'enabled': bool(data['enabled']), 'key_saved': bool(data['key']),
            'model': data['model'],
            'ready': bool(data['enabled'] and data['key'] and data['model'])}


def save_ai_settings(env, enabled, model, new_key='', clear_key=False):
    model = (model or '').strip()
    new_key = (new_key or '').strip()
    if not model or len(model) > 100 or any(c.isspace() for c in model):
        raise UserError('El modelo de OpenAI es obligatorio y no debe contener espacios.')
    if new_key and (not new_key.startswith('sk-') or len(new_key) < 15 or len(new_key) > 1024):
        raise UserError('La API Key no tiene el formato esperado (sk-...).')
    if clear_key and new_key:
        raise UserError('No se puede eliminar y reemplazar la clave en una sola operación.')
    previous = read_ai_settings(env)
    desired_key = '' if clear_key else (new_key or previous['key'])
    if enabled and not desired_key:
        raise UserError('Ingrese la API Key antes de activar ChatGPT.')
    keys = _company_keys(env)
    params = env['ir.config_parameter'].sudo()
    params.set_param(keys[1], desired_key)
    params.set_param(keys[2], model)
    params.set_param(keys[0], 'True' if enabled else 'False')
    current = read_ai_settings(env)
    if (current['enabled'] != bool(enabled) or current['model'] != model or
            current['key'] != desired_key):
        raise UserError('Odoo no pudo confirmar el guardado para la empresa seleccionada.')
    return current
