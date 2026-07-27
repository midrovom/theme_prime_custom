from odoo import http, _
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager


class CustomerWalletPortal(CustomerPortal):

    def _wallet_domain(self):
        partner = request.env.user.partner_id
        partner_ids = list(set([partner.id, partner.commercial_partner_id.id]))
        return [
            ("partner_id", "in", partner_ids),
            ("company_id", "=", request.env.company.id),
            ("portal_enabled", "=", True),
            ("status", "!=", "closed"),
        ]

    @http.route(
        ["/my/wallet", "/my/wallet/page/<int:page>"],
        type="http",
        auth="user",
        website=True,
        readonly=True,
    )
    def portal_my_wallet(self, page=1, filterby="all", **kw):
        values = self._prepare_portal_layout_values()
        wallet = request.env["loyalty.wallet"].sudo().search(
            self._wallet_domain(), order="id desc", limit=1
        )

        transactions = request.env["loyalty.wallet.transaction"].sudo()
        transaction_domain = [("id", "=", 0)]
        if wallet:
            transaction_domain = [
                ("wallet_id", "=", wallet.id),
                ("state", "=", "confirmed"),
            ]
            if filterby in ("credit", "debit"):
                transaction_domain.append(("transaction_type", "=", filterby))
            else:
                filterby = "all"

        total = transactions.search_count(transaction_domain)
        pager = portal_pager(
            url="/my/wallet",
            total=total,
            page=page,
            step=20,
            url_args={"filterby": filterby},
        )
        movement_records = transactions.search(
            transaction_domain,
            order="date desc, id desc",
            limit=20,
            offset=pager["offset"],
        )

        values.update(
            {
                "page_name": "reward_wallet",
                "wallet": wallet,
                "transactions": movement_records,
                "pager": pager,
                "filterby": filterby,
                "filters": {
                    "all": _("Todos"),
                    "credit": _("Abonos"),
                    "debit": _("Consumos"),
                },
            }
        )
        return request.render(
            "customer_loyalty_wallet.portal_my_wallet", values
        )
