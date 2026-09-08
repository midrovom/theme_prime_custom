import hashlib
import json
import logging
import re
import uuid
from datetime import datetime

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


# Current positional API layout. "Cantidad" is the quantity/m² supplied by source.
API_FIELDS = [
    "Tipo", "Numero", "Factura", "Fecha_Registro", "Vence", "Cliente",
    "Vendedor", "CodVendedor", "bodega", "Linea", "Marca", "Codproducto",
    "nProducto", "Cantidad", "costo", "Total_Costo", "Total_Precio",
    "Porc_Descuento", "pTarjeta", "Total_Neto", "Indica_Precio", "Descuento",
    "Utilidad", "PorcUtilidad", "Forma_pago", "Proveedor", "Origen",
    "localidad", "nLocal",
]

# Accepted only to ease transition from the first 28-column layout.
LEGACY_API_FIELDS = [
    "Tipo", "Numero", "Factura", "Fecha_Registro", "Vence", "Cliente",
    "Vendedor", "CodVendedor", "bodega", "Linea", "Marca", "Codproducto",
    "nProducto", "costo", "Total_Costo", "Total_Precio", "Porc_Descuento",
    "pTarjeta", "Total_Neto", "Indica_Precio", "Descuento", "Utilidad",
    "PorcUtilidad", "Forma_pago", "Proveedor", "Origen", "localidad", "nLocal",
]


def _norm_key(value):
    return re.sub(r"[^a-z0-9]", "", str(value or "").strip().lower())


def _clean(value):
    return str(value or "").strip()


