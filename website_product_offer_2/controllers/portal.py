from odoo import _, http
from odoo.exceptions import AccessError, MissingError, UserError
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager


class CustomerPortalOffers(CustomerPortal):
    def _offer_domain(self):
        partner = request.env.user.partner_id.commercial_partner_id
        return [("partner_id", "child_of", partner.id)]

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if "offer_count" in counters:
            values["offer_count"] = request.env["website.sale.offer"].sudo().search_count(
                self._offer_domain()
            )
        return values

    @http.route(
        ["/my/offers", "/my/offers/page/<int:page>"],
        type="http",
        auth="user",
        website=True,
    )
    def portal_my_offers(self, page=1, sortby="date", **kwargs):
        values = self._prepare_portal_layout_values()
        domain = self._offer_domain()
        sortings = {
            "date": {"label": _("Más recientes"), "order": "create_date desc"},
            "name": {"label": _("Referencia"), "order": "name desc"},
            "state": {"label": _("Estado"), "order": "state, create_date desc"},
        }
        sortby = sortby if sortby in sortings else "date"
        Offer = request.env["website.sale.offer"].sudo()
        offer_count = Offer.search_count(domain)
        pager = portal_pager(
            url="/my/offers",
            url_args={"sortby": sortby},
            total=offer_count,
            page=page,
            step=self._items_per_page,
        )
        offers = Offer.search(
            domain,
            order=sortings[sortby]["order"],
            limit=self._items_per_page,
            offset=pager["offset"],
        )
        values.update(
            {
                "offers": offers,
                "page_name": "offer",
                "pager": pager,
                "default_url": "/my/offers",
                "searchbar_sortings": sortings,
                "sortby": sortby,
            }
        )
        return request.render("website_product_offer_2.portal_my_offers", values)

    def _check_offer_access(self, offer_id, access_token=None):
        return self._document_check_access(
            "website.sale.offer",
            offer_id,
            access_token=access_token,
        )

    def _offer_page_values(self, offer, access_token=None, error=None):
        return {
            "offer": offer,
            "page_name": "offer",
            "access_token": access_token,
            "error": error,
        }

    @http.route(
        "/my/offers/<int:offer_id>",
        type="http",
        auth="public",
        website=True,
    )
    def portal_offer_page(self, offer_id, access_token=None, **kwargs):
        try:
            offer = self._check_offer_access(offer_id, access_token)
        except (AccessError, MissingError):
            return request.redirect("/my")
        return request.render(
            "website_product_offer_2.portal_offer_page",
            self._offer_page_values(offer, access_token),
        )

    @http.route(
        "/my/offers/<int:offer_id>/accept-counter",
        type="http",
        auth="public",
        methods=["POST"],
        website=True,
        csrf=True,
    )
    def portal_offer_accept_counter(self, offer_id, access_token=None, **kwargs):
        try:
            offer = self._check_offer_access(offer_id, access_token)
        except (AccessError, MissingError):
            return request.redirect("/my")
        try:
            offer.sudo().action_customer_accept_counter()
        except UserError as error:
            return request.render(
                "website_product_offer_2.portal_offer_page",
                self._offer_page_values(offer, access_token, str(error)),
            )
        return request.redirect(offer.get_portal_url())

    @http.route(
        "/my/offers/<int:offer_id>/cancel",
        type="http",
        auth="public",
        methods=["POST"],
        website=True,
        csrf=True,
    )
    def portal_offer_cancel(self, offer_id, access_token=None, **kwargs):
        try:
            offer = self._check_offer_access(offer_id, access_token)
        except (AccessError, MissingError):
            return request.redirect("/my")
        try:
            offer.sudo().action_customer_cancel()
        except UserError as error:
            return request.render(
                "website_product_offer_2.portal_offer_page",
                self._offer_page_values(offer, access_token, str(error)),
            )
        return request.redirect(offer.get_portal_url())

