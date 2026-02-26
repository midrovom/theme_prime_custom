# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
import pprint

from urllib.parse import quote as url_quote
from werkzeug import urls
from odoo import _, api, models, fields
from odoo.http import request
from odoo.exceptions import UserError, ValidationError
from odoo.addons.payment_datafast.const import ERROR_MESSAGE_MAPPING, TRANSACTION_STATUS_MAPPING
from odoo.addons.payment_datafast.controllers.main import DatafastController

_logger = logging.getLogger(__name__)

class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    transaction_df_id = fields.Char('Identificador de la transacción')

    def cancel_transaction(self):
        if self.provider_code == 'datafast':
            payload = {
                "amount": self.amount,
                "currency": self.currency_id.name,
                "paymentType": "RF"
            }
            result = self.provider_id._datafast_make_request(
                f'/v1/payments/{ self.transaction_df_id }',
                payload
            )

            _logger.info(f"MOSTRANDO ANULACION >>> { result }")

    # Envio de datos al api de datafast
    
    # def _get_specific_rendering_values(self, processing_values):
    #     """ Override of `payment` to return DataFast-specific rendering values.

    #     Note: self.ensure_one() from `_get_rendering_values`.

    #     :param dict processing_values: The generic and specific processing values of the transaction
    #     :return: The dict of provider-specific processing values.
    #     :rtype: dict
    #     """
    #     res = super()._get_specific_rendering_values(processing_values)
    #     if self.provider_code != 'datafast':
    #         return res

    #     # Initiate the payment and retrieve the payment link data.
    #     payload = self._datafast_prepare_authorization_payload()
    #     # _logger.info(
    #     #     "Sending '/checkout/preferences' request for link creation:\n%s",
    #     #     pprint.pformat(payload),
    #     # )
    #     api_url = self.provider_id._datafast_make_request(
    #         '/v1/checkouts', payload=payload
    #     )

    #     # Extract the payment link URL and embed it in the redirect form.
    #     _logger.info(api_url.get('id'))
    #     rendering_values = {
    #         'api_url': api_url,
    #     }

    #     return rendering_values
    
    def _get_specific_rendering_values(self, processing_values):
        """Override of `payment` to return DataFast-specific rendering values."""
        self.ensure_one()
        _logger.info("Entrando a _get_specific_rendering_values con provider_code=%s", self.provider_code)

        res = super()._get_specific_rendering_values(processing_values)
        if self.provider_code != 'datafast':
            _logger.info("Proveedor no es Datafast, devolviendo valores estándar")
            return res

        # Preparar payload y hacer request
        payload = self._datafast_prepare_authorization_payload()
        _logger.info("Payload enviado a Datafast:\n%s", pprint.pformat(payload))

        api_response = self.provider_id._datafast_make_request('/v1/checkouts', payload=payload)
        _logger.info("Respuesta cruda de Datafast:\n%s", pprint.pformat(api_response))

        # Extraer checkout_id del response
        checkout_id = api_response.get('id')
        if not checkout_id:
            _logger.error("No se recibió 'id' en la respuesta de Datafast: %s", api_response)
        else:
            _logger.info("Checkout ID recibido: %s", checkout_id)

        rendering_values = {
            'api_url': api_response,
            'checkout_id': checkout_id,
            'main_object': self,
        }
        _logger.info("Rendering values construidos:\n%s", pprint.pformat(rendering_values))

        return rendering_values

    def _datafast_prepare_authorization_payload(self):
        """
            Crea el payload con respecto a los campos requeridos por Datafast
        """

        given_name, middle_name, surname = self.partner_id.split_name()

        # Obtener la IP del cliente (si está en un contexto HTTP)
        try:
            client_ip = request.httprequest.headers.get('X-Forwarded-For', request.httprequest.remote_addr)
        except Exception:
            client_ip = '0.0.0.0'  # fallback si no se puede acceder al request

        sale_order_ids = self.sale_order_ids or None 
        sale_order = sale_order_ids[0]

        payload = {
            "amount": "{:.2f}".format(self.amount), #formato 2 decimales para datafast
            "currency": self.currency_id.name,
            "paymentType": "DB",
            "customer.givenName": given_name,
            "customer.middleName": middle_name,
            "customer.surname": surname,
            "customer.ip": client_ip,
            "customer.merchantCustomerId": f"{ self.partner_id.id }",
            "merchantTransactionId": f"transaction_{ self.id }",
            "customer.email": self.partner_email,
            "customer.identificationDocType": "IDCARD",
            "customer.identificationDocId": self.partner_id.get_identification_doc_id(),
            "customer.phone": self.partner_phone,
            "billing.street1": self.partner_address,
            "billing.country": self.partner_country_id.code.upper(),
            "shipping.street1": self.partner_address, # cambiar aqui es direccion de envio
            "shipping.country": self.partner_country_id.code.upper(), #cambiar aqui es pais de envio
            "customParameters[SHOPPER_ECI]": "0103910",
            "customParameters[SHOPPER_PSERV]": "17913101",
            "customParameters[SHOPPER_VAL_BASE0]": "{:.2f}".format(sale_order.shopper_val_base0),
            "customParameters[SHOPPER_VAL_BASEIMP]": "{:.2f}".format(sale_order.shopper_val_baseimp),#formato 2 decimales para datafast
            "customParameters[SHOPPER_VAL_IVA]": f"{ sale_order.shopper_val_iva }",
            "risk.parameters[USER_DATA2]": "DATAFAST",
            "customParameters[SHOPPER_VERSIONDF]": "2",
        }

        order_line_ids = sale_order_ids[0].order_line

        for i, l in enumerate(order_line_ids):
            payload[f"cart.items[{ i }].name"] = l.product_id.name
            payload[f"cart.items[{ i }].price"] = "{:.2f}".format(l.price_unit)
            payload[f"cart.items[{ i }].quantity"] = "{:.0f}".format(l.product_uom_qty) #formato entero para datafast

        for i, p in enumerate(self.partner_id.token_ids):
            payload[f'registrations[{ i }].id'] = f'{ p.token }'

        return payload

    @api.model
    def _datafast_get_error_msg(self, status_detail):
        """ Return the error message corresponding to the payment status.

        :param str status_detail: The status details sent by the provider.
        :return: The error message.
        :rtype: str
        """
        return "DataFast: " + ERROR_MESSAGE_MAPPING.get(
            status_detail, ERROR_MESSAGE_MAPPING['cc_rejected_other_reason']
        )
    

    def _get_processing_values(self):
        if self.provider_code != 'datafast':
            return super(PaymentTransaction, self)._get_processing_values()

        self.ensure_one()

        processing_values = {
            'provider_id': self.provider_id.id,
            'provider_code': self.provider_code,
            'reference': self.reference,
            'amount': self.amount,
            'currency_id': self.currency_id.id,
            'partner_id': self.partner_id.id,
        }

        # Complete generic processing values with provider-specific values.
        processing_values.update(self._get_specific_processing_values(processing_values))
        _logger.info(
            "generic and provider-specific processing values for transaction with reference "
            "%(ref)s:\n%(values)s",
            {'ref': self.reference, 'values': pprint.pformat(processing_values)},
        )

        # Render the html form for the redirect flow if available.
        if self.operation in ('online_redirect', 'validation'):
            redirect_form_view = self.provider_id._get_redirect_form_view(
                is_validation=self.operation == 'validation'
            )
            if redirect_form_view:  # Some provider don't need a redirect form.
                rendering_values = self._get_specific_rendering_values(processing_values)
                _logger.info(
                    "provider-specific rendering values for transaction with reference "
                    "%(ref)s:\n%(values)s",
                    {'ref': self.reference, 'values': pprint.pformat(rendering_values)},
                )
                processing_values.update(redirect_form_html="/payment/datafast")
                data = rendering_values.get('api_url')
                processing_values.update(data=data)


        return processing_values
    
    # def _get_processing_values(self):
    #     """Return the values used to process the transaction."""
    #     self.ensure_one()
    #     _logger.info("Entrando a _get_processing_values para referencia=%s", self.reference)

    #     if self.provider_code != 'datafast':
    #         _logger.info("Proveedor no es Datafast, usando super()")
    #         return super()._get_processing_values()

    #     # Valores base requeridos por Odoo
    #     processing_values = {
    #         'provider_id': self.provider_id.id,
    #         'provider_code': self.provider_code,
    #         'reference': self.reference,
    #         'amount': self.amount,
    #         'currency_id': self.currency_id.id,
    #         'partner_id': self.partner_id.id,
    #         'should_tokenize': self.tokenize,
    #     }

    #     _logger.info("Valores iniciales:\n%s", pprint.pformat(processing_values))

    #     # Añadir valores específicos del provider (aquí se crea el checkout)
    #     processing_values.update(
    #         self._get_specific_processing_values(processing_values)
    #     )

    #     _logger.info("Valores tras específicos:\n%s", pprint.pformat(processing_values))

    #     if self.operation in ('online_redirect', 'validation'):
    #         _logger.info("Operación %s requiere redirección", self.operation)

    #         rendering_values = self._get_specific_rendering_values(processing_values)

    #         _logger.info("Rendering values:\n%s", pprint.pformat(rendering_values))

    #         checkout_id = rendering_values.get('checkout_id')

    #         if checkout_id:
    #             processing_values['checkout_id'] = checkout_id
    #             _logger.info("checkout_id añadido a processing_values")
    #         else:
    #             _logger.warning("No se encontró checkout_id en rendering_values")

    #     _logger.info("Valores finales:\n%s", pprint.pformat(processing_values))
    #     return processing_values

    def _get_processing_values(self):
        if self.provider_code != 'datafast':
            return super(PaymentTransaction, self)._get_processing_values()

        self.ensure_one()

        processing_values = {
            'provider_id': self.provider_id.id,
            'provider_code': self.provider_code,
            'reference': self.reference,
            'amount': self.amount,
            'currency_id': self.currency_id.id,
            'partner_id': self.partner_id.id,
        }

        # Complete generic processing values with provider-specific values.
        processing_values.update(self._get_specific_processing_values(processing_values))
        _logger.info(
            "generic and provider-specific processing values for transaction with reference "
            "%(ref)s:\n%(values)s",
            {'ref': self.reference, 'values': pprint.pformat(processing_values)},
        )

        # Render the html form for the redirect flow if available.
        if self.operation in ('online_redirect', 'validation'):
            redirect_form_view = self.provider_id._get_redirect_form_view(
                is_validation=self.operation == 'validation'
            )
            if redirect_form_view:  # Some provider don't need a redirect form.
                rendering_values = self._get_specific_rendering_values(processing_values)
                _logger.info(
                    "provider-specific rendering values for transaction with reference "
                    "%(ref)s:\n%(values)s",
                    {'ref': self.reference, 'values': pprint.pformat(rendering_values)},
                )
                processing_values.update(redirect_form_html="/payment/datafast")
                data = rendering_values.get('api_url')
                processing_values.update(data=data)


        return processing_values
    
    def _get_tx_from_notification_data(self, provider_code, notification_data):
        if provider_code != "datafast":
            return super()._get_tx_from_notification_data(provider_code, notification_data)
        
        payment_provider_id = self.env['payment.provider'].search([('code', '=', provider_code)])

        merchand_id = notification_data.get('merchantTransactionId')
        merchand_id = merchand_id.split("_")
        merchand_id = merchand_id[1]

        transaction_id = self.search([
            ('id', '=', int(merchand_id)),
            ('provider_id', '=', payment_provider_id.id),
        ], limit=1)

        notification_data['provider_code'] = payment_provider_id.code
        notification_data['reference'] = transaction_id.reference

        return transaction_id
    
    # recibe notification enviado por Datafast y lo procesa

    def _process_notification_data(self, notification_data):
        super()._process_notification_data(notification_data)
        provider_code = notification_data.get('provider_code')
        if provider_code != "datafast":
            return
        
        self.write({ 'transaction_df_id': notification_data.get('id') })
        
        if notification_data.get('registrationId'):
            registration_id = notification_data.get('registrationId')
            card = notification_data.get('card')
            reference_card = card.get('bin') + card.get('last4Digits')
            expiry_month = card.get('expiryMonth')
            expiry_year = card.get('expiryYear')

            token_card = self.env['token.card'].search([
                ('reference_card', '=', reference_card),
                ('expiry_month', '=', expiry_month),
                ('expiry_year', '=', expiry_year),
            ])

            if not token_card:
                brand = notification_data.get('paymentBrand')
                self.partner_id.write({
                    'token_ids': [(0, 0, {
                        'name': brand, 
                        'token': registration_id,
                        'reference_card': reference_card,
                        'expiry_month': expiry_month,
                        'expiry_year': expiry_year,
                    })]
                })
        
        self.provider_reference = f"datafast-{ self.reference }"
        message_state = self.env['state.code.datafast'].search([
            ('code', '=', notification_data.get('result').get('code'))
            
        ], limit=1)

        _logger.info("DATAFAST RESULT >>> %s", notification_data.get('result'))

        if message_state.code == '000.100.112' or message_state.code == '000.000.000':
            self._set_done(state_message=message_state.name)

            request and request.website and request.website.sale_reset()
        else:
            _logger.error( "Transacción Datafast marcada como ERROR. " "ID DF: %s | Código recibido: %s | Mensaje: %s", notification_data.get('id'), notification_data.get('result').get('code'), message_state.name )
            
            self._set_error(state_message=message_state.name)
        



        


