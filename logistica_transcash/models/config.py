from odoo import fields, models


class TranscashSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    logistica_api_url = fields.Char(
        'URL de consulta al ERP (HTTPS)', config_parameter='logistica_transcash.api_url')
    logistica_api_outbound_token = fields.Char(
        'Token para consultar al ERP', config_parameter='logistica_transcash.api_outbound_token')
    logistica_api_inbound_token = fields.Char(
        'Token para recibir datos del ERP', config_parameter='logistica_transcash.api_inbound_token')

    logistica_credit_api_url = fields.Char(
        'Endpoint HTTPS solicitud NC ERP', config_parameter='logistica_transcash.credit_api_url')
