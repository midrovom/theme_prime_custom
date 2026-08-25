# import re

# from odoo import _, http
# from odoo.http import request


# EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


# class WebsiteProductOfferController(http.Controller):
#     @staticmethod
#     def _clean(value, limit=255):
#         return (value or "").strip()[:limit]

#     @staticmethod
#     def _number(value, default=0.0):
#         try:
#             return float(value)
#         except (TypeError, ValueError):
#             return default

#     def _get_product_data(self, product_id):
#         website = request.website.sudo()
#         if not website.offer_enabled:
#             return {"ok": False, "error": _("Las ofertas no están habilitadas en este sitio.")}

#         try:
#             product_id = int(product_id)
#         except (TypeError, ValueError):
#             return {"ok": False, "error": _("El producto seleccionado no es válido.")}

#         product = request.env["product.product"].sudo().browse(product_id).exists()
#         if not product or not product.active or not product.sale_ok:
#             return {"ok": False, "error": _("El producto ya no está disponible.")}

#         template = product.product_tmpl_id.with_context(website_id=website.id)
#         if not template.website_published:
#             return {"ok": False, "error": _("El producto no está publicado en este sitio.")}
#         restricted_website = getattr(template, "website_id", request.env["website"])
#         if restricted_website and restricted_website.id != website.id:
#             return {"ok": False, "error": _("El producto pertenece a otro sitio web.")}
#         if not template._website_offer_is_enabled(website):
#             return {"ok": False, "error": _("Este producto no está habilitado para recibir ofertas.")}

#         rule = template._website_offer_rule(website)
#         min_qty = rule._effective_min_qty() if rule else website.offer_default_min_qty
#         minimum_price_percent = (
#             rule._effective_minimum_price_percent()
#             if rule
#             else website.offer_minimum_price_percent
#         )
#         available_qty = template._website_offer_available_qty(website, product)
#         max_qty = rule.max_qty if rule else 0.0
#         if website.offer_limit_to_stock:
#             max_qty = min(max_qty, available_qty) if max_qty else available_qty

#         if website.offer_in_stock_only and available_qty <= 0:
#             return {"ok": False, "error": _("Este producto se quedó sin existencias.")}
#         if max_qty and min_qty > max_qty:
#             return {
#                 "ok": False,
#                 "error": _("El stock disponible es menor que la cantidad mínima permitida."),
#             }

#         return {
#             "ok": True,
#             "website": website,
#             "product": product,
#             "template": template,
#             "rule": rule,
#             "min_qty": min_qty,
#             "max_qty": max_qty,
#             "available_qty": available_qty,
#             "minimum_price_percent": minimum_price_percent,
#         }

#     @staticmethod
#     def _get_list_price(website, product, quantity):
#         pricelist = website.pricelist_id
#         price = pricelist._get_product_price(product, quantity)
#         return pricelist, max(0.0, price)

#     @http.route('/shop/offer/config',type="json", auth="public", methods=["POST"], website=True,)
#     def offer_config(self, product_id=None, quantity=None, **kwargs):
#         data = self._get_product_data(product_id)
#         if not data["ok"]:
#             return data
#         website = data["website"]
#         if website.offer_require_login and request.env.user._is_public():
#             return {
#                 "ok": False,
#                 "login_required": True,
#                 "error": _("Inicia sesión para enviar una oferta."),
#             }

#         quantity = max(data["min_qty"], self._number(quantity, data["min_qty"]))
#         pricelist, list_price = self._get_list_price(website, data["product"], quantity)
#         minimum_offer = list_price * data["minimum_price_percent"] / 100
#         return {
#             "ok": True,
#             "product_name": data["product"].display_name,
#             "list_price": list_price,
#             "currency": pricelist.currency_id.name,
#             "currency_symbol": pricelist.currency_id.symbol,
#             "min_qty": data["min_qty"],
#             "max_qty": data["max_qty"],
#             "available_qty": data["available_qty"],
#             "uom_name": data["product"].uom_id.name,
#             "uom_rounding": data["product"].uom_id.rounding,
#             "minimum_offer": minimum_offer,
#             "minimum_price_percent": data["minimum_price_percent"],
#         }

