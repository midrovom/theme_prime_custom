# -*- coding: utf-8 -*-
"""Desactivar el enlace antiguo Gestionar rubros al actualizar desde v1.4.64."""
from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    old_menu = env.ref('expense_budget_control.menu_expense_budget_rubros_registrar',
                       raise_if_not_found=False)
    if old_menu:
        old_menu.sudo().write({'active': False})
