# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request


class DynamicSnippetProductsBrand(http.Controller):

    @http.route(
        '/dynamic_snippet_products/brand',
        type='json', auth='public', website=True
    )
    def dynamic_snippet_products_brand(self, **kwargs):

        # Recibir parámetros desde JS
        product_brand_id = kwargs.get('productBrandId')
        limit = kwargs.get('limit', 8)
        domain = kwargs.get('domain', [])

        # Convertir el dominio del snippet en objeto Python
        if isinstance(domain, str):
            try:
                domain = request.env[domain]
            except Exception:
                domain = []

        # Agregar dominio de marca
        if product_brand_id and product_brand_id != "all":
            domain.append(("value_ids", "=", int(product_brand_id)))

        products = request.env["product.template"].sudo().search(domain, limit=limit)

        return request.env["ir.ui.view"]._render_template(
            "website.s_dynamic_snippet_products",
            {"products": products}
        )
