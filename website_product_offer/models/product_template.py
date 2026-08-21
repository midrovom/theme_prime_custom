from odoo import models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    def _website_offer_rule(self, website):
        self.ensure_one()
        return self.env["website.product.offer.rule"].sudo().search(
            [
                ("website_id", "=", website.id),
                ("product_tmpl_id", "=", self.id),
                ("active", "=", True),
            ],
            limit=1,
        )

    def _website_offer_available_qty(self, website, product=None):
        self.ensure_one()
        product = product or self.product_variant_id
        if not product:
            return 0.0
        product = product.sudo().with_company(website.company_id)
        website_qty_method = getattr(website, "_get_product_available_qty", None)
        if website_qty_method:
            return max(0.0, website_qty_method(product))
        warehouse = website._get_warehouse_available()
        warehouse_id = getattr(warehouse, "id", warehouse)
        return max(
            0.0,
            product.with_context(warehouse=warehouse_id).free_qty,
        )

    def _website_offer_is_enabled(self, website):
        self.ensure_one()
        website = website.sudo()
        if not website.offer_enabled or not self.sale_ok:
            return False
        if website.offer_product_scope == "selected" and not self._website_offer_rule(website):
            return False
        if website.offer_in_stock_only:
            return any(
                self._website_offer_available_qty(website, variant) > 0
                for variant in self.sudo().product_variant_ids
            )
        return True
