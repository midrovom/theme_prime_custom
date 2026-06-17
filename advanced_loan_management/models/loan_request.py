# -*- coding: utf-8 -*-
################################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2023-TODAY Cybrosys Technologies(<https://www.cybrosys.com>).
#    Author: Sabeel (odoo@cybrosys.com)
#
#    You can modify it under the terms of the GNU AFFERO
#    GENERAL PUBLIC LICENSE (AGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU AFFERO GENERAL PUBLIC LICENSE (AGPL v3) for more details.
#
#    You should have received a copy of the GNU AFFERO GENERAL PUBLIC LICENSE
#    (AGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
################################################################################

import pytz

from datetime import datetime
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models, _
from odoo.exceptions import UserError

import logging
_logger = logging.getLogger(__name__)


class LoanRequest(models.Model):
    """Can create new loan requests and manage records"""
    _name = 'loan.request'
    _inherit = ['mail.thread']
    _description = 'Loan Request'

    name = fields.Char(string='Referencia de préstamo', readonly=True,
                       copy=False, help="Número de secuencia para solicitudes de préstamo",
                       default=lambda self: 'New')
    company_id = fields.Many2one('res.company', string='Compañía',
                                 readonly=True,
                                 help="Nombre de la compañia",
                                 default=lambda self:
                                 self.env.company)
    currency_id = fields.Many2one('res.currency', string='Moneda', create=False, index=False,
                                  required=True, help="Tipo de moneda",
                                  default=lambda self: self.env.user.company_id.
                                  currency_id)
    loan_type_id = fields.Many2one('loan.type', string='Tipo de Préstamos',
                                   required=True, 
                                   help="Puede elegir diferente "
                                                       "tipos de préstamos adecuados")
    """ product_id = fields.Many2one('product.template', string='Producto',
                                   required=True, help="Escoja el Producto  "
                                                       "Para Gestionar el Credito") """

    product_id = fields.Many2one(   'product.template', 
                                    string='Producto',         
                                    index=True,
                                    auto_join=True,
                                    tracking=True
                                )
                                

    product_image = fields.Binary(string='Imagen del Producto', related='product_id.image_256', store=False)
    
    loan_amount = fields.Float(string="Monto del Préstamo", store=True, compute="_compute_loan_amount",
                               help="Total monto del préstamo" )
   
    loan_amount_total = fields.Float(string="Total Credito", store=True,
                               help="Total monto del prestamo  ( (Monto del Préstamo  * Tasa de interés) + Monto del Préstamo )",compute="_compute_loan_amount_total" )
    tenure = fields.Integer(string="Plazo", store=True, compute="_compute_tenure",
                            help="Periodo de amortización")

    interest_rate = fields.Float(string="Tasa de interés", compute="_compute_interest_rate", help="Tasa de interés " 
                                                        "percentage" , readonly=True ,store=True)

 
    entry_amount = fields.Float(string="Valor de Entrada", compute="_compute_entry_amount", help="Valor de Entrada Inicial"
                                                              " ( Monto del Préstamo  * Tasa de Entrada Sugerida )")
    entry_rate = fields.Float(string="Tasa de Entrada Sugerida",
                               help="Tasa de Entrada Sugerida"
                               )
    date = fields.Date(string="Fecha Proximo Pago", default=fields.Date.today(),
                       readonly=False, help="Fecha de Sigueinte Pago")
                       
    date_concesion = fields.Date(string="Fecha de Concesion", default=fields.Date.today(),
                       readonly=True, help="Fecha de Concesion")
    partner_id = fields.Many2one('res.partner', string="Partner",
                                 required=True,
                                 help="Partner")
    repayment_lines_ids = fields.One2many('repayment.line',
                                          'loan_id',
                                          string="Loan Line", index=True,
                                          help="Repayment lines")
    documents_ids = fields.Many2many('loan.documents',
                                     string="Proofs",
                                     help="Documents as proof")
    img_attachment_ids = fields.Many2many('ir.attachment',
                                          relation="m2m_ir_identity_card_rel",
                                          column1="documents_ids",
                                          string="Images",
                                          help="Image proofs")
    journal_id = fields.Many2one('account.journal',
                                 string="Journal",
                                 help="Journal types",
                                 domain="[('type', '=', 'purchase'),"
                                        "('company_id', '=', company_id)]",
                                 )
    debit_account_id = fields.Many2one('account.account',
                                       string="Debit account",
                                       help="Choose account for "
                                            "disbursement debit")
    credit_account_id = fields.Many2one('account.account',
                                        string="Credit account",
                                        help="Choose account for "
                                             "disbursement credit")
    reject_reason = fields.Text(string="Reason", help="Displays "
                                                      "rejected reason")
    request = fields.Boolean(string="Request", default=False,
                             help="For monitoring the record")
    
    state = fields.Selection(
        string='State',
        selection=[('draft', 'Pendiente'), ('confirmed', 'Confirmado'),
                   ('waiting for approval', 'En espera de aprobación'),
                   ('approved', 'Aprobado'), ('disbursed', 'Generado'),
                   ('rejected', 'Rechazado'), ('closed', 'Cerrado')],
        required=True, readonly=True, copy=False,
        tracking=True, default='draft', help="Estados de solicitud del plan")


    suggested_loan_amount = fields.Float(string='Monto sugerido', store=True, default='0.00' ,compute = '_compute_suggested_loan_amount',
                                        help="Monto sugerido depende del tipo de plan ")

    disbursal_amount = fields.Float(string="Monto de desembolso", compute="_compute_disbursal_amount",
                                    help="Total del monto a entregar ")
    
    payment_value = fields.Float(string="Cuota Aprox", compute="_compute_payment_value",
                                    help="Calculo cuota periodica")

    imei = fields.Char(string='IMEI', size=15, help="Número de serie")


    @api.depends('interest_rate', 'loan_amount','entry_amount')
    def _compute_loan_amount_total(self):
        for record in self:
            #_logger.info("VALUE REWARD AMOUNT DISCOUNT  %s", record.interest_rate )
            #record.loan_amount_total = ((record.loan_amount - record.entry_amount) * record.interest_rate ) + record.loan_amount
            record.loan_amount_total = (  record.loan_amount * record.interest_rate) + record.loan_amount

    @api.depends('entry_rate', 'loan_amount')
    def _compute_entry_amount(self):
        for record in self:
            record.entry_amount = record.loan_amount * record.entry_rate

    @api.depends('loan_type_id')
    def _compute_suggested_loan_amount(self):
        for record in self:
            record.suggested_loan_amount = record.loan_type_id.loan_amount

    @api.depends('loan_type_id')
    def _compute_interest_rate(self):
        for record in self:
            record.interest_rate = record.loan_type_id.interest_rate
    
    @api.depends('loan_type_id')
    def _compute_tenure(self):
        for record in self:
            record.tenure = record.loan_type_id.tenure

    @api.depends('product_id')
    def _compute_loan_amount(self):
        for record in self:
            if record.product_id:
                record.loan_amount = record.product_id.list_price
            else:
                record.loan_amount = 0.0

    @api.depends('interest_rate', 'loan_amount','entry_amount')
    def _compute_disbursal_amount(self):
        for record in self:
            record.disbursal_amount = ((record.interest_rate * record.loan_amount ) + record.loan_amount) - record.entry_amount
    
    @api.depends('disbursal_amount', 'tenure')
    def _compute_payment_value(self):
        for record in self:
            if record.disbursal_amount > 0 and  record.tenure > 0 :
                record.payment_value = record.disbursal_amount / record.tenure
            else:
                record.payment_value = 0.00

    @api.constrains('imei')
    def _check_imei_length(self):
        for record in self:
            if record.imei and len(record.imei) != 15:
                raise UserError(
                    _('El campo IMEI debe tener exactamente 15 caracteres.'))
               
            
    @api.model
    def create(self, vals):
        """create  auto sequence for the loan request records"""
        loan_count = self.env['loan.request'].search(
            [('partner_id', '=', vals['partner_id']),
             ('state', 'not in', ('draft', 'rejected', 'closed'))])
        if loan_count:
            for rec in loan_count:
                if rec.state != 'closed':
                    raise UserError(
                        _('The partner has already an ongoing loan.'))
        else:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'increment_loan_ref')
            res = super().create(vals)
            return res

    @api.onchange('loan_type_id')
    def _onchange_loan_type_id(self):
        """Changing field values based on the chosen loan type"""
        for record in self:
            if record.loan_type_id:
                record.entry_rate = record.loan_type_id.entry_rate
            else:
                record.entry_rate = 0.0 

        #type_id = self.loan_type_id
        #self.loan_amount = type_id.loan_amount
        #self.disbursal_amount = (type_id.interest_rate * self.loan_amount ) + self.loan_amount-self.entry_amount
        #self.tenure = type_id.tenure
        #self.interest_rate = type_id.interest_rate
        #self.documents_ids = type_id.documents_ids
        #self.dentry_val = type_id.loan_amount * type_id.entry_rate
    
    
        #@api.onchange('loan_amount','entry_rate','interest_rate')
        #def _onchange_loan_amount_entry(self):
        #    """Changing field values based on the chosen loan type"""
        #    type_id = self.loan_type_id
        #    self.entry_amount = self.loan_amount * self.entry_rate
        #    #self.disbursal_amount= self.loan_amount_total - self.entry_amount
        #    #self.disbursal_amount= self.loan_amount - self.entry_amount
        #    self.disbursal_amount = (type_id.interest_rate * self.loan_amount ) + self.loan_amount - self.entry_amount
        #self.disbursal_amount = self.loan_amount


    def action_loan_request(self):
        """Changes the state to confirmed and send confirmation mail"""
        self.write({'state': "confirmed"})
        partner = self.partner_id
        loan_no = self.name
        subject = 'Loan Confirmation'

        message = (f"Dear {partner.name},<br/> This is a confirmation mail "
                   f"for your loan{loan_no}. We have submitted your loan "
                   f"for approval.")

        outgoing_mail = self.company_id.email
        mail_values = {
            'subject': subject,
            'email_from': outgoing_mail,
            'author_id': self.env.user.partner_id.id,
            'email_to': partner.email,
            'body_html': message,
        }
        mail = self.env['mail.mail'].sudo().create(mail_values)
        mail.send()

    def action_request_for_loan(self):
        """Change the state to waiting for approval"""
        if self.request:
            self.write({'state': "waiting for approval"})
        else:
            message_id = self.env['message.popup'].create(
                {'message': _("Calcular las amortizaciones antes de solicitar")})
            return {
                'name': _('Pagos'),
                'type': 'ir.actions.act_window',
                'view_mode': 'form',
                'res_model': 'message.popup',
                'res_id': message_id.id,
                'target': 'new'
            }

    def action_loan_approved(self):
        """Change to Approved state"""
        self.write({'state': "approved"})



    def action_disburse_loan(self):
        """Disbursing the loan to customer and creating journal
         entry for the disbursement"""
        for loan in self:
            if  not loan.imei:
                loan.imei = False 
                message_id = self.env['message.popup'].create(
                {'message': _("SE debe registrar el imei para el desembolso")})
                return {
                    'name': _('Pagos'),
                    'type': 'ir.actions.act_window',
                    'view_mode': 'form',
                    'res_model': 'message.popup',
                    'res_id': message_id.id,
                    'target': 'new'
                }
                
                return False
            else :
                self.write({'state': "disbursed"})
                return True

        #for loan in self:
        #    amount = loan.disbursal_amount
        #    loan_name = loan.partner_id.name
        #    reference = loan.name
        #    journal_id = loan.journal_id.id
        #    debit_account_id = loan.debit_account_id.id
        #    credit_account_id = loan.credit_account_id.id
        #    date_now = loan.date
        #    debit_vals = {
        #        'name': loan_name,
        #        'account_id': debit_account_id,
        #        'journal_id': journal_id,
        #        'date': date_now,
        #        'debit': amount > 0.0 and amount or 0.0,
        #        'credit': amount < 0.0 and -amount or 0.0,
        #
        #    }
        #    credit_vals = {
        #        'name': loan_name,
        #        'account_id': credit_account_id,
        #        'journal_id': journal_id,
        #        'date': date_now,
        #        'debit': amount < 0.0 and -amount or 0.0,
        #        'credit': amount > 0.0 and amount or 0.0,
        #    }
        #    vals = {
        #        'name': f'DIS / {reference}',
        #        'narration': reference,
        #        'ref': reference,
        #        'journal_id': journal_id,
        #        'date': date_now,
        #        'line_ids': [(0, 0, debit_vals), (0, 0, credit_vals)]
        #    }
        #    move = self.env['account.move'].create(vals)
        #    move.action_post()
        #return True

    def action_close_loan(self):
        """Closing the loan"""
        demo = []
        for check in self.repayment_lines_ids:
            if check.state == 'unpaid':
                demo.append(check)
        if len(demo) >= 1:
            message_id = self.env['message.popup'].create(
                {'message': _("Pagos pendientes")})
            return {
                'name': _('Pagos'),
                'type': 'ir.actions.act_window',
                'view_mode': 'form',
                'res_model': 'message.popup',
                'res_id': message_id.id,
                'target': 'new'
            }
        self.write({'state': "closed"})

    def action_loan_rejected(self):
        """You can add reject reasons here"""
        return {'type': 'ir.actions.act_window',
                'name': 'Rechazo del plan',
                'res_model': 'reject.reason',
                'target': 'new',
                'view_mode': 'form',
                'context': {'default_loan': self.name}
                }

    def action_compute_repayment(self):
        """This automatically create the installment the employee need to pay to
        company based on payment start date and the no of installments.
            """
        self.request = True
        #self.loan_amount_total=0
        for loan in self:
            loan.repayment_lines_ids.unlink()
            """ if (loan.loan_type_id.tenure_plan=='monthly'):
                date_start = (datetime.strptime(str(loan.date),
                                            '%Y-%m-%d') +
                          relativedelta(months=1))
            elif(loan.loan_type_id.tenure_plan=='biweekly'):
                date_start = (datetime.strptime(str(loan.date),
                                            '%Y-%m-%d') +
                          relativedelta(weeks=2))
            elif(loan.loan_type_id.tenure_plan=='weekly'):
                date_start = (datetime.strptime(str(loan.date),
                                            '%Y-%m-%d') +
                          relativedelta(weeks=1))    """
            date_start = loan.date
            _logger.info("VALUE REWARD AMOUNT DISCOUNT fecha %s", date_start)
            #amount = (loan.loan_amount-loan.entry_amount) / loan.tenure
            #amount = (loan.disbursal_amount) / loan.tenure
            amount_per_installment = (loan.disbursal_amount) / loan.tenure
            amount_per_installment = round(amount_per_installment, 2)
            _logger.info(" VALUE REWARD amount_per_installment  %s", amount_per_installment )
            #interest = (loan.loan_amount-loan.entry_amount) * loan.interest_rate
            #interest = (loan.disbursal_amount) * loan.interest_rate
            #interest_amount = interest / loan.tenure 
            #_logger.info("VALUE REWARD AMOUNT DISCOUNT  interest_amoun%s", interest_amount)
            total_amount = 0
            
            partner = self.partner_id
            #loan.loan_amount_total+=total_amount
            for rand_num in range(1, loan.tenure ):
                self.env['repayment.line'].create({
                    'name': f"{loan.name}/{rand_num}",
                    'partner_id': partner.id,
                    'date': date_start,
                    'amount': 0.00,
                    'interest_amount': 0.00,
                    'total_amount': amount_per_installment ,
                    'interest_account_id': loan.loan_type_id.interes_account_id.id,
                    #self.env.ref('advanced_loan_management.'
                    #                                    'loan_management_'
                    #                                   'inrst_accounts').id,
                    'repayment_account_id': loan.loan_type_id.cobros_account_id.id,
                    #self.env.ref('advanced_loan_management.'
                    #                                    'demo_'
                    #                                     'loan_accounts').id,
                    'loan_id': loan.id})
                #date_start += relativedelta(months=1)
                if (loan.loan_type_id.tenure_plan=='monthly'):
                    date_start += relativedelta(months=1)
                elif(loan.loan_type_id.tenure_plan=='biweekly'):
                    date_start += relativedelta(weeks=2)
                elif(loan.loan_type_id.tenure_plan=='weekly'):
                   date_start += relativedelta(weeks=1) 
                total_amount += amount_per_installment
            #total_amount = amount_per_installment * (loan.tenure - 1)

            total_amount_1 = round(total_amount, 2)

            _logger.info("VALUE REWARD AMOUNT DISCOUNT  total_amount %s", total_amount_1)

            remaining_amount = loan.disbursal_amount - total_amount
            _logger.info("VALUE REWARD AMOUNT DISCOUNT  remaining_amountt %s", remaining_amount)
            _logger.info("VALUE REWARD AMOUNT DISCOUNT  remaining_amountt %s", loan.disbursal_amount)

            last_installment_name = f"{loan.name}/{loan.tenure}"
            last_installment_amount =  remaining_amount
            _logger.info("VALUE REWARD AMOUNT DISCOUNT  last_installment_amount t %s", last_installment_amount)

            self.env['repayment.line'].create({
                'name': last_installment_name,
                'partner_id': loan.partner_id.id,
                'date': date_start,
                'amount': 0.00,
                'interest_amount': 0.00,
                'total_amount': last_installment_amount,
                'interest_account_id': loan.loan_type_id.interes_account_id.id,
                'repayment_account_id': loan.loan_type_id.cobros_account_id.id,
                'loan_id': loan.id
            })
            
        return True

        
    def update_states_non_payment(self):
        _logger.info("ENTRAMOS AL CRON**** ")
        my_company = self.env.user.company_id
        repayment_line_model = self.env['repayment.line']
        # Obtener la zona horaria de Guayaquil
        local_tz = pytz.timezone('America/Guayaquil')
        # Obtener la fecha y hora actual en la zona horaria de Guayaquil
        fecha_actual = datetime.now(local_tz).date()
        _logger.info("Fecha actual en Guayaquil: %s", fecha_actual)
        # Buscar todas las líneas de pago impagas en la fecha actual y para la compañía actual
        repayment_lines = repayment_line_model.search([
            ('state', '=', 'unpaid'),
            ('date', '<=', fecha_actual),  # Asegurarse de que la fecha de vencimiento sea anterior o igual a la fecha actual
            ('company_id', '=', my_company.id)
        ])
        _logger.info("Líneas de pago encontradas: %d", len(repayment_lines))
        for repayment_line in repayment_lines:
            loan_request = repayment_line.loan_id
            _logger.info("Línea de pago: %s, Estado del préstamo: %s", repayment_line.id, loan_request.state)
            if loan_request.state == 'disbursed':
                _logger.info("Se actualiza el estado de la línea de pago %s a 'defeated'", repayment_line.id)
                repayment_line.write({'state': 'defeated'})
            else:
                _logger.info("La línea de pago %s no se actualiza porque el estado del préstamo es: %s", repayment_line.id, loan_request.state)