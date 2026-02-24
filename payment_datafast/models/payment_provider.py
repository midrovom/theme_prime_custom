import logging
import pprint

import requests
from werkzeug import urls

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from odoo.addons.payment_datafast.const import SUPPORTED_CURRENCIES


_logger = logging.getLogger(__name__)

CONTENT_TYPE = "application/x-www-form-urlencoded"

class StateCodeDatafast(models.Model):
    _name = 'state.code.datafast'
    
    name = fields.Char('Descripcion')
    code = fields.Char('Codigo')
    datafast_id = fields.Many2one('payment.provider', string='Datafast')
    

class PaymentProvider(models.Model):
    _inherit = 'payment.provider'

    code = fields.Selection(
        selection_add=[('datafast', "DataFast")], ondelete={'datafast': 'set default'}
    )

    state_code_ids = fields.One2many('state.code.datafast', 'datafast_id', string='Codigos de estado')
    datafast_url = fields.Char(string='Url del proveedor')
    entity_id = fields.Char(string='Identificador de entidad')
    merchant_id = fields.Char(string='Identificador del comercio')
    terminal_id = fields.Char(string='Identificador del terminal')

    test_mode = fields.Char(
        string='Modo test',
        default='EXTERNAL',
        readonly=True,
        help="""
            Este parámetro solo es disponible en ambiente de pruebas y el valor fijo es EXTERNAL.
        """
    )

    datafast_access_token = fields.Char(
        string="Token de acceso",
        required_if_provider='datafast',
        groups='base.group_system',
    )

    # === BUSINESS METHODS === #

    @api.model
    def _get_compatible_providers(self, *args, currency_id=None, **kwargs):
        """ Override of `payment` to unlist DataFast providers for unsupported currencies. """
        providers = super()._get_compatible_providers(*args, currency_id=currency_id, **kwargs)

        currency = self.env['res.currency'].browse(currency_id).exists()
        if currency and currency.name not in SUPPORTED_CURRENCIES:
            providers = providers.filtered(lambda p: p.code != 'datafast')

        return providers

    def _datafast_make_request(self, endpoint, payload=None, method='POST'):
        """ Make a request to DataFast API at the specified endpoint.

        Note: self.ensure_one()

        :param str endpoint: The endpoint to be reached by the request.
        :param dict payload: The payload of the request.
        :param str method: The HTTP method of the request.
        :return The JSON-formatted content of the response.
        :rtype: dict
        :raise ValidationError: If an HTTP error occurs.
        """
        self.ensure_one()

        if payload and method == "POST":
            payload["entityId"] = self.entity_id

            if payload.get("paymentType") != "RF":
                payload["customParameters[SHOPPER_MID]"] = self.merchant_id
                payload["customParameters[SHOPPER_TID]"] = self.terminal_id

            if self.state == 'test':
                payload["testMode"] = self.test_mode

        url = urls.url_join(self.datafast_url, endpoint)
        headers = {
            'Authorization': f'Bearer { self.datafast_access_token }',
            "Content-Type": CONTENT_TYPE,
        }

        try:
            if method == 'GET':
                response = requests.get(url, params=payload, headers=headers, timeout=10)
            else:
                response = requests.post(url, headers=headers, data=payload, timeout=10)
            try:
                response.raise_for_status()
            except requests.exceptions.HTTPError:
                _logger.exception(
                    "Solicitud de API no válida en %s con datos:\n%s", url, pprint.pformat(payload),
                )
                try:
                    response_content = response.json()
                    error_code = response_content.get('error')
                    error_message = response_content.get('message')
                    raise ValidationError("DataFast: " + _(
                        "Falló la comunicación con la API. DataFast devolvió esta información: '%s' (código %s)",
                        error_message, 
                        error_code
                    ))
                except ValueError:  # The response can be empty when the access token is wrong.
                    raise ValidationError("DataFast: " + _(
                        "La comunicación con la API falló. La respuesta está vacía. Por favor, verifica tu token de acceso." 
                    ))
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            _logger.exception("No se pudo acceder al endpoint en %s", url)
            raise ValidationError(
                "DataFast: " + _("No se pudo establecer la conexión con la API."  )
            )

        return response.json()
