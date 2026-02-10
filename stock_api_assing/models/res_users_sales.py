# -*- coding: utf-8 -*-

from odoo import models, fields, api



class ResUsersSales(models.Model):
    _inherit = 'res.users'

    # Just for searching, you may have extra or duplicate area code.
    vendor_codes = fields.Char(
        string='Código de vendedor',
        help='Código de vendedor para radis'
    )
    
