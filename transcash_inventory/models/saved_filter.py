# -*- coding: utf-8 -*-
"""Favoritos persistentes del dashboard, por usuario y compañía de Odoo."""
from odoo import fields, models


class TranscashInventorySavedFilter(models.Model):
    _name = 'transcash.inventory.saved.filter'
    _description = 'Filtro guardado de Inventario Inteligente'
    _order = 'is_default desc, name asc, id asc'

    name = fields.Char(string='Nombre del filtro', required=True, index=True)
    user_id = fields.Many2one('res.users', string='Creado por', required=True,
                              index=True, ondelete='cascade', default=lambda self: self.env.user)
    company_id = fields.Many2one('res.company', string='Empresa', required=True,
                                 index=True, ondelete='cascade', default=lambda self: self.env.company)
    filter_json = fields.Text(string='Criterios de filtro (JSON)', required=True)
    is_default = fields.Boolean(string='Aplicar automáticamente', default=False)
    is_shared = fields.Boolean(string='Compartir con otros usuarios de la empresa', default=False)

    _sql_constraints = [
        ('user_company_name_unique', 'unique(user_id,company_id,name)',
         'Ya existe un filtro con ese nombre para este usuario y empresa.'),
    ]
