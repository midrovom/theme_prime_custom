from odoo import api, fields, models, _
from odoo.exceptions import UserError


API_NAME = "comisiones_transcash_retail"


class CommissionSync(models.Model):
    _inherit = "commission.sync"

    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        required=False,
        default=lambda self: self.env.company,
        index=True,
    )
    api_administrator_id = fields.Many2one(
        "api.administrator",
        string="Configuración API",
        compute="_compute_api_administrator_id",
        readonly=True,
    )
    api_request_url = fields.Char(
        string="URL de consulta",
        compute="_compute_api_request_url",
        readonly=True,
    )

    def _api_search_domain(self):
        self.ensure_one()
        api_model = self.env["api.administrator"].sudo()
        domain = [
            ("name", "=", API_NAME),
            ("type", "=", "get"),
            ("company_id", "=", self.company_id.id or self.env.company.id),
        ]
        if "status" in api_model._fields:
            domain.append(("status", "=", "A"))
        return domain

    def _get_api_administrator(self, required=True):
        self.ensure_one()
        api_model = self.env["api.administrator"].sudo()
        records = api_model.search(self._api_search_domain(), limit=2)
        if len(records) > 1:
            raise UserError(_(
                "Existe más de una configuración activa '%(api)s' tipo GET para "
                "la compañía %(company)s. Deje una sola configuración activa."
            ) % {
                "api": API_NAME,
                "company": self.company_id.display_name or self.env.company.display_name,
            })
        if not records and required:
            raise UserError(_(
                "No se encontró una API activa llamada '%(api)s', tipo GET, para "
                "la compañía %(company)s en api.administrator."
            ) % {
                "api": API_NAME,
                "company": self.company_id.display_name or self.env.company.display_name,
            })
        return records[:1]

    @api.depends("company_id")
    def _compute_api_administrator_id(self):
        for rec in self:
            rec.api_administrator_id = rec._get_api_administrator(required=False)

    @api.depends("company_id", "date_from", "date_to")
    def _compute_api_request_url(self):
        for rec in self:
            rec.api_request_url = False
            api_record = rec._get_api_administrator(required=False)
            if api_record and rec.date_from and rec.date_to:
                try:
                    # Keep credentials out of the preview. URL contains only the
                    # configured endpoint and period dates.
                    rec.api_request_url = api_record._commission_build_request_url(
                        rec.date_from, rec.date_to
                    )
                except UserError:
                    rec.api_request_url = False

    def _fetch_remote_rows(self):
        """Use api.administrator instead of the generic commission connector."""
        self.ensure_one()
        if not self.date_from or not self.date_to:
            raise UserError(_("Indique fecha desde y fecha hasta antes de sincronizar."))
        if self.date_to < self.date_from:
            raise UserError(_("La fecha hasta no puede ser anterior a la fecha desde."))

        api_record = self._get_api_administrator(required=True)
        payload = api_record.call_commission_sales_api(self.date_from, self.date_to)

        if isinstance(payload, dict) and payload.get("success") is False:
            raise UserError(_(
                "La API respondió con error: %s"
            ) % (payload.get("message") or payload.get("error") or _("Error no especificado")))

        if isinstance(payload, dict):
            rows = payload.get("data")
            if rows is None:
                # Compatibility with alternative wrappers while preserving the
                # expected {data: [...]} format as first choice.
                rows = payload.get("result")
            if rows is None:
                rows = payload.get("rows")
            if rows is None:
                rows = []
        else:
            rows = payload

        if not isinstance(rows, list):
            raise UserError(_(
                "La respuesta de '%s' debe contener una lista en la clave 'data'."
            ) % API_NAME)
        return rows
