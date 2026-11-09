# -*- coding: utf-8 -*-
"""Serialización pequeña y comprobable, sin importaciones de Odoo.

No modifica el JSON original: copia las órdenes y líneas y añade
los porcentajes por producto y el código ERP de la forma de pago en cabecera.
"""
from math import isclose


class PayloadMismatch(ValueError):
    """La carga no corresponde a las líneas actuales del pedido."""


def _num(value, label):
    try:
        return float(value)
    except (ValueError, TypeError) as exc:
        raise PayloadMismatch('Campo numérico inválido: %s' % label) from exc


def enrich_payload(payload, find_order):
    result = []
    for order_data in payload:
        order = find_order(order_data['order_name'])
        # Usar exactamente el mismo filtro y orden que el módulo original
        # `stock_api_assing` en botón manual y en cron.
        lines = order.order_line.filtered(lambda l: l.product_id and not l.display_type)
        sent = order_data['order_lines']
        if len(lines) != len(sent):
            raise PayloadMismatch('Cantidad de líneas distinta en %s.' % order_data['order_name'])
        new_lines = []
        for position, (line, item) in enumerate(zip(lines, sent), 1):
            if not isinstance(item, dict):
                raise PayloadMismatch('Línea %s con formato inválido.' % position)
            expected_wh = (line.warehouse_id or order.warehouse_id).code
            if (
                str(item.get('sku') or '') != str(line.product_id.default_code or '')
                or str(item.get('order_location_wh') or '') != str(expected_wh or '')
                or not isclose(_num(item.get('quantity'), 'quantity'),
                               float(line.product_uom_qty), rel_tol=1e-9, abs_tol=1e-6)
                or not isclose(_num(item.get('price_unit'), 'price_unit'),
                               float(line.price_unit), rel_tol=1e-9, abs_tol=1e-6)
            ):
                raise PayloadMismatch('Producto/cantidad/bodega/precio no coincide en línea %s de %s.' % (
                    position, order_data['order_name']))
            enriched = dict(item)
            enriched.update(order._catastro_radis_line_percentages(line))
            new_lines.append(enriched)
        enriched_order = dict(order_data)
        enriched_order['order_lines'] = new_lines
        # Valor de CABECERA, no una propiedad de las líneas.
        # Mantener intactas las órdenes nativas sin una opción de pago PWA;
        # para opciones configuradas, el método de Odoo valida el código ERP.
        erp_payment_code = order._catastro_radis_payment_erp_code()
        if erp_payment_code is not None:
            enriched_order['order_payment_code'] = erp_payment_code
        result.append(enriched_order)
    return result