#     @http.route('/shop/offer/submit', type="json", auth="public", methods=["POST"], website=True,)
#     def submit_offer(
#         self,
#         product_id=None,
#         quantity=None,
#         offered_price=None,
#         contact_name=None,
#         contact_email=None,
#         contact_phone=None,
#         company_name=None,
#         customer_message=None,
#         source_url=None,
#         website_bait=None,
#         **kwargs,
#     ):
#         if website_bait:
#             return {"ok": False, "error": _("No fue posible procesar el formulario.")}

#         data = self._get_product_data(product_id)
#         if not data["ok"]:
#             return data
#         website = data["website"]
#         if website.offer_require_login and request.env.user._is_public():
#             return {
#                 "ok": False,
#                 "login_required": True,
#                 "error": _("Inicia sesión para enviar una oferta."),
#             }

#         quantity = self._number(quantity)
#         offered_price = self._number(offered_price)
#         if quantity < data["min_qty"]:
#             return {
#                 "ok": False,
#                 "error": _("La cantidad mínima para este producto es %(quantity)s.", quantity=data["min_qty"]),
#             }
#         if data["max_qty"] and quantity > data["max_qty"]:
#             return {
#                 "ok": False,
#                 "error": _("La cantidad máxima disponible es %(quantity)s.", quantity=data["max_qty"]),
#             }
#         if offered_price <= 0:
#             return {"ok": False, "error": _("Ingresa un precio unitario válido.")}

#         pricelist, list_price = self._get_list_price(website, data["product"], quantity)
#         minimum_offer = list_price * data["minimum_price_percent"] / 100
#         if minimum_offer and offered_price < minimum_offer:
#             return {
#                 "ok": False,
#                 "error": _(
#                     "La oferta está por debajo del mínimo permitido para este producto."
#                 ),
#             }

#         public_user = request.env.user._is_public()
#         partner = request.env.user.partner_id if not public_user else request.env["res.partner"]
#         contact_name = self._clean(contact_name, 120) or (partner.name if partner else "")
#         contact_email = self._clean(contact_email, 160) or (partner.email if partner else "")
#         contact_phone = self._clean(contact_phone, 60) or (partner.phone if partner else "")
#         company_name = self._clean(company_name, 160)
#         customer_message = self._clean(customer_message, 2000)
#         source_url = self._clean(source_url, 500)
#         if not source_url.startswith("/"):
#             source_url = data["template"].website_url

#         if not contact_name:
#             return {"ok": False, "error": _("Indica el nombre de la persona de contacto.")}
#         if not contact_email and not contact_phone:
#             return {"ok": False, "error": _("Indica un correo o teléfono de contacto.")}
#         if contact_email and not EMAIL_PATTERN.match(contact_email):
#             return {"ok": False, "error": _("El correo electrónico no tiene un formato válido.")}

#         Offer = request.env["website.sale.offer"].sudo().with_company(website.company_id)
#         offer = Offer.create(
#             {
#                 "website_id": website.id,
#                 "company_id": website.company_id.id,
#                 "user_id": website.offer_user_id.id,
#                 "partner_id": partner.id,
#                 "contact_name": contact_name,
#                 "contact_email": contact_email,
#                 "contact_phone": contact_phone,
#                 "company_name": company_name,
#                 "product_id": data["product"].id,
#                 "quantity": quantity,
#                 "available_qty_snapshot": data["available_qty"],
#                 "pricelist_id": pricelist.id,
#                 "list_price": list_price,
#                 "offered_price": offered_price,
#                 "customer_message": customer_message,
#                 "valid_until": Offer._default_valid_until(website),
#                 "source_url": source_url,
#             }
#         )
#         offer._send_status_email("website_product_offer.mail_template_offer_received")
#         return {
#             "ok": True,
#             "reference": offer.name,
#             "portal_url": offer.get_portal_url(),
#             "message": _("Recibimos tu oferta. Nuestro equipo la revisará y te responderá pronto."),
#         }


import json
import re

from odoo import _, Command, http
from odoo.http import request


EMAIL_PATTERN = re.compile(
    r"^[^\s@]+@[^\s@]+\.[^\s@]+$"
)


