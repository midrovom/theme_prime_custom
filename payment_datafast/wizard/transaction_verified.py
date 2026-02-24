from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)

class TransactionVerified(models.TransientModel):
    _name = 'payment.transaction.verified'
    _description = 'Verificador de transacciones de pago'

    transaction_id = fields.Char('Id Transacción')
    payment_brand = fields.Char('Marca de Pago')
    amount = fields.Char('Monto')
    payment_type = fields.Char('Tipo de pago')
    payment_transaction = fields.Char('Transacción de pago')
    reference_nbr = fields.Char('Numero de referencia')
    auth_code = fields.Char('Codigo de autorizacion')
    adquirer_response = fields.Char('Respuesta del adquiriente')

    def action_search_transaction(self):
        provider = self.env['payment.provider'].search([('code', '=', 'datafast')], limit=1)
        result = provider._datafast_make_request(
            f'/v1/query/{ self.transaction_id }',
            { 'entityId': provider.entity_id },
            method="GET"
        )

        if result:
            self.write({
                'payment_brand': result.get('paymentBrand'),
                'amount': result.get('amount'),
                'payment_type': result.get('paymentType'),
                'payment_transaction': result.get('merchantTransactionId'),
                'auth_code': result.get('resultDetails', {}).get('AuthCode'),
                'reference_nbr': result.get('resultDetails', {}).get('ReferenceNbr'),
                'adquirer_response': result.get('resultDetails', {}).get('AcquirerResponse'),
            })
    
        return {
            'type': 'ir.actions.act_window',
            'name': 'Verificador de Transacciones',  # <-- Añade este campo
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'view_id': self.env.ref('payment_datafast.payment_datafast_verified_view_form').id,  # <-- Asegúrate de usar tu nombre de módulo correcto
            'views': [(False, 'form')],
        }
    