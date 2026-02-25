# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
import pprint

from odoo.addons.website_sale.controllers import main
from odoo import http
from odoo.exceptions import ValidationError
from odoo.http import request
from werkzeug.exceptions import NotFound

_logger = logging.getLogger(__name__)

import requests

class DatafastController(http.Controller):
    _return_url = '/payment/datafast/return'
    _webhook_url = '/payment/datafast/webhook'

    @http.route('/payment/datafast', type='http', auth='public', website=True)
    def payment_redirect(self, **kwargs):
        checkout_id = request.session.get('checkout_id')
        if not checkout_id:
            raise NotFound("Missing checkout_id in session.")
        
        _logger.info(f'MOSTRANDO EL CHECKOUT ID >>> { checkout_id }')

        return request.render('payment_datafast.redirect_form', {
            'checkout_id': checkout_id,
        })
    
    @http.route('/payment/datafast/callback', type='http', auth='public', website=True)
    def payment_datafast_callback(self, **kwargs):
        _logger.info(f'MOSTRANDO RESOURCE PATH >> { kwargs }')
        id = kwargs.get('id')
        if not id:
            _logger.error('No se recibió el ID en el callback.')
            return request.redirect('/payment/status?error=no_id')
        
        provider = request.env['payment.provider'].sudo().search([('code', '=', 'datafast')], limit=1)

        headers = {
            'Authorization': f'Bearer { provider.datafast_access_token }'
        }

        url = f'{ provider.datafast_url }/v1/checkouts/{ id }/payment'
        params = {
            'entityId': provider.entity_id
        }

        try:
            response = requests.get(url, headers=headers, params=params)
            result = response.json()
            response.raise_for_status()

            _logger.info(f'MOSTRANDO RESPONSE >>> { result }')
            request.env['payment.transaction'].sudo()._handle_notification_data('datafast', result)

        except requests.exceptions.HTTPError as e:
            _logger.error(f'HTTPError: {e.response.status_code} - {e.response.text}')
            return request.redirect('/payment/status?error=http')
        except Exception as e:
            _logger.error(f'Error inesperado: {str(e)}')
            return request.redirect('/payment/status?error=unexpected')

        return request.redirect('/payment/status')
    

    # @http.route('/payment/datafast/callback', type='http', auth='public', website=True)
    # def payment_datafast_callback(self, **kwargs):
    #     id = kwargs.get('id')
    #     if not id:
    #         _logger.error('No se recibió el ID en el callback.')
    #         return request.redirect('/payment/status?error=no_id')

    #     headers = {
    #         'Authorization': 'Bearer OGE4Mjk0MTg1YTY1YmY1ZTAxNWE2YzhjNzI4YzBkOTV8YmZxR3F3UTMyWA=='
    #     }

    #     url = f'https://eu-test.oppwa.com/v1/checkouts/{ id }/payment'
    #     params = {
    #         'entityId': '8ac7a4c795a0f72f0195a5faf0cf0984'
    #     }

    #     try:
    #         response = requests.get(url, headers=headers, params=params)
    #         response.raise_for_status()
    #         result = response.json()
    #         _logger.info(f'MOSTRANDO RESPONSE >>> {result}')

    #         # Buscar la transacción en Odoo
    #         tx_sudo = request.env['payment.transaction'].sudo().search([
    #             ('reference', '=', result.get('merchantTransactionId'))
    #         ])

    #         if tx_sudo:
    #             if result['result']['code'] == '000.100.112' and result['resultDetails']['Response'] == '00':
    #                 _logger.info(f"Datafast payment approved for tx {tx_sudo.reference}")
    #                 tx_sudo._handle_notification_data('datafast', result)
    #             else:
    #                 _logger.warning(f"Datafast payment failed for tx {tx_sudo.reference}")
    #                 tx_sudo._handle_notification_data('datafast', result)
    #         else:
    #             _logger.error(f"Transaction with reference {result.get('merchantTransactionId')} not found.")

    #     except requests.exceptions.HTTPError as e:
    #         _logger.error(f'HTTPError: {e.response.status_code} - {e.response.text}')
    #         return request.redirect('/payment/status?error=http')
    #     except Exception as e:
    #         _logger.error(f'Error inesperado: {str(e)}')
    #         return request.redirect('/payment/status?error=unexpected')

    #     return request.redirect('/payment/status')



    @http.route(_return_url, type='http', methods=['GET'], auth='public')
    def datafast_return_from_checkout(self, **data):
        """ Process the notification data sent by DataFast after redirection from checkout.

        :param dict data: The notification data.
        """
        # Handle the notification data.
        _logger.info("Handling redirection from DataFast with data:\n%s", pprint.pformat(data))
        if data.get('payment_id') != 'null':
            request.env['payment.transaction'].sudo()._handle_notification_data(
                'datafast', data
            )
        else:  # The customer cancelled the payment by clicking on the return button.
            pass  # Don't try to process this case because the payment id was not provided.

        # Redirect the user to the status page.
        return request.redirect('/payment/status')

    @http.route(
        f'{_webhook_url}/<reference>', type='http', auth='public', methods=['POST'], csrf=False
    )
    def datafast_webhook(self, reference, **_kwargs):
        """ Process the notification data sent by DataFast to the webhook.

        :param str reference: The transaction reference embedded in the webhook URL.
        :param dict _kwargs: The extra query parameters.
        :return: An empty string to acknowledge the notification.
        :rtype: str
        """
        data = request.get_json_data()
        _logger.info("Notification received from DataFast with data:\n%s", pprint.pformat(data))

        # DataFast sends two types of asynchronous notifications: webhook notifications and
        # IPNs which are very similar to webhook notifications but are sent later and contain less
        # information. Therefore, we filter the notifications we receive based on the 'action'
        # (type of event) key as it is not populated for IPNs, and we don't want to process the
        # other types of events.
        if data.get('action') in ('payment.created', 'payment.updated'):
            # Handle the notification data.
            try:
                payment_id = data.get('data', {}).get('id')
                request.env['payment.transaction'].sudo()._handle_notification_data(
                    'datafast', {'external_reference': reference, 'payment_id': payment_id}
                )  # Use 'external_reference' as the reference key like in the redirect data.
            except ValidationError:  # Acknowledge the notification to avoid getting spammed.
                _logger.exception("Unable to handle the notification data; skipping to acknowledge")
        return ''  # Acknowledge the notification.


class PaymentPortalDatafast(main.PaymentPortal):
    @http.route(
        '/shop/payment/transaction/<int:order_id>', type='json', auth='public', website=True
    )
    def shop_payment_transaction(self, order_id, access_token, **kwargs):
        result = super(PaymentPortalDatafast, self).shop_payment_transaction(order_id, access_token, **kwargs)

        if result.get('provider_code') != 'datafast':
            return result
        
        request.session['checkout_id'] = result.get("data").get("id")

        return result
    