class WebsiteProductOfferController(http.Controller):

    # ============================================================
    # HELPERS
    # ============================================================

    @staticmethod
    def _clean(value, limit=255):
        return (value or "").strip()[:limit]

    @staticmethod
    def _number(value, default=0.0):
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _int(value, default=None):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    # ============================================================
    # PRODUCT DATA
    # ============================================================

    def _get_product_data(self, product_id):
        """
        Valida que el producto:

        - exista
        - esté activo
        - se pueda vender
        - esté publicado
        - pertenezca al website correcto
        - tenga habilitadas las ofertas
        - cumpla las reglas de stock/cantidad
        """

        website = request.website.sudo()

        if not website.offer_enabled:
            return {
                "ok": False,
                "error": _(
                    "Las ofertas no están habilitadas en este sitio."
                ),
            }

        product_id = self._int(product_id)

        if not product_id:
            return {
                "ok": False,
                "error": _(
                    "El producto seleccionado no es válido."
                ),
            }

        product = (
            request.env["product.product"]
            .sudo()
            .browse(product_id)
            .exists()
        )

        if not product or not product.active or not product.sale_ok:
            return {
                "ok": False,
                "error": _(
                    "El producto ya no está disponible."
                ),
            }

        template = product.product_tmpl_id.with_context(
            website_id=website.id
        )

        if not template.website_published:
            return {
                "ok": False,
                "error": _(
                    "El producto no está publicado en este sitio."
                ),
            }

        restricted_website = getattr(
            template,
            "website_id",
            request.env["website"],
        )

        if (
            restricted_website
            and restricted_website.id != website.id
        ):
            return {
                "ok": False,
                "error": _(
                    "El producto pertenece a otro sitio web."
                ),
            }

        if not template._website_offer_is_enabled(website):
            return {
                "ok": False,
                "error": _(
                    "Este producto no está habilitado "
                    "para recibir ofertas."
                ),
            }

        rule = template._website_offer_rule(website)

        min_qty = (
            rule._effective_min_qty()
            if rule
            else website.offer_default_min_qty
        )

        minimum_price_percent = (
            rule._effective_minimum_price_percent()
            if rule
            else website.offer_minimum_price_percent
        )

        available_qty = (
            template._website_offer_available_qty(
                website,
                product,
            )
        )

        max_qty = rule.max_qty if rule else 0.0

        if website.offer_limit_to_stock:
            max_qty = (
                min(max_qty, available_qty)
                if max_qty
                else available_qty
            )

        if (
            website.offer_in_stock_only
            and available_qty <= 0
        ):
            return {
                "ok": False,
                "error": _(
                    "Este producto se quedó sin existencias."
                ),
            }

        if max_qty and min_qty > max_qty:
            return {
                "ok": False,
                "error": _(
                    "El stock disponible es menor que "
                    "la cantidad mínima permitida."
                ),
            }

        return {
            "ok": True,
            "website": website,
            "product": product,
            "template": template,
            "rule": rule,
            "min_qty": min_qty,
            "max_qty": max_qty,
            "available_qty": available_qty,
            "minimum_price_percent": minimum_price_percent,
        }

    # ============================================================
    # PRICING
    # ============================================================

    @staticmethod
    def _get_list_price(website, product, quantity):
        """
        Obtiene el precio de lista usando la lista de precios
        configurada en el website.
        """

        pricelist = website.pricelist_id

        price = pricelist._get_product_price(
            product,
            quantity,
        )

        return pricelist, max(0.0, price)

    # ============================================================
    # LOGIN VALIDATION
    # ============================================================

    @staticmethod
    def _check_login_required(website):
        if (
            website.offer_require_login
            and request.env.user._is_public()
        ):
            return {
                "ok": False,
                "login_required": True,
                "error": _(
                    "Inicia sesión para enviar una oferta."
                ),
            }

        return None

    # ============================================================
    # /shop/offer/config
    # ============================================================

    @http.route(
        "/shop/offer/config",
        type="json",
        auth="public",
        methods=["POST"],
        website=True,
    )
    def offer_config(
        self,
        product_id=None,
        quantity=None,
        **kwargs,
    ):
        """
        Devuelve la configuración de un producto.

        Este endpoint sigue siendo individual porque el frontend
        lo puede utilizar cada vez que se agrega/modifica una
        línea de la oferta.
        """

        data = self._get_product_data(product_id)

        if not data["ok"]:
            return data

        website = data["website"]

        login_error = self._check_login_required(website)

        if login_error:
            return login_error

        quantity = max(
            data["min_qty"],
            self._number(
                quantity,
                data["min_qty"],
            ),
        )

        # No permitir consultar una cantidad superior al máximo.
        if data["max_qty"]:
            quantity = min(
                quantity,
                data["max_qty"],
            )

        pricelist, list_price = self._get_list_price(
            website,
            data["product"],
            quantity,
        )

        minimum_offer = (
            list_price
            * data["minimum_price_percent"]
            / 100
        )

        return {
            "ok": True,

            "product_id": data["product"].id,

            "product_name": data["product"].display_name,

            "list_price": list_price,

            "currency": pricelist.currency_id.name,

            "currency_symbol": pricelist.currency_id.symbol,

            "min_qty": data["min_qty"],

            "max_qty": data["max_qty"],

            "available_qty": data["available_qty"],

            "uom_name": data["product"].uom_id.name,

            "uom_rounding": data["product"].uom_id.rounding,

            "minimum_offer": minimum_offer,

            "minimum_price_percent": (
                data["minimum_price_percent"]
            ),
        }

    # ============================================================
    # VALIDATE ONE OFFER LINE
    # ============================================================

    def _validate_offer_line(
        self,
        website,
        line,
        index,
    ):
        """
        Valida una línea individual de la oferta.

        Retorna:

        {
            "ok": True,
            "values": {...}
        }

        o

        {
            "ok": False,
            "error": "..."
        }
        """

        if not isinstance(line, dict):
            return {
                "ok": False,
                "error": _(
                    "La línea %(line)s de la oferta "
                    "no es válida.",
                    line=index,
                ),
            }

        product_id = self._int(
            line.get("product_id")
        )

        if not product_id:
            return {
                "ok": False,
                "error": _(
                    "El producto de la línea %(line)s "
                    "no es válido.",
                    line=index,
                ),
            }

        quantity = self._number(
            line.get("quantity")
        )

        offered_price = self._number(
            line.get("offered_price")
        )

        # --------------------------------------------------------
        # PRODUCT
        # --------------------------------------------------------

        data = self._get_product_data(
            product_id
        )

        if not data["ok"]:
            return {
                "ok": False,
                "error": _(
                    "Producto de la línea %(line)s: %(error)s",
                    line=index,
                    error=data["error"],
                ),
            }

        product = data["product"]

        # --------------------------------------------------------
        # QUANTITY
        # --------------------------------------------------------

        if quantity <= 0:
            return {
                "ok": False,
                "error": _(
                    "La cantidad para %(product)s "
                    "debe ser mayor que cero.",
                    product=product.display_name,
                ),
            }

        if quantity < data["min_qty"]:
            return {
                "ok": False,
                "error": _(
                    "La cantidad mínima para %(product)s "
                    "es %(quantity)s.",
                    product=product.display_name,
                    quantity=data["min_qty"],
                ),
            }

        if (
            data["max_qty"]
            and quantity > data["max_qty"]
        ):
            return {
                "ok": False,
                "error": _(
                    "La cantidad máxima para %(product)s "
                    "es %(quantity)s.",
                    product=product.display_name,
                    quantity=data["max_qty"],
                ),
            }

        # --------------------------------------------------------
        # PRICE
        # --------------------------------------------------------

        if offered_price <= 0:
            return {
                "ok": False,
                "error": _(
                    "Ingresa un precio unitario válido "
                    "para %(product)s.",
                    product=product.display_name,
                ),
            }

        pricelist, list_price = self._get_list_price(
            website,
            product,
            quantity,
        )

        minimum_offer = (
            list_price
            * data["minimum_price_percent"]
            / 100
        )

        if (
            minimum_offer
            and offered_price < minimum_offer
        ):
            return {
                "ok": False,
                "error": _(
                    "La oferta para %(product)s está "
                    "por debajo del mínimo permitido.",
                    product=product.display_name,
                ),
            }

        # --------------------------------------------------------
        # RETURN NORMALIZED LINE
        # --------------------------------------------------------

        return {
            "ok": True,
            "values": {
                "product_id": product.id,
                "quantity": quantity,
                "available_qty_snapshot": (
                    data["available_qty"]
                ),
                "pricelist_id": pricelist.id,
                "list_price": list_price,
                "offered_price": offered_price,
            },
        }

    # ============================================================
    # /shop/offer/submit
    # ============================================================

    @http.route(
        "/shop/offer/submit",
        type="json",
        auth="public",
        methods=["POST"],
        website=True,
    )
    def submit_offer(
        self,
        lines=None,
        contact_name=None,
        contact_email=None,
        contact_phone=None,
        company_name=None,
        customer_message=None,
        source_url=None,
        website_bait=None,
        **kwargs,
    ):
        """
        Crea una oferta comercial multiproducto.

        Formato esperado:

        lines = [
            {
                "product_id": 10,
                "quantity": 5,
                "offered_price": 700,
            },
            {
                "product_id": 20,
                "quantity": 3,
                "offered_price": 900,
            },
        ]
        """

        # ========================================================
        # HONEYPOT
        # ========================================================

        if website_bait:
            return {
                "ok": False,
                "error": _(
                    "No fue posible procesar el formulario."
                ),
            }

        # ========================================================
        # WEBSITE
        # ========================================================

        website = request.website.sudo()

        if not website.offer_enabled:
            return {
                "ok": False,
                "error": _(
                    "Las ofertas no están habilitadas "
                    "en este sitio."
                ),
            }

        # ========================================================
        # LOGIN
        # ========================================================

        login_error = self._check_login_required(
            website
        )

        if login_error:
            return login_error

        # ========================================================
        # NORMALIZE LINES
        # ========================================================

        if not lines:
            return {
                "ok": False,
                "error": _(
                    "Debes agregar al menos un "
                    "producto a la oferta."
                ),
            }

        # FormData puede enviar JSON como string.
        if isinstance(lines, str):
            try:
                lines = json.loads(lines)
            except (
                TypeError,
                ValueError,
                json.JSONDecodeError,
            ):
                return {
                    "ok": False,
                    "error": _(
                        "Las líneas de la oferta "
                        "no tienen un formato válido."
                    ),
                }

        if not isinstance(lines, list):
            return {
                "ok": False,
                "error": _(
                    "Las líneas de la oferta "
                    "no tienen un formato válido."
                ),
            }

        if not lines:
            return {
                "ok": False,
                "error": _(
                    "Debes agregar al menos un "
                    "producto a la oferta."
                ),
            }

        # ========================================================
        # LIMITAR CANTIDAD DE LÍNEAS
        # ========================================================

        max_lines = 100

        if len(lines) > max_lines:
            return {
                "ok": False,
                "error": _(
                    "La oferta no puede contener "
                    "más de %(max)s productos.",
                    max=max_lines,
                ),
            }

        # ========================================================
        # CUSTOMER
        # ========================================================

        public_user = (
            request.env.user._is_public()
        )

        partner = (
            request.env.user.partner_id
            if not public_user
            else request.env["res.partner"]
        )

        contact_name = self._clean(
            contact_name,
            120,
        ) or (
            partner.name
            if partner
            else ""
        )

        contact_email = self._clean(
            contact_email,
            160,
        ) or (
            partner.email
            if partner
            else ""
        )

        contact_phone = self._clean(
            contact_phone,
            60,
        ) or (
            partner.phone
            if partner
            else ""
        )

        company_name = self._clean(
            company_name,
            160,
        )

        customer_message = self._clean(
            customer_message,
            2000,
        )

        source_url = self._clean(
            source_url,
            500,
        )

        # ========================================================
        # CONTACT VALIDATION
        # ========================================================

        if not contact_name:
            return {
                "ok": False,
                "error": _(
                    "Indica el nombre de la persona "
                    "de contacto."
                ),
            }

        if not contact_email and not contact_phone:
            return {
                "ok": False,
                "error": _(
                    "Indica un correo o teléfono "
                    "de contacto."
                ),
            }

        if (
            contact_email
            and not EMAIL_PATTERN.match(
                contact_email
            )
        ):
            return {
                "ok": False,
                "error": _(
                    "El correo electrónico no tiene "
                    "un formato válido."
                ),
            }

        # ========================================================
        # SOURCE URL
        # ========================================================

        if not source_url.startswith("/"):
            source_url = "/shop"

        # ========================================================
        # DUPLICATE PRODUCTS
        # ========================================================

        product_ids = set()

        for index, line in enumerate(
            lines,
            start=1,
        ):
            if not isinstance(line, dict):
                return {
                    "ok": False,
                    "error": _(
                        "La línea %(line)s "
                        "no es válida.",
                        line=index,
                    ),
                }

            product_id = self._int(
                line.get("product_id")
            )

            if not product_id:
                return {
                    "ok": False,
                    "error": _(
                        "El producto de la línea "
                        "%(line)s no es válido.",
                        line=index,
                    ),
                }

            if product_id in product_ids:
                product = (
                    request.env[
                        "product.product"
                    ]
                    .sudo()
                    .browse(product_id)
                )

                return {
                    "ok": False,
                    "error": _(
                        "El producto %(product)s "
                        "aparece más de una vez "
                        "en la oferta.",
                        product=(
                            product.display_name
                            if product.exists()
                            else product_id
                        ),
                    ),
                }

            product_ids.add(product_id)

        # ========================================================
        # VALIDATE ALL LINES
        # ========================================================

        validated_lines = []

        for index, line in enumerate(
            lines,
            start=1,
        ):
            result = self._validate_offer_line(
                website,
                line,
                index,
            )

            if not result["ok"]:
                return result

            validated_lines.append(
                result["values"]
            )

        # ========================================================
        # ENSURE SAME PRICELIST
        # ========================================================

        pricelist_ids = {
            line["pricelist_id"]
            for line in validated_lines
        }

        if len(pricelist_ids) != 1:
            return {
                "ok": False,
                "error": _(
                    "Todos los productos de la oferta "
                    "deben utilizar la misma lista de precios."
                ),
            }

        pricelist_id = next(
            iter(pricelist_ids)
        )

        # ========================================================
        # CREATE OFFER
        # ========================================================

        Offer = (
            request.env[
                "website.sale.offer"
            ]
            .sudo()
            .with_company(
                website.company_id
            )
        )

        offer = Offer.create(
            {
                "website_id": website.id,

                "company_id": (
                    website.company_id.id
                ),

                "user_id": (
                    website.offer_user_id.id
                ),

                "partner_id": (
                    partner.id
                    if partner
                    else False
                ),

                "contact_name": contact_name,

                "contact_email": contact_email,

                "contact_phone": contact_phone,

                "company_name": company_name,

                "pricelist_id": pricelist_id,

                "customer_message": (
                    customer_message
                ),

                "valid_until": (
                    Offer._default_valid_until(
                        website
                    )
                ),

                "source_url": source_url,

                "line_ids": [
                    Command.create(
                        {
                            "product_id": line[
                                "product_id"
                            ],

                            "quantity": line[
                                "quantity"
                            ],

                            "available_qty_snapshot": line[
                                "available_qty_snapshot"
                            ],

                            "list_price": line[
                                "list_price"
                            ],

                            "offered_price": line[
                                "offered_price"
                            ],
                        }
                    )
                    for line in validated_lines
                ],
            }
        )

        # ========================================================
        # EMAIL
        # ========================================================

        offer._send_status_email(
            "website_product_offer.mail_template_offer_received"
        )

        # ========================================================
        # RESPONSE
        # ========================================================

        return {
            "ok": True,

            "reference": offer.name,

            "portal_url": (
                offer.get_portal_url()
            ),

            "message": _(
                "Recibimos tu oferta. Nuestro "
                "equipo la revisará y te "
                "responderá pronto."
            ),

            "line_count": len(
                validated_lines
            ),

            "offer_total": offer.offer_total,

            "currency": (
                offer.currency_id.name
            ),

            "currency_symbol": (
                offer.currency_id.symbol
            ),
        }

