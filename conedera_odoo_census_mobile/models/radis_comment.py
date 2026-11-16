# -*- coding: utf-8 -*-
"""Adaptador de comentario Radis exclusivo para cotizaciones creadas/gestionadas por la PWA.

No depende de stock_api_assing. Si su método extract_plain_text() está presente,
la herencia devuelve la referencia cliente solo para órdenes explícitamente
marcadas; las demás conservan el método original que lee sale.order.note.
"""

from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    catastro_pwa_origin = fields.Boolean(
        string="Proforma originada en PWA",
        default=False,
        copy=False,
        readonly=True,
        index=True,
        help="Identifica cotizaciones creadas o editadas en la PWA; "
             "no modifica la nota ni la referencia original.",
    )

    def extract_plain_text(self):
        self.ensure_one()
        if self.catastro_pwa_origin:
            return (self.client_order_ref or "").strip()
        return super().extract_plain_text()
