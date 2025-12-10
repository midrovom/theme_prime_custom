from odoo.addons.website_sale.controllers.main import WebsiteSale

class WebsiteSaleBrand(WebsiteSale):

    def _get_search_options(
        self, category=None, attrib_values=None, tags=None,
        min_price=0.0, max_price=0.0, conversion_rate=1, **post
    ):
        # Llamamos al original para no perder funcionalidad
        options = super()._get_search_options(
            category=category,
            attrib_values=attrib_values,
            tags=tags,
            min_price=min_price,
            max_price=max_price,
            conversion_rate=conversion_rate,
            **post
        )

        # 👇 añadimos nuestra opción de marca
        product_brand_id = post.get('productBrandId')
        if product_brand_id and product_brand_id != 'all':
            options['productBrandId'] = product_brand_id

        return options

    def _get_search_domain(self, options):
        domain = super()._get_search_domain(options)
        product_brand_id = options.get('productBrandId')
        if product_brand_id and product_brand_id != 'all':
            domain.append(('value_ids', '=', int(product_brand_id)))
        return domain

