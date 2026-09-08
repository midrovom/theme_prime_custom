from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    commission_api_url = fields.Char(
        string="URL del origen de ventas",
        config_parameter="transcash_commission.api_url",
    )
    commission_api_method = fields.Selection(
        [("GET", "GET"), ("POST", "POST")],
        default="GET",
        string="Método HTTP",
        config_parameter="transcash_commission.api_method",
    )
    commission_api_auth_type = fields.Selection(
        [("none", "Sin autenticación"), ("bearer", "Bearer token"), ("header", "API key en cabecera")],
        default="none",
        string="Autenticación",
        config_parameter="transcash_commission.api_auth_type",
    )
    commission_api_token = fields.Char(
        string="Token / API key",
        config_parameter="transcash_commission.api_token",
        groups="base.group_system",
    )
    commission_api_header_name = fields.Char(
        string="Nombre de cabecera API key",
        default="X-API-Key",
        config_parameter="transcash_commission.api_header_name",
    )
    commission_api_timeout = fields.Integer(
        string="Timeout (segundos)",
        default=60,
        config_parameter="transcash_commission.api_timeout",
    )
    commission_api_date_from_param = fields.Char(
        string="Parámetro fecha desde",
        default="fecha_desde",
        config_parameter="transcash_commission.api_date_from_param",
    )
    commission_api_date_to_param = fields.Char(
        string="Parámetro fecha hasta",
        default="fecha_hasta",
        config_parameter="transcash_commission.api_date_to_param",
    )
    commission_api_auto_import = fields.Boolean(
        string="Sincronización automática",
        config_parameter="transcash_commission.api_auto_import",
    )
    commission_api_cron_days_back = fields.Integer(
        string="Días a consultar en sincronización automática",
        default=1,
        config_parameter="transcash_commission.api_cron_days_back",
        help="Permite volver a consultar días anteriores. La huella de importación evita duplicados.",
    )
