from odoo import http
from odoo.http import request
from odoo.tools import formatLang

class WebsiteProductOfferController(http.Controller):

    @http.route("/shop/offer/add", type="json", auth="public", website=True)
    def shop_offer_add(self, **kwargs):
        product_id = int(kwargs.get("product_id") or 0)
        quantity = float(kwargs.get("quantity") or 0)
        offered_price = float(kwargs.get("offered_price") or 0)

        if not product_id or quantity <= 0 or offered_price <= 0:
            return {"ok": False, "error": "Datos inválidos."}

        product = request.env["product.product"].sudo().browse(product_id)
        if not product.exists():
            return {"ok": False, "error": "El producto no existe."}

        offer_cart = list(request.session.get("wpo_offer_cart", []))

        existing_line = next((line for line in offer_cart if int(line.get("product_id")) == product.id), None)
        if existing_line:
            existing_line.update({
                "quantity": quantity,
                "offered_price": offered_price,
                "total": quantity * offered_price,
                "offered_price_formatted": formatLang(request.env, offered_price, currency_obj=product.currency_id),
                "total_formatted": formatLang(request.env, quantity * offered_price, currency_obj=product.currency_id),
            })
        else:
            offer_cart.append({
                "product_id": product.id,
                "product_name": product.display_name,
                "quantity": quantity,
                "offered_price": offered_price,
                "total": quantity * offered_price,
                "list_price": product.lst_price,
                "list_price_formatted": formatLang(request.env, product.lst_price, currency_obj=product.currency_id),
                "offered_price_formatted": formatLang(request.env, offered_price, currency_obj=product.currency_id),
                "total_formatted": formatLang(request.env, quantity * offered_price, currency_obj=product.currency_id),
                "website_url": product.website_url,
            })

        request.session["wpo_offer_cart"] = offer_cart
        request.session.modified = True

        return {"ok": True, "redirect": "/shop/offer/cart", "count": len(offer_cart)}

    @http.route("/shop/offer/cart", type="http", auth="public", website=True)
    def shop_offer_cart(self):
        offer_cart = request.session.get("wpo_offer_cart", [])
        total = sum(line["total"] for line in offer_cart)
        offer_cart_summary = {
            "total_formatted": formatLang(request.env, total, currency_obj=request.website.currency_id),
        }
        return request.render("website_product_offer.offer_cart", {
            "offer_cart": offer_cart,
            "offer_cart_summary": offer_cart_summary,
        })

    @http.route("/shop/offer/submit", type="json", auth="public", website=True)
    def shop_offer_submit(self, **kwargs):
        offer_cart = request.session.get("wpo_offer_cart", [])
        if not offer_cart:
            return {"ok": False, "error": "No tienes productos en tu oferta."}

        contact_name = (kwargs.get("contact_name") or "").strip()
        contact_email = (kwargs.get("contact_email") or "").strip()
        contact_phone = (kwargs.get("contact_phone") or "").strip()
        company_name = (kwargs.get("company_name") or "").strip()
        customer_message = (kwargs.get("customer_message") or "").strip()

        Offer = request.env["website.sale.offer"].sudo()
        offer = Offer.create({
            "website_id": request.website.id,
            "company_id": request.website.company_id.id,
            "pricelist_id": request.website.pricelist_id.id,
            "contact_name": contact_name,
            "contact_email": contact_email,
            "contact_phone": contact_phone,
            "company_name": company_name,
            "customer_message": customer_message,
            "valid_until": Offer._default_valid_until(request.website),
            "source_url": "/shop/offer/cart",
        })

        OfferLine = request.env["website.sale.offer.line"].sudo()
        for item in offer_cart:
            product = request.env["product.product"].sudo().browse(int(item["product_id"]))
            if not product.exists():
                continue
            OfferLine.create({
                "offer_id": offer.id,
                "product_id": product.id,
                "quantity": float(item["quantity"]),
                "list_price": float(item["list_price"]),
                "offered_price": float(item["offered_price"]),
                "available_qty_snapshot": product.qty_available,
            })

        request.session.pop("wpo_offer_cart", None)
        request.session.modified = True

        return {
            "ok": True,
            "reference": offer.name,
            "portal_url": offer.get_portal_url(),
            "message": "Tu oferta fue enviada correctamente.",
        }
