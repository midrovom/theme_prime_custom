# -*- coding: utf-8 -*-
"""Installable Control de Gastos entry point using Odoo 18's native PWA.

The dedicated manifest has its own app identity and icons. We intentionally DO
NOT register a second service worker, which would conflict with Odoo's own worker
and risk caching protected accounting pages or POST responses.
"""
import json

from odoo import http
from odoo.http import request


class ExpenseBudgetPWA(http.Controller):
    @http.route('/expense-budget/pwa/manifest.webmanifest', type='http', auth='public', methods=['GET'], csrf=False)
    def pwa_manifest(self, **kwargs):
        icon_root = '/expense_budget_control/static/pwa/'
        manifest = {
            'id': '/expense-budget/pwa/launch',
            'name': 'Control de Gastos',
            'short_name': 'Gastos',
            'description': 'Presupuestos, consumos y reportes de gastos',
            'lang': 'es',
            'start_url': '/expense-budget/pwa/launch',
            'scope': '/',
            'display': 'standalone',
            'background_color': '#f4f8fb',
            'theme_color': '#204c68',
            'icons': [
                {'src': icon_root + 'icon-192.png', 'sizes': '192x192', 'type': 'image/png', 'purpose': 'any maskable'},
                {'src': icon_root + 'icon-512.png', 'sizes': '512x512', 'type': 'image/png', 'purpose': 'any maskable'},
            ],
        }
        return request.make_response(
            json.dumps(manifest, ensure_ascii=False),
            headers=[('Content-Type', 'application/manifest+json; charset=utf-8'), ('Cache-Control', 'public, max-age=3600')],
        )

    @http.route('/expense-budget/pwa', type='http', auth='public', methods=['GET'], csrf=False)
    def pwa_install_page(self, **kwargs):
        # No Odoo data is rendered here: this is just an install/launch screen.
        return request.make_response(
            '<!DOCTYPE html>\n' + request.env['ir.ui.view']._render_template('expense_budget_control.pwa_install_page'),
            headers=[('Content-Type', 'text/html; charset=utf-8'), ('Cache-Control', 'no-store')],
        )

    @http.route('/expense-budget/pwa/launch', type='http', auth='user', methods=['GET'], csrf=False)
    def pwa_launch(self, **kwargs):
        allowed_groups = (
            'expense_budget_control.group_expense_budget_user',
            'expense_budget_control.group_expense_budget_registrar',
            'expense_budget_control.group_expense_budget_approver',
            'expense_budget_control.group_expense_budget_manager',
        )
        if not any(request.env.user.has_group(xmlid) for xmlid in allowed_groups):
            return request.redirect('/web')
        # Odoo 18 path-based routing. Always use the current database's action ID.
        action = request.env.ref('expense_budget_control.action_expense_budget_mobile_home')
        return request.redirect('/odoo/action-%d' % action.id)
