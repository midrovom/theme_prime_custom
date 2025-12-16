from odoo.addons.website_sale.controllers.main import WebsiteSale


class WebsiteSaleFilterAttribute(WebsiteSale):

    def _get_shop_values(self, category, search, **kwargs):
        values = super()._get_shop_values(category, search, **kwargs)

        attributes = values.get('attributes')
        if attributes:
            # Forzar carga del campo
            attributes.read(['filter_attribute'])

            # Filtrar SOLO los marcados
            values['attributes'] = attributes.filtered(
                lambda a: a.filter_attribute
            )

        return values
