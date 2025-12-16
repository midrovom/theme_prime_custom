# Controlador para check de atributos
from odoo.addons.website_sale.controllers.main import WebsiteSale

class WebsiteSaleFilterAttribute(WebsiteSale):

    def _get_shop_values(self, category, search, **kwargs):
        values = super()._get_shop_values(category, search, **kwargs)

        attributes = values.get('attributes')
        if attributes:
            attributes.read(['filter_attribute'])

        return values
