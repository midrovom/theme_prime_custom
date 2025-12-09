# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request

class WebsiteSaleBrand(http.Controller):

    @http.route(['/website_sale/get_products_by_brand'], type='json', auth='public', website=True)
    def get_dynamic_snippet_brand(
        self,
        filter_id=None,
        product_brand_id=None,
        limit=16,
        search_domain=None,
        with_sample=False
    ):
        """
        Devuelve productos filtrados por marca para el snippet dinámico.
        """
        Product = request.env["product.product"].sudo()
        domain = [("website_published", "=", True)]

        if search_domain:
            domain += search_domain

        # Marca seleccionada
        if product_brand_id and product_brand_id not in ("all", "current"):
            try:
                product_brand_id = int(product_brand_id)
                domain.append(
                    ("product_template_attribute_value_ids.attribute_value_id", "=", product_brand_id)
                )
            except:
                pass

        # Filtro dinámico si viene uno asignado
        if filter_id:
            filter_sudo = request.env["website.snippet.filter"].sudo().browse(int(filter_id))
            if filter_sudo.exists():
                domain += filter_sudo._get_eval_domain()

        products = Product.search(domain, limit=limit)

        # Preparar salida
        records = []
        for prod in products:
            records.append({
                "_record": prod,
                "id": prod.id,
                "display_name": prod.display_name,
                "image_512": prod.image_512
                    and f"/web/image/product.product/{prod.id}/image_512"
                    or "/web/static/img/placeholder.png",
                "brand": prod.dr_brand_value_id.name if prod.dr_brand_value_id else "",
            })

        return {
            "records": records,
            "is_sample": with_sample,
        }


class WebsiteBrandFilter(http.Controller):

    @http.route(['/website_sale/brand_filter'], type='json', auth='public', website=True)
    def get_brand_filter(self, filter_name="Productos por Marca"):
        """
        Crea o devuelve el filtro dinámico del snippet de marca.
        """
        domain = [
            ('name', '=', filter_name),
            ('model_name', '=', 'product.product'),
            ('website_id', 'in', (False, request.website.id)),
        ]

        brand_filter = request.env["website.snippet.filter"].sudo().search(domain, limit=1)

        if not brand_filter:
            brand_filter = request.env["website.snippet.filter"].sudo().create({
                "name": filter_name,
                "model_name": "product.product",
                "field_names": "display_name,image_512",
                "limit": 16,
                "website_id": request.website.id,
                "action_server_id": request.env.ref(
                    "conedera_theme_common.dynamic_snippet_products_by_brand_action"
                ).id,
            })

        return brand_filter.id
