from odoo import http
from odoo.http import request


class WebsiteProductOfferController(http.Controller):

    @http.route(
        "/shop/offer/add",
        type="json",
        auth="public",
        website=True,
    )
    def shop_offer_add(self, **kwargs):
        """
        Agrega temporalmente un producto a la oferta del usuario.
        No crea todavía la oferta definitiva.
        """

        product_id = int(kwargs.get("product_id") or 0)
        quantity = float(kwargs.get("quantity") or 0)
        offered_price = float(kwargs.get("offered_price") or 0)

        if not product_id:
            return {
                "ok": False,
                "error": "Producto no válido.",
            }

        if quantity <= 0:
            return {
                "ok": False,
                "error": "La cantidad debe ser mayor a cero.",
            }

        if offered_price <= 0:
            return {
                "ok": False,
                "error": "El precio ofrecido debe ser mayor a cero.",
            }

        product = request.env["product.product"].sudo().browse(product_id)

        if not product.exists():
            return {
                "ok": False,
                "error": "El producto no existe.",
            }

        # -----------------------------------------
        # Recuperar lista temporal
        # -----------------------------------------
        offer_cart = request.session.get("wpo_offer_cart", [])

        # Hacemos una copia para evitar modificar
        # directamente el objeto de sesión.
        offer_cart = list(offer_cart)

        # -----------------------------------------
        # Buscar si el producto ya estaba agregado
        # -----------------------------------------
        existing_line = next(
            (
                line
                for line in offer_cart
                if int(line.get("product_id", 0)) == product.id
            ),
            None,
        )

        if existing_line:
            # Puedes elegir si acumulas cantidad
            # o reemplazas los datos.
            existing_line.update({
                "quantity": quantity,
                "offered_price": offered_price,
                "total": quantity * offered_price,
            })
        else:
            offer_cart.append({
                "product_id": product.id,
                "product_name": product.display_name,
                "quantity": quantity,
                "offered_price": offered_price,
                "total": quantity * offered_price,
                "list_price": product.lst_price,
                "website_url": product.website_url,
            })

        # -----------------------------------------
        # Guardar nuevamente en sesión
        # -----------------------------------------
        request.session["wpo_offer_cart"] = offer_cart
        request.session.modified = True

        return {
            "ok": True,
            "redirect": "/shop/offer/cart",
            "count": len(offer_cart),
            "message": "Producto agregado a tu oferta.",
        }

    @http.route("/shop/offer/cart", type="http", auth="public", website=True,)
    def shop_offer_cart(self):
        offer_cart = request.session.get("wpo_offer_cart", [])
        return request.render(
            "tu_modulo.website_offer_cart",
            {
                "offer_cart": offer_cart,
            },
        )

    @http.route("/shop/offer/submit", type="json", auth="public", website=True,)
    def shop_offer_submit(self, **kwargs):
        offer_cart = request.session.get("wpo_offer_cart", [])
        if not offer_cart:
            return {
                "ok": False,
                "error": "No tienes productos en tu oferta.",
            }

        contact_name = (kwargs.get("contact_name") or "").strip()
        company_name = (kwargs.get("company_name") or "").strip()
        contact_email = (kwargs.get("contact_email") or "").strip()
        contact_phone = (kwargs.get("contact_phone") or "").strip()
        customer_message = (kwargs.get("customer_message") or "").strip()

        if not contact_email and not contact_phone:
            return {
                "ok": False,
                "error": "Indica un correo o un teléfono para poder responderte.",
            }

        try:
            offer = self._create_offer(
                offer_cart=offer_cart,
                contact_name=contact_name,
                company_name=company_name,
                contact_email=contact_email,
                contact_phone=contact_phone,
                customer_message=customer_message,
            )
        except Exception as error:
            return {
                "ok": False,
                "error": str(error),
            }

        request.session.pop("wpo_offer_cart", None)
        request.session.modified = True

        return {
            "ok": True,
            "reference": offer.name,
            "message": "Tu oferta fue enviada correctamente.",
            "portal_url": "/my/offers/%s" % offer.id,
        }

    def _create_offer(
        self,
        offer_cart,
        contact_name,
        company_name,
        contact_email,
        contact_phone,
        customer_message,
    ):
        Offer = request.env["website.product.offer"].sudo()

        offer = Offer.create({
            "partner_id": request.env.user.partner_id.id
                if not request.env.user._is_public()
                else False,

            "contact_name": contact_name,
            "company_name": company_name,
            "contact_email": contact_email,
            "contact_phone": contact_phone,
            "customer_message": customer_message,
        })

        OfferLine = request.env["website.product.offer.line"].sudo()

        for item in offer_cart:

            product = request.env["product.product"].sudo().browse(
                int(item["product_id"])
            )

            if not product.exists():
                continue

            OfferLine.create({
                "offer_id": offer.id,
                "product_id": product.id,
                "quantity": float(item["quantity"]),
                "offered_price": float(item["offered_price"]),
            })

        return offer