class CommissionSale(models.Model):
    _name = "commission.sale"
    _description = "Venta para cálculo de comisiones"
    _order = "registration_date desc, number desc, id desc"
    _rec_name = "name"

    name = fields.Char(compute="_compute_name", store=True)
    fingerprint = fields.Char(
        index=True,
        readonly=True,
        copy=False,
        default=lambda self: uuid.uuid4().hex,
        help="Huella de deduplicación. La sincronización genera una huella determinística.",
    )
    raw_payload = fields.Text(readonly=True, string="Payload origen")
    imported_at = fields.Datetime(default=fields.Datetime.now, readonly=True, index=True)
    sync_id = fields.Many2one(
        "commission.sync",
        string="Sincronización",
        readonly=True,
        copy=False,
        index=True,
        ondelete="set null",
    )

    document_type = fields.Char(string="Tipo", index=True)
    number = fields.Char(string="Número", index=True)
    invoice = fields.Char(string="Factura", index=True)
    registration_date = fields.Date(string="Fecha registro", required=True, index=True)
    due_date = fields.Date(string="Vence")
    client = fields.Char(string="Cliente")

    # Raw source values are retained in addition to the master relations.
    seller_name = fields.Char(string="Vendedor origen")
    seller_code = fields.Char(string="Cod. vendedor", index=True)
    seller_id = fields.Many2one(
        "commission.seller",
        string="Vendedor",
        index=True,
        ondelete="restrict",
    )

    warehouse = fields.Char(string="Bodega")
    product_line = fields.Char(string="Línea")
    brand = fields.Char(string="Marca")
    product_code = fields.Char(string="Cód. producto", index=True)
    product_name = fields.Char(string="Producto")
    quantity = fields.Float(
        string="Cantidad / m²",
        digits=(16, 6),
        help="Cantidad recibida desde la fuente. Para el bono de liquidación esta cantidad corresponde a m².",
    )
    cost = fields.Float(string="Costo", digits=(16, 6))
    total_cost = fields.Float(string="Total costo", digits=(16, 6))
    total_price = fields.Float(string="Total precio", digits=(16, 6))
    discount_percent = fields.Float(string="% descuento", digits=(16, 6))
    card_percent = fields.Float(string="pTarjeta", digits=(16, 6))
    total_net = fields.Float(string="Total neto", digits=(16, 6))
    price_indicator = fields.Float(string="Indica precio", digits=(16, 6), index=True)
    discount = fields.Float(string="Descuento", digits=(16, 6))
    profit = fields.Float(string="Utilidad", digits=(16, 6))
    profit_percent = fields.Float(string="% utilidad", digits=(16, 6))
    payment_method = fields.Char(string="Forma pago")
    supplier = fields.Char(string="Proveedor")
    origin = fields.Char(string="Origen", index=True)

    location_code = fields.Char(string="Localidad origen", index=True)
    location_name = fields.Char(string="Nombre local origen")
    location_id = fields.Many2one(
        "commission.location",
        string="Localidad",
        index=True,
        ondelete="restrict",
    )

    document_sign = fields.Float(
        string="Signo",
        default=1.0,
        required=True,
        help="+1 para ventas, -1 para devoluciones/notas de crédito.",
    )
    excluded = fields.Boolean(
        string="Excluir de comisiones",
        default=False,
        help="Permite excluir manualmente una venta sin borrar el dato importado.",
    )
    exclusion_reason = fields.Char(string="Motivo exclusión")

    _sql_constraints = [
        ("sale_fingerprint_unique", "unique(fingerprint)", "La venta ya fue importada."),
    ]

    @api.depends("document_type", "number", "invoice", "product_code", "seller_code")
    def _compute_name(self):
        for rec in self:
            rec.name = "%s %s / %s / %s" % (
                rec.document_type or "DOC",
                rec.number or rec.invoice or "",
                rec.seller_code or "",
                rec.product_code or "",
            )

    @api.constrains("quantity")
    def _check_quantity(self):
        for rec in self:
            if rec.quantity < 0:
                raise ValidationError(_("La cantidad debe almacenarse positiva; el signo del documento controla las devoluciones."))

    @api.model_create_multi
    def create(self, vals_list):
        """Create missing seller/location masters for every ORM insertion path.

        This is intentionally placed here rather than only in the API importer. Any
        connector, XML-RPC/JSON-RPC integration, cron or custom module that calls
        env['commission.sale'].create(...) gets identical master-data behavior.
        Direct SQL INSERT statements bypass Odoo ORM and therefore must not be used.
        """
        prepared = []
        for original in vals_list:
            vals = dict(original)

            # Normalize denormalized source fields.
            for field_name in ("seller_code", "seller_name", "location_code", "location_name"):
                if field_name in vals:
                    vals[field_name] = _clean(vals.get(field_name))

            location = self.env["commission.location"].browse()
            if vals.get("location_id"):
                location = self.env["commission.location"].browse(vals["location_id"]).exists()
                if location:
                    vals.setdefault("location_code", location.code)
                    vals.setdefault("location_name", location.name)
            elif vals.get("location_code"):
                location = self.env["commission.location"].sudo().get_or_create_from_sale(
                    vals.get("location_code"), vals.get("location_name")
                )
                vals["location_id"] = location.id or False

            seller = self.env["commission.seller"].browse()
            if vals.get("seller_id"):
                seller = self.env["commission.seller"].browse(vals["seller_id"]).exists()
                if seller:
                    vals.setdefault("seller_code", seller.code)
                    vals.setdefault("seller_name", seller.name)
            elif vals.get("seller_code"):
                seller = self.env["commission.seller"].sudo().get_or_create_from_sale(
                    vals.get("seller_code"), vals.get("seller_name"), location
                )
                vals["seller_id"] = seller.id or False

            if "document_sign" not in vals:
                vals["document_sign"] = self._document_sign(vals.get("document_type"))
            if "fingerprint" not in vals or not vals.get("fingerprint"):
                vals["fingerprint"] = uuid.uuid4().hex

            prepared.append(vals)

        return super().create(prepared)

    def amount_for_basis(self, basis):
        self.ensure_one()
        raw = {
            "net": self.total_net,
            "price": self.total_price,
            "margin": self.profit,
        }.get(basis, self.total_net)
        return (raw or 0.0) * (self.document_sign or 1.0)

    @api.model
    def _parse_date(self, value):
        if not value:
            return False
        if isinstance(value, datetime):
            return value.date()
        text = str(value).strip()
        for fmt in ("%Y.%m.%d", "%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y"):
            try:
                return datetime.strptime(text, fmt).date()
            except ValueError:
                continue
        raise ValidationError(_("Fecha no reconocida en fuente: %s") % text)

    @api.model
    def _to_float(self, value):
        if value in (None, ""):
            return 0.0
        if isinstance(value, (int, float)):
            return float(value)
        text = str(value).strip().replace(" ", "")
        if "," in text and "." not in text:
            text = text.replace(",", ".")
        elif "," in text and "." in text:
            text = text.replace(",", "")
        try:
            return float(text)
        except ValueError as exc:
            raise ValidationError(_("Valor numérico no reconocido en fuente: %s") % value) from exc

    @api.model
    def _row_as_mapping(self, row):
        if isinstance(row, dict):
            normalized = {_norm_key(k): v for k, v in row.items()}
            return {field: normalized.get(_norm_key(field)) for field in API_FIELDS}

        if isinstance(row, (list, tuple)):
            if len(row) >= len(API_FIELDS):
                return dict(zip(API_FIELDS, row[: len(API_FIELDS)]))
            if len(row) == len(LEGACY_API_FIELDS):
                mapping = dict(zip(LEGACY_API_FIELDS, row))
                mapping["Cantidad"] = 0.0
                return mapping
            raise ValidationError(
                _("La fila tiene %s columnas; se esperan %s con Cantidad.")
                % (len(row), len(API_FIELDS))
            )

        raise ValidationError(_("Formato de fila no soportado: %s") % type(row).__name__)

    @api.model
    def _fingerprint(self, mapping, occurrence=1):
        canonical = []
        for key in API_FIELDS:
            value = mapping.get(key)
            if isinstance(value, str):
                value = value.strip()
            canonical.append(value)
        canonical.append(["__occurrence__", occurrence])
        payload = json.dumps(canonical, ensure_ascii=False, sort_keys=False, default=str)
        return hashlib.sha1(payload.encode("utf-8")).hexdigest()

    @api.model
    def _document_sign(self, document_type):
        code = _clean(document_type)
        conf = self.env["commission.document.type"].search([("code", "=", code)], limit=1)
        return -1.0 if conf and conf.sign == "-1" else 1.0

    @api.model
    def _mapping_to_vals(self, mapping):
        # Master creation is intentionally NOT done here. create() owns that rule so
        # every insertion path behaves the same way.
        quantity = abs(self._to_float(mapping.get("Cantidad")))
        return {
            "raw_payload": json.dumps(mapping, ensure_ascii=False, default=str, indent=2),
            "document_type": _clean(mapping.get("Tipo")),
            "number": _clean(mapping.get("Numero")),
            "invoice": _clean(mapping.get("Factura")),
            "registration_date": self._parse_date(mapping.get("Fecha_Registro")),
            "due_date": self._parse_date(mapping.get("Vence")),
            "client": _clean(mapping.get("Cliente")),
            "seller_name": _clean(mapping.get("Vendedor")),
            "seller_code": _clean(mapping.get("CodVendedor")),
            "warehouse": _clean(mapping.get("bodega")),
            "product_line": _clean(mapping.get("Linea")),
            "brand": _clean(mapping.get("Marca")),
            "product_code": _clean(mapping.get("Codproducto")),
            "product_name": _clean(mapping.get("nProducto")),
            "quantity": quantity,
            "cost": self._to_float(mapping.get("costo")),
            "total_cost": self._to_float(mapping.get("Total_Costo")),
            "total_price": self._to_float(mapping.get("Total_Precio")),
            "discount_percent": self._to_float(mapping.get("Porc_Descuento")),
            "card_percent": self._to_float(mapping.get("pTarjeta")),
            "total_net": self._to_float(mapping.get("Total_Neto")),
            "price_indicator": self._to_float(mapping.get("Indica_Precio")),
            "discount": self._to_float(mapping.get("Descuento")),
            "profit": self._to_float(mapping.get("Utilidad")),
            "profit_percent": self._to_float(mapping.get("PorcUtilidad")),
            "payment_method": _clean(mapping.get("Forma_pago")),
            "supplier": _clean(mapping.get("Proveedor")),
            "origin": _clean(mapping.get("Origen")),
            "location_code": _clean(mapping.get("localidad")),
            "location_name": _clean(mapping.get("nLocal")),
            "document_sign": self._document_sign(mapping.get("Tipo")),
        }

    @api.model
    def import_rows(self, rows, sync=None):
        """Normalize and insert a batch. Masters are generated by create()."""
        created = 0
        skipped = 0
        errors = []
        occurrences = {}

        for idx, row in enumerate(rows or [], start=1):
            try:
                mapping = self._row_as_mapping(row)
                base_fp = self._fingerprint(mapping, occurrence=0)
                occurrences[base_fp] = occurrences.get(base_fp, 0) + 1
                fingerprint = self._fingerprint(mapping, occurrence=occurrences[base_fp])

                if self.search_count([("fingerprint", "=", fingerprint)], limit=1):
                    skipped += 1
                    continue

                vals = self._mapping_to_vals(mapping)
                vals["fingerprint"] = fingerprint
                if sync:
                    vals["sync_id"] = sync.id
                self.create(vals)
                created += 1
            except Exception as exc:  # one bad row must not lose the full batch
                _logger.exception("Error importing commission sale row %s", idx)
                errors.append("Fila %s: %s" % (idx, exc))

        return {"created": created, "skipped": skipped, "errors": errors}
