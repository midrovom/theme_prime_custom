# -*- coding: utf-8 -*-
"""Consolidar ajustes antiguos sin perder la selección de API de centros.

Las vistas del modelo heredado permanecen desactivadas y el modelo se conserva
para no borrar datos de instalaciones anteriores.
"""
from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    old_configs = env['expense.budget.cost.center.api.config'].sudo().search([])
    unified = env['expense.budget.api.config'].sudo()
    for old in old_configs:
        config = unified.search([('company_id', '=', old.company_id.id)], limit=1)
        if config:
            if not config.center_catalog_api_id and old.api_administrator_id:
                config.write({'center_catalog_api_id': old.api_administrator_id.id})
        elif old.api_administrator_id:
            unified.with_company(old.company_id).create({
                'company_id': old.company_id.id,
                'center_catalog_api_id': old.api_administrator_id.id,
            })
    legacy_menu = env.ref('expense_budget_control.menu_expense_budget_cost_center_api',
                          raise_if_not_found=False)
    if legacy_menu:
        legacy_menu.sudo().write({'active': False})

    # Desactivar las vistas del formulario antiguo para instalaciones que saltan
    # directamente desde una versión anterior a 1.4.61. No borrar datos.
    for xml_id in ('view_expense_budget_cost_center_api_form',
                   'view_expense_budget_cost_center_api_list'):
        old_view = env.ref('expense_budget_control.' + xml_id,
                           raise_if_not_found=False)
        if old_view:
            old_view.sudo().write({'active': False})
