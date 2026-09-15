import hashlib
import json
import logging
import re
import unicodedata
from decimal import Decimal, InvalidOperation

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

API_SOURCE = "comisiones_transcash_retail"

# Keep the order aligned with transcash_commission.models.sale.API_FIELDS.
SOURCE_FIELDS = [
    "Tipo", "Numero", "Factura", "Fecha_Registro", "Vence", "Cliente",
    "Vendedor", "CodVendedor", "bodega", "Linea", "Marca", "Codproducto",
    "nProducto", "Cantidad", "costo", "Total_Costo", "Total_Precio",
    "Porc_Descuento", "pTarjeta", "Total_Neto", "Indica_Precio", "Descuento",
    "Utilidad", "PorcUtilidad", "Forma_pago", "Proveedor", "Origen",
    "localidad", "nLocal",
]

DATE_FIELDS = {"Fecha_Registro", "Vence"}
NUMERIC_FIELDS = {
    "Cantidad", "costo", "Total_Costo", "Total_Precio", "Porc_Descuento",
    "pTarjeta", "Total_Neto", "Indica_Precio", "Descuento", "Utilidad",
    "PorcUtilidad",
}


def _normalize_text(value):
    text = unicodedata.normalize("NFKC", str(value or ""))
    # API values historically contain padded fixed-width strings and line breaks.
    text = re.sub(r"\s+", " ", text).strip()
    return text.casefold()


def _normalize_decimal(value):
    if value in (None, ""):
        return "0"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float, Decimal)):
        text = str(value)
    else:
        text = str(value).strip().replace(" ", "")
        if "," in text and "." not in text:
            text = text.replace(",", ".")
        elif "," in text and "." in text:
            text = text.replace(",", "")
    try:
        number = Decimal(text)
    except (InvalidOperation, ValueError):
        # Let the base importer report the precise numeric validation error later.
        return _normalize_text(value)
    if number == 0:
        return "0"
    normalized = number.normalize()
    # Avoid scientific notation so 12000, 12000.0 and "12000.000" hash equally.
    result = format(normalized, "f")
    if "." in result:
        result = result.rstrip("0").rstrip(".")
    return result or "0"


