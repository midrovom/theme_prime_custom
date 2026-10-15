"""Integration settings intended for Logistica administrators, not Portal users.

The integration does not expose or replicate credentials in the webapp.
"""
import json
import secrets
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError


class TranscashAPIWizard(models.TransientModel):
    _name = 'transcash.api.wizard'
    _description = 'Configuración de integración ERP Transcash'

    api_url = fields.Char('URL HTTPS para consultar guías (GET)')
    api_outbound_token = fields.Char('Token para consultar al ERP')
    api_inbound_token = fields.Char('Token para recibir guías desde ERP')
    credit_api_url = fields.Char('URL para solicitar notas de crédito (POST)')
    sync_active = fields.Boolean('Sincronización automática activada', default=True)
    interval_minutes = fields.Integer('Frecuencia (minutos)', default=15)
    last_sync = fields.Char('Última sincronización realizada', readonly=True)
    inbound_endpoint = fields.Char('Endpoint de recepción de guías', readonly=True)
    callback_endpoint = fields.Char('Endpoint para confirmar nota de crédito', readonly=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        self._check_manager()
        cfg = self.env['ir.config_parameter'].sudo()
        cron = self.env.ref('logistica_transcash.cron_transcash_sync_erp', raise_if_not_found=False)
        base = (cfg.get_param('web.base.url') or '').rstrip('/')
        defaults = {
            'api_url': cfg.get_param('logistica_transcash.api_url') or '',
            'api_outbound_token': cfg.get_param('logistica_transcash.api_outbound_token') or '',
            'api_inbound_token': cfg.get_param('logistica_transcash.api_inbound_token') or '',
            'credit_api_url': cfg.get_param('logistica_transcash.credit_api_url') or '',
            'sync_active': cron.active if cron else False,
            'interval_minutes': cron.interval_number if cron else 15,
            'last_sync': cfg.get_param('logistica_transcash.last_sync') or 'Aún no ejecutada',
            'inbound_endpoint': base + '/api/transcash/v1/guias',
            'callback_endpoint': base + '/api/transcash/v1/notas-credito/estado',
        }
        return {**res, **{key:value for key,value in defaults.items() if key in fields_list}}

    def _check_manager(self):
        if not self.env.user.has_group('logistica_transcash.group_logistica_manager'):
            raise AccessError(_('Solo Administración de Logística puede configurar la API.'))

    def _check_https(self, value, label):
        value = (value or '').strip()
        if not value:
            return ''
        parsed = urlparse(value)
        if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
            raise UserError(_('%s debe ser una URL HTTPS válida sin usuario, contraseña ni fragmentos.') % label)
        if len(value) > 2048:
            raise UserError(_('%s es demasiado larga.') % label)
        return value

    def _values(self):
        self.ensure_one()
        self._check_manager()
        if self.interval_minutes < 5 or self.interval_minutes > 1440:
            raise UserError(_('Configure un intervalo entre 5 y 1440 minutos.'))
        return {
            'logistica_transcash.api_url': self._check_https(self.api_url, _('La URL del ERP')),
            'logistica_transcash.api_outbound_token': (self.api_outbound_token or '').strip(),
            'logistica_transcash.api_inbound_token': (self.api_inbound_token or '').strip(),
            'logistica_transcash.credit_api_url': self._check_https(self.credit_api_url, _('La URL de notas de crédito')),
        }

    def action_save(self):
        self.ensure_one()
        values = self._values()
        cfg = self.env['ir.config_parameter'].sudo()
        for key, value in values.items():
            cfg.set_param(key, value)
        cron = self.env.ref('logistica_transcash.cron_transcash_sync_erp', raise_if_not_found=False)
        if cron:
            cron.sudo().write({'active': bool(self.sync_active), 'interval_number': int(self.interval_minutes), 'interval_type':'minutes'})
        return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
            'title': _('Integración ERP'), 'message': _('Configuración guardada.'),
            'type': 'success', 'sticky': False,
        }}

    def action_generate_token(self):
        self.ensure_one()
        self._check_manager()
        # Generate in form but do not enable the API credential until the operator saves.
        self.write({'api_inbound_token': secrets.token_urlsafe(48)})
        return {
            'type':'ir.actions.act_window', 'res_model':self._name, 'res_id':self.id,
            'name':_('Integración API Transcash'), 'view_mode':'form', 'target':'current',
        }

    def action_test(self):
        self.ensure_one()
        self._check_manager()
        url = self._check_https(self.api_url, _('La URL del ERP'))
        if not url:
            raise UserError(_('Configure primero la URL HTTPS del endpoint GET del ERP.'))
        headers = {'Accept':'application/json', 'User-Agent':'Odoo-Transcash/18'}
        if self.api_outbound_token:
            headers['Authorization'] = 'Bearer ' + self.api_outbound_token.strip()
        try:
            with urlopen(Request(url, headers=headers, method='GET'), timeout=12) as response:
                if response.status != 200:
                    raise UserError(_('El ERP respondió con HTTP %s.') % response.status)
                raw = response.read(5 * 1024 * 1024 + 1)
                if len(raw) > 5 * 1024 * 1024:
                    raise UserError(_('El ERP devolvió más de 5 MB.'))
            body = json.loads(raw.decode('utf-8'))
            guides = body.get('guias') if isinstance(body, dict) else body
            if not isinstance(guides, list):
                raise UserError(_('El ERP debe devolver una lista JSON o un objeto con clave "guias".'))
        except (OSError, ValueError, UnicodeError) as exc:
            raise UserError(_('Error al comprobar conexión con ERP: %s') % str(exc)[:230]) from exc
        # Important: this is read only. It does not import or modify any guide.
        return {'type':'ir.actions.client', 'tag':'display_notification', 'params': {
            'title':_('Conexión con ERP'),
            'message':_('Conexión correcta; respuesta con %s guías (sin importar datos).') % len(guides),
            'type':'success', 'sticky':False,
        }}

    def action_sync(self):
        self.ensure_one()
        self.action_save()  # Persist the values before manual synchronisation.
        return self.env['transcash.guia'].action_sync_now()
