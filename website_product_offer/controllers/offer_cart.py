from odoo import http
from odoo.http import request

class WebsiteProductOfferController(http.Controller):

    # @http.route("/shop/offer/add", type="json", auth="public", website=True)
    # def shop_offer_add(self, **kwargs):
    #     product_id = int(kwargs.get("product_id") or 0)
    #     quantity = float(kwargs.get("quantity") or 0)
    #     offered_price = float(kwargs.get("offered_price") or 0)

    #     if not product_id or quantity <= 0 or offered_price <= 0:
    #         return {"ok": False, "error": "Datos inválidos."}

    #     product = request.env["product.product"].sudo().browse(product_id)
    #     if not product.exists():
    #         return {"ok": False, "error": "El producto no existe."}

    #     offer_cart = list(request.session.get("wpo_offer_cart", []))
    #     total_line = quantity * offered_price

    #     existing_line = next((line for line in offer_cart if int(line.get("product_id")) == product.id), None)
    #     if existing_line:
    #         existing_line.update({
    #             "quantity": quantity,
    #             "offered_price": offered_price,
    #             "total": total_line,
    #             "contact_name": kwargs.get("contact_name"),
    #             "contact_email": kwargs.get("contact_email"),
    #             "contact_phone": kwargs.get("contact_phone"),
    #         })
    #     else:
    #         offer_cart.append({
    #             "product_id": product.id,
    #             "product_name": product.display_name,
    #             "quantity": quantity,
    #             "offered_price": offered_price,
    #             "total": total_line,
    #             "list_price": product.lst_price,
    #             "website_url": product.website_url,
    #             "contact_name": kwargs.get("contact_name"),
    #             "contact_email": kwargs.get("contact_email"),
    #             "contact_phone": kwargs.get("contact_phone"),
    #         })

    #     request.session["wpo_offer_cart"] = offer_cart
    #     request.session.modified = True
    #     total_cart = sum(line["total"] for line in offer_cart)

    #     return {
    #         "ok": True,
    #         "redirect": "/shop/offer/cart",
    #         "count": len(offer_cart),
    #         "total": total_cart,
    #     }

    @http.route("/shop/offer/add", type="json", auth="public", website=True)
    def shop_offer_add(self, **kwargs):
        product_id = int(kwargs.get("product_id") or 0)
        quantity = self._number(kwargs.get("quantity"))
        offered_price = self._number(kwargs.get("offered_price"))

        if not product_id or quantity <= 0 or offered_price <= 0:
            return {"ok": False, "error": _("Datos inválidos.")}

        data = self._get_product_data(product_id)
        if not data["ok"]:
            return data
        website = data["website"]

        # Validaciones por producto
        if quantity < data["min_qty"]:
            return {
                "ok": False,
                "error": _("La cantidad mínima para este producto es %(quantity)s.", quantity=data["min_qty"]),
            }
        if data["max_qty"] and quantity > data["max_qty"]:
            return {
                "ok": False,
                "error": _("La cantidad máxima disponible es %(quantity)s.", quantity=data["max_qty"]),
            }
        if offered_price <= 0:
            return {"ok": False, "error": _("Ingresa un precio unitario válido.")}

        pricelist, list_price = self._get_list_price(website, data["product"], quantity)
        minimum_offer = list_price * data["minimum_price_percent"] / 100
        if minimum_offer and offered_price < minimum_offer:
            return {
                "ok": False,
                "error": _("La oferta está por debajo del mínimo permitido para este producto."),
            }

        product = data["product"]
        total_line = quantity * offered_price
        offer_cart = list(request.session.get("wpo_offer_cart", []))

        existing_line = next((line for line in offer_cart if int(line.get("product_id")) == product.id), None)
        if existing_line:
            existing_line.update({
                "quantity": quantity,
                "offered_price": offered_price,
                "total": total_line,
                "list_price": list_price,
                "contact_name": kwargs.get("contact_name"),
                "contact_email": kwargs.get("contact_email"),
                "contact_phone": kwargs.get("contact_phone"),
            })
        else:
            offer_cart.append({
                "product_id": product.id,
                "product_name": product.display_name,
                "quantity": quantity,
                "offered_price": offered_price,
                "total": total_line,
                "list_price": list_price,
                "website_url": product.website_url,
                "contact_name": kwargs.get("contact_name"),
                "contact_email": kwargs.get("contact_email"),
                "contact_phone": kwargs.get("contact_phone"),
            })

        request.session["wpo_offer_cart"] = offer_cart
        request.session.modified = True
        total_cart = sum(line["total"] for line in offer_cart)

        return {
            "ok": True,
            "redirect": "/shop/offer/cart",
            "count": len(offer_cart),
            "total": total_cart,
        }

    @http.route("/shop/offer/remove", type="json", auth="public", website=True)
    def shop_offer_remove(self, product_id=None, **kwargs):
        """Eliminar una línea del carrito de oferta por product_id"""
        if not product_id:
            return {"ok": False, "error": "Producto inválido."}

        offer_cart = list(request.session.get("wpo_offer_cart", []))
        new_cart = [line for line in offer_cart if int(line.get("product_id")) != int(product_id)]

        request.session["wpo_offer_cart"] = new_cart
        request.session.modified = True
        total_cart = sum(line["total"] for line in new_cart)

        return {"ok": True, "redirect": "/shop/offer/cart", "count": len(new_cart), "total": total_cart}

    @http.route("/shop/offer/cart", type="http", auth="public", website=True)
    def shop_offer_cart(self):
        offer_cart = request.session.get("wpo_offer_cart", [])
        total = sum(line["total"] for line in offer_cart)
        offer_cart_summary = {
            "total": total,
        }
        return request.render("website_product_offer.offer_cart", {
            "offer_cart": offer_cart,
            "offer_cart_summary": offer_cart_summary,
            "contact_name": offer_cart and offer_cart[0].get("contact_name") or "",
            "contact_email": offer_cart and offer_cart[0].get("contact_email") or "",
            "contact_phone": offer_cart and offer_cart[0].get("contact_phone") or "",
        })
