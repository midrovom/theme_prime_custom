# -*- coding: utf-8 -*-
"""Guardia de warehouse_id para sale.order.line.

El cliente PWA guarda warehouse_id en sale.order pero en algunas versiones no
lo incluye en los comandos de order_line. stock_api_assing intenta recuperar la
bodega desde la orden en sale.order.line.create(); durante un create anidado,
ese valor puede no estar disponible antes del INSERT SQL, cuando en la BD
sale_order_line.warehouse_id es NOT NULL.

La solucion no cambia reglas de stock ni los permisos: solo propaga la bodega
que ya ha sido seleccionada en la propia orden.
"""
from odoo import api, models

from .warehouse_commands import add_warehouse_to_new_lines


class SaleOrder(models.Model):
    _inherit = "sale.order"

    @api.model_create_multi
    def create(self, vals_list):
        updated = []
        for vals in vals_list:
            values = dict(vals)
            wh_id = values.get("warehouse_id")
            if wh_id and "order_line" in values:
                values["order_line"] = add_warehouse_to_new_lines(
                    values["order_line"], wh_id
                )
            updated.append(values)
        return super().create(updated)

    def write(self, vals):
        # Cuando un write anade comandos CREATE a una orden existente, su
        # bodega ya esta disponible. Para recordsets multiples se hace por
        # registro cuando los comandos implican lineas nuevas y no se ha
        # especificado una bodega en vals.
        if "order_line" not in vals:
            return super().write(vals)
        specified_wh_id = vals.get("warehouse_id")
        if specified_wh_id:
            values = dict(vals)
            values["order_line"] = add_warehouse_to_new_lines(
                values["order_line"], specified_wh_id
            )
            return super().write(values)
        # Las actualizaciones de varias ordenes deben mantener la bodega
        # independiente de cada orden, sin atribuir una bodega ajena.
        result = True
        for order in self:
            values = dict(vals)
            if order.warehouse_id:
                values["order_line"] = add_warehouse_to_new_lines(
                    values["order_line"], order.warehouse_id.id
                )
            result = super(SaleOrder, order).write(values) and result
        return result


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    @api.model_create_multi
    def create(self, vals_list):
        updated = []
        for vals in vals_list:
            values = dict(vals)
            if not values.get("warehouse_id") and values.get("order_id"):
                order = self.env["sale.order"].browse(values["order_id"]).exists()
                if order and order.warehouse_id:
                    values["warehouse_id"] = order.warehouse_id.id
            updated.append(values)
        return super().create(updated)
