from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .client_utils import normalize_client_name


class CommissionPeriodClientExclusion(models.Model):
    _name = "commission.period.client.exclusion"
    _description = "Cliente excluido de comisión por período"
    _order = "client_name, id"

    period_id = fields.Many2one(
        "commission.period",
        string="Período",
        required=True,
        ondelete="cascade",
        index=True,
    )
    client_id = fields.Many2one(
        "commission.client",
        string="Cliente",
        index=True,
        ondelete="restrict",
        domain=[("active", "=", True)],
        help="Seleccione el cliente desde el maestro generado automáticamente por las ventas.",
    )
    # Campo conservado por compatibilidad con versiones 1.10.0 y anteriores.
    # Se mantiene sincronizado con client_id y no se usa como selector en la UI.
    client_name = fields.Char(string="Cliente [legado]", index=True)
    normalized_client_name = fields.Char(
        string="Cliente normalizado",
        compute="_compute_normalized_client_name",
        store=True,
        index=True,
    )
    count_for_target = fields.Boolean(
        string="Contar para metas / mínimos",
        default=False,
        help=(
            "Si está activo, las ventas del cliente NO generan comisión, pero sí "
            "pueden ayudar a cumplir rangos/metas de vendedor, metas de local, "
            "mínimos administrativos y mínimos de liquidación. Si está desactivado, "
            "esas ventas se omiten también de dichos cumplimientos."
        ),
    )
    active = fields.Boolean(default=True)
    note = fields.Char(string="Observación")

    @api.depends("client_id", "client_id.normalized_name", "client_name")
    def _compute_normalized_client_name(self):
        for rec in self:
            rec.normalized_client_name = (
                rec.client_id.normalized_name
                or normalize_client_name(rec.client_name)
            )

    @api.onchange("client_id")
    def _onchange_client_id(self):
        for rec in self:
            if rec.client_id:
                rec.client_name = rec.client_id.name

    @api.model_create_multi
    def create(self, vals_list):
        Client = self.env["commission.client"]
        prepared = []
        for original in vals_list:
            vals = dict(original)
            if vals.get("client_id"):
                client = Client.browse(vals["client_id"]).exists()
                if client:
                    vals["client_name"] = client.name
            elif vals.get("client_name"):
                # Compatibilidad para copias/migraciones antiguas.
                client = Client.get_or_create_from_sale(vals.get("client_name"))
                if client:
                    vals["client_id"] = client.id
                    vals["client_name"] = client.name
            prepared.append(vals)
        return super().create(prepared)

    def write(self, vals):
        vals = dict(vals)
        if vals.get("client_id"):
            client = self.env["commission.client"].browse(vals["client_id"]).exists()
            if client:
                vals["client_name"] = client.name
        return super().write(vals)

    @api.constrains("client_id", "client_name", "period_id", "active")
    def _check_client_and_duplicate(self):
        for rec in self:
            if rec.active and not rec.client_id:
                raise ValidationError(_("Debe seleccionar un cliente."))
            normalized = rec.normalized_client_name
            if not normalized:
                raise ValidationError(_("Debe indicar un cliente válido."))
            duplicate = self.search_count([
                ("id", "!=", rec.id),
                ("period_id", "=", rec.period_id.id),
                ("normalized_client_name", "=", normalized),
            ])
            if duplicate:
                raise ValidationError(_(
                    "El cliente %(client)s ya está configurado en este período."
                ) % {"client": rec.client_id.display_name or rec.client_name})


class CommissionPeriodClientExclusionMixin(models.Model):
    _inherit = "commission.period"

    client_exclusion_ids = fields.One2many(
        "commission.period.client.exclusion",
        "period_id",
        string="Clientes excluidos de comisión",
        copy=False,
    )
    client_exclusion_count = fields.Integer(
        string="Clientes excluidos",
        compute="_compute_client_exclusion_count",
    )

    @api.depends("client_exclusion_ids", "client_exclusion_ids.active")
    def _compute_client_exclusion_count(self):
        for rec in self:
            rec.client_exclusion_count = len(rec.client_exclusion_ids.filtered("active"))

    def _client_exclusion_maps(self):
        """Return id/name maps once per period for O(1) sale classification."""
        self.ensure_one()
        by_client_id = {}
        by_name = {}
        for exclusion in self.client_exclusion_ids.filtered("active"):
            if exclusion.client_id:
                by_client_id[exclusion.client_id.id] = exclusion
            if exclusion.normalized_client_name:
                by_name[exclusion.normalized_client_name] = exclusion
        return by_client_id, by_name

    def _classify_sales_by_client_exclusion(self, sales):
        """Classify sales without recordset unions inside the main loop.

        This is intentionally linear in the number of sales. ``|=`` on growing
        Odoo recordsets can become noticeably slower on large monthly datasets.
        """
        self.ensure_one()
        by_client_id, by_name = self._client_exclusion_maps()
        commissionable_ids = []
        qualification_ids = []
        exclusion_by_sale = {}

        for sale in sales:
            exclusion = None
            if sale.client_id:
                exclusion = by_client_id.get(sale.client_id.id)
            if not exclusion:
                key = sale.client_match_name or normalize_client_name(sale.client)
                exclusion = by_name.get(key)

            if exclusion:
                exclusion_by_sale[sale.id] = exclusion
                if exclusion.count_for_target:
                    qualification_ids.append(sale.id)
            else:
                commissionable_ids.append(sale.id)
                qualification_ids.append(sale.id)

        Sale = self.env["commission.sale"]
        return (
            Sale.browse(commissionable_ids),
            Sale.browse(qualification_ids),
            exclusion_by_sale,
        )


class CommissionSaleClientMatch(models.Model):
    _inherit = "commission.sale"

    client_match_name = fields.Char(
        string="Cliente normalizado para exclusiones",
        compute="_compute_client_match_name",
        store=True,
        index=True,
    )

    @api.depends("client", "client_id", "client_id.normalized_name")
    def _compute_client_match_name(self):
        for rec in self:
            rec.client_match_name = (
                rec.client_id.normalized_name
                or normalize_client_name(rec.client)
            )
