"""Puente sin alterar las guías ni estados operativos de la versión 5.32.

La importación se guarda en los modelos independientes tc.guide.
La conciliación futura con transcash.guia es otra fase deliberada.
"""
import logging
from odoo import api, models, fields, _
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)
API_NAME = 'getguiaslogistica'


class TranscashGuiaAdministratorBridge(models.Model):
    _inherit = 'transcash.guia'

    @api.model
    def _transcash_api_config(self, company_id):
        record = self.env['api.administrator'].sudo().search([
            ('name', '=', API_NAME), ('type', '=', 'get'),
            ('status', '=', 'A'), ('company_id', '=', company_id),
        ], limit=1)
        if not record:
            raise UserError(_(
                'No existe la API activa GET getguiaslogistica para la empresa %s en API Administrator.'
            ) % self.env['res.company'].browse(company_id).display_name)
        return record

    @api.model
    def _transcash_run_api_sync(self, company_id):
        self._transcash_api_config(company_id)
        return self.env['tc.guide.sync'].sudo().sync_from_api(company_id)

    @api.model
    def action_sync_now(self):
        if not (self.env.is_superuser() or self.env.user.has_group(
            'logistica_transcash.group_logistica_manager'
        )):
            raise AccessError(_('Solo el jefe de logística puede sincronizar guías.'))
        result = self._transcash_run_api_sync(self.env.company.id)
        self.env['ir.config_parameter'].sudo().set_param(
            'logistica_transcash.last_sync', fields.Datetime.now())
        return {
            'type': 'ir.actions.client', 'tag': 'display_notification',
            'params': {
                'title': _('Guías sincronizadas desde API Administrator'),
                'message': _('En bandeja de importación: creadas %(c)s, actualizadas %(u)s, errores %(e)s. Las guías operativas v5.32 no se modificaron.') % {
                    'c': result['created'], 'u': result['updated'], 'e': len(result['errors']),
                },
                'type': 'warning' if result['errors'] else 'success',
                'sticky': bool(result['errors']),
            }
        }

    @api.model
    def cron_sync_erp(self):
        # No requiere logistica_transcash.api_url ni el token antiguo.
        try:
            self._transcash_run_api_sync(self.env.company.id)
            self.env['ir.config_parameter'].sudo().set_param(
                'logistica_transcash.last_sync', fields.Datetime.now())
        except Exception:
            _logger.exception('Error en cron de getguiaslogistica por API Administrator')


class TranscashAPIWizardBridge(models.TransientModel):
    _inherit = 'transcash.api.wizard'

    def action_test(self):
        self.ensure_one()
        self._check_manager()
        config = self.env['transcash.guia']._transcash_api_config(self.env.company.id)
        result = self.env['api.administrator'].sudo().call_api(
            API_NAME, method='get', company_id=self.env.company.id)
        if not isinstance(result, dict) or result.get('success') is False:
            raise UserError(_('Error consultando getguiaslogistica: %s') % str(result)[:300])
        data = result.get('data')
        if not isinstance(data, list):
            raise UserError(_('La API debe devolver un objeto JSON con data como lista.'))
        return {
            'type': 'ir.actions.client', 'tag': 'display_notification',
            'params': {
                'title': _('Conexión con API Administrator'),
                'message': _('%s registros de guías disponibles en la API %s (sin importar).') % (len(data), config.name),
                'type': 'success', 'sticky': False,
            }
        }

    def action_sync(self):
        self.ensure_one()
        self._check_manager()
        # NO llamar action_save(): regrabaría la URL/token legacy.
        return self.env['transcash.guia'].action_sync_now()
