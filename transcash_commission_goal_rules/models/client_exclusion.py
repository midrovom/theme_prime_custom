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
    client_name = fields.Char(
        string="Cliente",
        required=True,
        index=True,
        help=(
            "Nombre del cliente tal como llega en las ventas. La comparación es "
            "exacta sobre una versión normalizada del nombre."
        ),
    )
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

    @api.depends("client_name")
    def _compute_normalized_client_name(self):
        for rec in self:
            rec.normalized_client_name = normalize_client_name(rec.client_name)

    @api.constrains("client_name", "period_id", "active")
    def _check_client_name_and_duplicate(self):
        for rec in self:
            normalized = normalize_client_name(rec.client_name)
            if not normalized:
                raise ValidationError(_("Debe indicar un nombre de cliente válido."))
            duplicate = self.search_count([
                ("id", "!=", rec.id),
                ("period_id", "=", rec.period_id.id),
                ("normalized_client_name", "=", normalized),
                ("active", "=", True),
            ])
            if rec.active and duplicate:
                raise ValidationError(_(
                    "El cliente %(client)s ya está configurado como exclusión en este período."
                ) % {"client": rec.client_name})


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

    def _client_exclusion_map(self):
        self.ensure_one()
        return {
            exclusion.normalized_client_name: exclusion
            for exclusion in self.client_exclusion_ids.filtered("active")
            if exclusion.normalized_client_name
        }

    def _classify_sales_by_client_exclusion(self, sales):
        """Return commissionable and qualification recordsets plus lookup map.

        * commissionable: client is not excluded -> may generate commission.
        * qualification: non-excluded sales plus excluded sales explicitly marked
          to count for targets/minimums.
        * exclusion_by_sale: sale.id -> matching exclusion record.
        """
        self.ensure_one()
        exclusion_map = self._client_exclusion_map()
        Sale = self.env["commission.sale"]
        commissionable = Sale.browse()
        qualification = Sale.browse()
        exclusion_by_sale = {}

        for sale in sales:
            key = sale.client_match_name or normalize_client_name(sale.client)
            exclusion = exclusion_map.get(key)
            if exclusion:
                exclusion_by_sale[sale.id] = exclusion
                if exclusion.count_for_target:
                    qualification |= sale
            else:
                commissionable |= sale
                qualification |= sale

        return commissionable, qualification, exclusion_by_sale


class CommissionSaleClientMatch(models.Model):
    _inherit = "commission.sale"

    client_match_name = fields.Char(
        string="Cliente normalizado para exclusiones",
        compute="_compute_client_match_name",
        store=True,
        index=True,
    )

    @api.depends("client")
    def _compute_client_match_name(self):
        for rec in self:
            rec.client_match_name = normalize_client_name(rec.client)
