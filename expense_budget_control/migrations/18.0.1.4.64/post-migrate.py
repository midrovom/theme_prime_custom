# -*- coding: utf-8 -*-
"""Eliminar el acceso rápido independiente en escritorio tras la actualización."""
from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    shortcut = env.ref('expense_budget_control.menu_expense_budget_mobile_home', raise_if_not_found=False)
    if shortcut:
        shortcut.sudo().write({'active': False})
