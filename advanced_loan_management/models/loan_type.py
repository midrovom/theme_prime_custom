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
from odoo import api, fields, models


class LoanTypes(models.Model):
    """Create different types of Loans, And can wisely choose while requesting
     for loan"""
    _name = 'loan.type'
    _inherit = ['mail.thread']
    _description = 'Loan Type'

    name = fields.Char(string='Nombre', required=True, help="LoanType Name")

    #En este caso como el monto del préstamo lo va ha dar el valor del producto este campo queda como un valor maximo sugerido
    loan_amount = fields.Integer(string='Monto del préstamo', help="Monto del préstamo")
    tenure = fields.Integer(string='Plazo', default='1',
                            help="Periodo de amortización")
    #tenure_plan = fields.Char(string="Tenure Plan", default='monthly',
    #                          readonly='True', help="EMI payment plan")
    tenure_plan = fields.Selection(
        string='Plan',
        selection=[('weekly', 'Semanal'), ('biweekly', 'Quincenal'),
                   ('monthly', 'Mensual'),
                  ],
        required=True, readonly=False, copy=False,
        tracking=True, default='weekly', help="Planes de Crédito")
    interest_rate = fields.Float(string='Tasa de interés',
                                 help="tasa de interés del préstamo")
    entry_rate = fields.Float(string='Tasa de Entrada',
                                 help="Ingrese aqui la Tasa Recomendable de Entrada")
    """  disbursal_amount = fields.Float(string='Valor Maximo Recomendado',
                                    compute='_compute_disbursal_amount',
                                    help="Monto total a desembolsar") """
    documents_ids = fields.Many2many('loan.documents',
                                     string="Documentos",
                                     help="Documentos Rqueridos para el préstamo")
    processing_fee = fields.Integer(string="Cuoto Gastos Administrativos",
                                    help="Monto para inicializar el préstamo")
    note = fields.Text(string="Criterios", help="Criterios para aprobación"
                                               "loan requests")
    company_id = fields.Many2one('res.company', string='Company',
                                 readonly=True,
                                 help="Company Name",
                                 default=lambda self:
                                 self.env.company, )
    interes_account_id = fields.Many2one('account.account',
                                       string="Cuenta de Intereses",
                                       help="Seleccione la Cuenta Para  "
                                            "Cobro de Intereses")
    cobros_account_id = fields.Many2one('account.account',
                                        string="Cuentas de Cobros",
                                        help="Seleccione la Cuenta Para  "
                                             "Los Cobros de los Creditos")

    """  @api.depends('processing_fee')
    def _compute_disbursal_amount(self):
        #Calculating amount for disbursing
        self.disbursal_amount = self.loan_amount - self.processing_fee """

