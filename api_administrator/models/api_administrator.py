# -*- coding: utf-8 -*-


import logging

from odoo import models, fields, api

_logger = logging.getLogger(__name__)



class ApiAdministrator(models.Model):
    _name = 'api.administrator'
    _description = 'api_administrator'

    name = fields.Char(string='Nombre',help='Hacer referencia del modelo en que se va ejecutar')
    url = fields.Char(string='Url',)
    end_point = fields.Char(string='End Point',)
    user_id = fields.Char(string='Usuario Api',)
    password = fields.Char(string='Password',)
    flag = fields.Selection([("D", "Diario"), ("H", "Horas"), ("M", "Mensual"), ("A", "Anual")], 
                            default="H",
                            help='Si el crom llama a la funcion en diferente periodos diario o por horas')
    description = fields.Text(string='Nota',)
    type = fields.Selection([("post", "post"), ("get", "get"), ("put", "put"), ("delete", "delete")], default="get")
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                default=lambda self: self.env.user.company_id)
    
    is_stock_update = fields.Boolean(string='¿Es para actualización de stock?', default=False)

    status = fields.Selection(
        selection=[
            ("A", "Activado"),
            ("D", "Desactivado"),
        ],
        string="Estado",
        copy=False,
        default="A",
        index=True
    )

    price_list_id = fields.Many2one('product.pricelist', string='Lista de Precios',
                                    help='Seleccione la lista de precios asociada a esta API si aplica.')
    
    warehouse_id = fields.Many2one(
        'stock.warehouse', 
        string='Bodega Relacionada',
        domain="[('company_id', '=', company_id)]",
        ondelete='restrict',
        help='Seleccione una bodega relacionada que pertenezca a la misma empresa configurada en la API.'
    )
