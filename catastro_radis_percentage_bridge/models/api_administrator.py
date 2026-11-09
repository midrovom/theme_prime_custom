# -*- coding: utf-8 -*-
"""Extensión sin modificar stock_api_assing ni duplicar su cliente HTTP.

Ambos caminos del módulo original (botón manual y cron) construyen su JSON
antes de llamar a `api.administrator.call_api`. Interceptar ese punto común
permite añadir porcentajes sin copiar ni sustituir ninguna rutina de Radis.
"""
import logging

from odoo import models, _
from odoo.exceptions import ValidationError

from ..radis_payload import enrich_payload, PayloadMismatch

_logger = logging.getLogger(__name__)


class APIAdministrator(models.Model):
    _inherit = 'api.administrator'

    def call_api(self, api_name, method='get', company_id=1, params=None, headers_extra=None):
        # Intervenir únicamente en el endpoint original de cotizaciones Radis.
        # Nunca se modifican las llamadas de stock, precios u otras APIs.
        if api_name == 'check_update_qoutes' and str(method).lower() == 'post':
            try:
                params = self._catastro_radis_enrich_quotes(params, company_id)
            except PayloadMismatch as exc:
                _logger.warning('Radis: exportación detenida para evitar porcentajes incorrectos: %s', exc)
                raise ValidationError(_(
                    'No se pudo verificar la correspondencia de las líneas de la '
                    'cotización para enviar descuentos e incrementos a Radis: %s'
                ) % exc) from exc
        return super().call_api(
            api_name, method=method, company_id=company_id,
            params=params, headers_extra=headers_extra,
        )

    def _catastro_radis_enrich_quotes(self, params, company_id):
        # Los llamados no estándar no se alteran.
        if not isinstance(params, list) or not params:
            return params
        if not all(isinstance(item, dict) and 'order_name' in item and
                   isinstance(item.get('order_lines'), list) for item in params):
            return params
        try:
            company = int(company_id)
        except (TypeError, ValueError) as exc:
            raise PayloadMismatch('Empresa inválida en la exportación de cotizaciones.') from exc
        if not company:
            raise PayloadMismatch('La empresa no está definida.')
        Sale = self.env['sale.order'].sudo()

        def find_order(order_name):
            orders = Sale.search([
                ('name', '=', order_name), ('company_id', '=', company),
            ], limit=2)
            if len(orders) != 1:
                raise PayloadMismatch('La orden %s no está identificada de forma única en su empresa.' % order_name)
            return orders

        return enrich_payload(params, find_order)