class CommissionSale(models.Model):
    _inherit = "commission.sale"

    api_bridge_source = fields.Char(
        string="Origen API bridge",
        readonly=True,
        copy=False,
        index=True,
    )
    api_bridge_key = fields.Char(
        string="Clave API bridge",
        readonly=True,
        copy=False,
        index=True,
        help="Clave determinística usada para que una resincronización no duplique ventas.",
    )

    _sql_constraints = [
        (
            "commission_sale_api_bridge_key_unique",
            "unique(api_bridge_source, api_bridge_key)",
            "La venta ya fue importada desde esta fuente API.",
        ),
    ]

    @api.model
    def _bridge_normalized_mapping(self, mapping):
        canonical = []
        for field_name in SOURCE_FIELDS:
            value = mapping.get(field_name)
            if field_name in DATE_FIELDS:
                if not value:
                    normalized = ""
                else:
                    try:
                        parsed = self._parse_date(value)
                        normalized = parsed.isoformat() if parsed else ""
                    except Exception:
                        normalized = _normalize_text(value)
            elif field_name in NUMERIC_FIELDS:
                normalized = _normalize_decimal(value)
            else:
                normalized = _normalize_text(value)
            canonical.append(normalized)
        return canonical

    @api.model
    def _bridge_row_hash(self, mapping):
        payload = json.dumps(
            self._bridge_normalized_mapping(mapping),
            ensure_ascii=False,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @api.model
    def _bridge_source_name(self, sync=None):
        company = sync.company_id if sync and "company_id" in sync._fields else self.env.company
        company_id = company.id or self.env.company.id
        return "%s:%s" % (API_SOURCE, company_id)

    @api.model
    def _bridge_key(self, row_hash, occurrence):
        raw = "%s:%s" % (row_hash, int(occurrence or 1))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @api.model
    def _bridge_backfill_legacy_keys(self, sync, incoming_hash_counts):
        """Assign bridge keys to prior imports so the first upgraded re-sync is idempotent.

        Version 1.0.x used the base module fingerprint. Existing rows therefore do not
        yet have ``api_bridge_key``. We backfill only the requested date interval and
        only rows that retain the source payload. If the database already contains
        duplicates from prior runs, they receive occurrences 1..N. A new API response
        with N/2 genuine rows will match occurrences 1..N/2 and will not create more.
        Existing historical duplicates are deliberately not deleted automatically.
        """
        if not sync or not sync.date_from or not sync.date_to or not incoming_hash_counts:
            return

        source_name = self._bridge_source_name(sync)
        domain = [
            ("registration_date", ">=", sync.date_from),
            ("registration_date", "<=", sync.date_to),
            ("api_bridge_key", "=", False),
            ("raw_payload", "!=", False),
        ]
        legacy_sales = self.sudo().search(domain, order="id asc")
        if not legacy_sales:
            return

        # Existing keys (if a previous upgraded synchronization already tagged some rows).
        existing_key_records = self.sudo().search([
            ("api_bridge_source", "=", source_name),
            ("api_bridge_key", "!=", False),
            ("registration_date", ">=", sync.date_from),
            ("registration_date", "<=", sync.date_to),
        ])
        used_keys = set(existing_key_records.mapped("api_bridge_key"))
        occurrence_by_hash = {}
        tagged = 0

        for sale in legacy_sales:
            try:
                payload = json.loads(sale.raw_payload or "{}")
                mapping = self._row_as_mapping(payload)
                row_hash = self._bridge_row_hash(mapping)
                # Ignore unrelated/manual payloads not present in the current API batch.
                if row_hash not in incoming_hash_counts:
                    continue
                occurrence = occurrence_by_hash.get(row_hash, 0) + 1
                key = self._bridge_key(row_hash, occurrence)
                while key in used_keys:
                    occurrence += 1
                    key = self._bridge_key(row_hash, occurrence)
                occurrence_by_hash[row_hash] = occurrence
                used_keys.add(key)
                sale.sudo().write({
                    "api_bridge_source": source_name,
                    "api_bridge_key": key,
                })
                tagged += 1
            except Exception:
                _logger.exception(
                    "No se pudo generar clave bridge para venta histórica ID %s",
                    sale.id,
                )
        if tagged:
            _logger.info(
                "API bridge: %s ventas históricas etiquetadas para deduplicación (%s - %s)",
                tagged,
                sync.date_from,
                sync.date_to,
            )

    @api.model
    def import_rows(self, rows, sync=None):
        """Idempotent import for the commission API bridge.

        For non-bridge calls, preserve the base module behavior. For bridge syncs, use
        a canonical row key that is insensitive to harmless representation changes
        (padding, case, numeric formatting and date formatting).
        """
        if not sync or "api_request_url" not in sync._fields:
            return super().import_rows(rows, sync=sync)

        created = 0
        skipped = 0
        errors = []
        prepared = []
        occurrence_by_hash = {}
        incoming_hash_counts = {}

        # Normalize once. This avoids one database lookup per API line.
        for idx, row in enumerate(rows or [], start=1):
            try:
                mapping = self._row_as_mapping(row)
                row_hash = self._bridge_row_hash(mapping)
                occurrence = occurrence_by_hash.get(row_hash, 0) + 1
                occurrence_by_hash[row_hash] = occurrence
                incoming_hash_counts[row_hash] = occurrence
                prepared.append((idx, mapping, row_hash, occurrence))
            except Exception as exc:
                _logger.exception("Error preparando fila API de comisión %s", idx)
                errors.append("Fila %s: %s" % (idx, exc))

        # Make existing 1.0.x data recognizable before checking new keys.
        self._bridge_backfill_legacy_keys(sync, incoming_hash_counts)

        source_name = self._bridge_source_name(sync)
        incoming_keys = [
            self._bridge_key(row_hash, occurrence)
            for _idx, _mapping, row_hash, occurrence in prepared
        ]

        existing_keys = set()
        # PostgreSQL/Odoo handles a few thousand values well; chunk to stay safe with
        # very large periods and avoid oversized SQL IN clauses.
        chunk_size = 2000
        for start in range(0, len(incoming_keys), chunk_size):
            chunk = incoming_keys[start:start + chunk_size]
            if not chunk:
                continue
            records = self.sudo().search([
                ("api_bridge_source", "=", source_name),
                ("api_bridge_key", "in", chunk),
            ])
            existing_keys.update(records.mapped("api_bridge_key"))

        for idx, mapping, row_hash, occurrence in prepared:
            bridge_key = self._bridge_key(row_hash, occurrence)
            if bridge_key in existing_keys:
                skipped += 1
                continue
            try:
                vals = self._mapping_to_vals(mapping)
                vals.update({
                    "api_bridge_source": source_name,
                    "api_bridge_key": bridge_key,
                    # Keep the original base constraint deterministic for new rows too.
                    "fingerprint": hashlib.sha1(
                        ("api-bridge:%s:%s" % (source_name, bridge_key)).encode("utf-8")
                    ).hexdigest(),
                })
                if sync:
                    vals["sync_id"] = sync.id
                # Savepoint keeps one malformed row from rolling back the whole period.
                with self.env.cr.savepoint():
                    self.create(vals)
                existing_keys.add(bridge_key)
                created += 1
            except Exception as exc:
                _logger.exception("Error importing commission API row %s", idx)
                errors.append("Fila %s: %s" % (idx, exc))

        return {"created": created, "skipped": skipped, "errors": errors}
