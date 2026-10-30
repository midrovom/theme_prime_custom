"""ERP GET adapter. Excel and API share the same invoice engine and publisher."""
from datetime import date, datetime
import hashlib
import json
import re
from zoneinfo import ZoneInfo

from .engine import as_date, invoice_key, normalize, number

ENDPOINT = "getdatosdespachos"
MAX_ROWS = 500_000
MAX_RESPONSE_BYTES = 128 * 1024 * 1024
MAX_CHUNK_BYTES = 20 * 1024 * 1024
NUMERIC_FIELDS = (
    "Facturado", "DespachoFisico", "AjusteDevolucion", "Despachado", "Pendiente",
    "PesoPendiente", "PesoDespacho", "PesoFacturado", "PesoAjusteDevolucion",
    "CajasPendientes", "PalletsPendientes", "PalletsFacturados",
)
FIELD_NAMES = (
    "TipoFactura", "NumeroFactura", "Factura", "FechaFactura", "HoraFactura",
    "Ciudad", "Cond_Entrega", "CodCliente", "Cliente", "Vendedor", "CodBodega",
    "Bodega", "CodProducto", "Producto", "UltimoDespacho", "EstadoDespacho",
    "Direccion", "Comentario", "Bloques", "Ubicaciones", *NUMERIC_FIELDS,
)


class DispatchAPIError(ValueError):
    """Messages are safe for operators; never contain credentials or raw bodies."""


def _key(value):
    return re.sub(r"[^A-Z0-9]", "", normalize(value))


ALIASES = {_key(name): name for name in FIELD_NAMES}
ALIASES.update({"TIPO": "TipoFactura", "NUMERO": "NumeroFactura",
                "PESODESPACHADO": "PesoDespacho", "FECHAULTIMODESPACHO": "UltimoDespacho"})


def _check_pagination(meta):
    pagination = meta.get("PAGINATION") or {}
    pagination = {_key(k): v for k, v in pagination.items()} if isinstance(pagination, dict) else {}
    for values in (meta, pagination):
        if (values.get("HASMORE") or values.get("NEXTPAGE") or values.get("NEXT")
                or (isinstance(values.get("LINKS"), dict) and values["LINKS"].get("next"))):
            raise DispatchAPIError("La API devolvió una página parcial. getdatosdespachos debe entregar el corte completo.")
        for name in ("TOTALPAGES", "LASTPAGE"):
            if values.get(name) is not None:
                try:
                    partial = int(values[name]) > 1
                except (ValueError, TypeError):
                    raise DispatchAPIError("La API contiene metadatos de paginación inválidos.") from None
                if partial:
                    raise DispatchAPIError("La API está paginada. getdatosdespachos debe entregar el corte completo.")


def _date(value, label, timezone="America/Guayaquil"):
    if value in (None, "", False):
        return None
    try:
        if isinstance(value, datetime):
            return (value.astimezone(ZoneInfo(timezone)) if value.tzinfo else value).date().isoformat()
        if isinstance(value, date):
            return as_date(value).isoformat()
        text = str(value).strip()
        # SQL Server commonly serializes date columns as ISO timestamps.
        if len(text) > 10 and text[10] in ("T", " "):
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            return (parsed.astimezone(ZoneInfo(timezone)) if parsed.tzinfo else parsed).date().isoformat()
        return as_date(text).isoformat()
    except (ValueError, TypeError, OverflowError):
        raise DispatchAPIError("%s: %s debe ser una fecha ISO YYYY-MM-DD válida." % (ENDPOINT, label)) from None


def _unwrap(raw, timezone="America/Guayaquil"):
    if isinstance(raw, (str, bytes)):
        try:
            raw = json.loads(raw)
        except (ValueError, TypeError):
            raise DispatchAPIError("%s no devolvió JSON válido." % ENDPOINT) from None
    cutoff, expected = None, None
    for _ in range(8):
        if isinstance(raw, list):
            if not raw:
                # A blank feed is not evidence that the whole operation is empty.
                raise DispatchAPIError("La API no devolvió registros. Se conserva el corte vigente; revise el origen.")
            if len(raw) > MAX_ROWS or any(not isinstance(row, dict) for row in raw):
                raise DispatchAPIError("La API debe devolver hasta 500.000 registros de tipo objeto.")
            if expected is not None and expected != len(raw):
                raise DispatchAPIError("La API devolvió una carga incompleta: el control de líneas no coincide.")
            return raw, cutoff
        if not isinstance(raw, dict):
            break
        meta = {_key(k): v for k, v in raw.items()}
        if meta.get("SUCCESS") is False or meta.get("OK") is False or meta.get("ERROR"):
            raise DispatchAPIError("%s informó un error. Revise el servicio del ERP." % ENDPOINT)
        _check_pagination(meta)
        for name in ("CUTOFFDATE", "FECHACORTE"):
            if meta.get(name) not in (None, "", False):
                current = _date(meta[name], "fecha_corte", timezone)
                if cutoff and cutoff != current:
                    raise DispatchAPIError("La API contiene fechas de corte contradictorias.")
                cutoff = current
        controls = ("TOTALROWS", "TOTALRECORDS", "TOTALLINEAS")
        if any(name in meta for name in ("DATA", "RESULT", "RESULTS", "ITEMS", "ROWS", "RECORDS", "RESPONSE", "PAYLOAD")):
            controls += ("TOTAL",)
        for name in controls:
            if name in meta:
                value = meta[name]
                if isinstance(value, bool) or not str(value).isdigit():
                    raise DispatchAPIError("El control de líneas de la API debe ser un entero no negativo.")
                if expected is not None and expected != int(value):
                    raise DispatchAPIError("La API contiene controles de líneas contradictorios.")
                expected = int(value)
        for name in ("DATA", "RESULT", "RESULTS", "ITEMS", "ROWS", "RECORDS", "RESPONSE", "PAYLOAD"):
            if name in meta and isinstance(meta[name], (dict, list)):
                raw = meta[name]
                break
        else:
            if _key("TipoFactura") in meta or "TIPO" in meta:
                raw = [raw]
                continue
            break
    raise DispatchAPIError("%s debe devolver una lista de registros, directamente o dentro de data/result/items/rows." % ENDPOINT)


def convert_dispatch_payload(raw, today, timezone="America/Guayaquil"):
    """Normalize SQL/Excel column names without inferring unknown kg or pallets."""
    received, cutoff = _unwrap(raw, timezone)
    cutoff = _date(cutoff or today, "fecha_corte", timezone)
    if date.fromisoformat(cutoff) > as_date(today):
        raise DispatchAPIError("El corte recibido de la API es posterior a hoy.")
    rows, winners = [], {}
    for index, item in enumerate(received, 1):
        row = {}
        for name, value in item.items():
            canonical = ALIASES.get(_key(name), name)
            if canonical in row and row[canonical] != value:
                raise DispatchAPIError("La línea %s contiene columnas equivalentes con valores distintos." % index)
            row[canonical] = value
        for name in ("TipoFactura", "NumeroFactura"):
            value = row.get(name)
            if isinstance(value, bool) or not isinstance(value, (str, int)) or not str(value).strip():
                raise DispatchAPIError("La línea %s necesita %s como texto o entero; conserve los ceros iniciales como texto." % (index, name))
            row[name] = normalize(value) if name == "TipoFactura" else str(value).strip()
        try:
            identity = invoice_key(row)
            for name in NUMERIC_FIELDS:
                if row.get(name) not in (None, ""):
                    row[name] = number(row[name], name)
            for name in ("Facturado", "DespachoFisico", "Pendiente"):
                if row.get(name) in (None, ""):
                    raise ValueError()
            for name in ("FechaFactura", "UltimoDespacho"):
                if name in row:
                    row[name] = _date(row[name], name, timezone)
            # Missing warehouse codes must not collapse different named origins.
            if row.get("CodBodega") in (None, "") and row.get("Bodega"):
                row["CodBodega"] = normalize(row["Bodega"])
            json.dumps(row, allow_nan=False)
        except DispatchAPIError:
            raise
        except (ValueError, TypeError, OverflowError):
            raise DispatchAPIError("Línea %s: revise Facturado, DespachoFisico, Pendiente y los campos numéricos del contrato." % index) from None
        rows.append(row)
        detail = (identity, normalize(row.get("CodBodega")), str(row.get("CodProducto") or "").strip())
        winners[detail] = row
    # Same effective records in a different order are unchanged. Conflicting
    # repeated details retain the engine's last-observation-wins convention.
    digest = hashlib.sha256()
    for key in sorted(winners):
        digest.update(json.dumps(winners[key], ensure_ascii=False, sort_keys=True, allow_nan=False,
                                 separators=(",", ":")).encode())
        digest.update(b"\n")
    return {"rows": rows, "cutoff_date": cutoff, "checksum": digest.hexdigest(),
            "unique_lines": len(winners), "duplicate_rows": len(rows) - len(winners)}


def iter_api_chunks(rows):
    """Respect the existing authenticated intake's row and byte limits."""
    chunk, size = [], 2
    for row in rows:
        length = len(json.dumps(row, ensure_ascii=False, sort_keys=True, allow_nan=False,
                                separators=(",", ":")).encode())
        if length + 2 > MAX_CHUNK_BYTES:
            raise DispatchAPIError("Una línea de la API supera el límite de 20 MiB.")
        if chunk and (len(chunk) >= 5000 or size + length + 1 > MAX_CHUNK_BYTES):
            yield chunk
            chunk, size = [], 2
        chunk.append(row)
        size += length + 1
    if chunk:
        yield chunk


def fetch_dispatch_api(env):
    if "api.administrator" not in env.registry:
        raise DispatchAPIError("Instale API Administrator para consultar getdatosdespachos.")
    records = env["api.administrator"].sudo().with_company(env.company).search([
        ("name", "=", ENDPOINT), ("type", "=", "get"), ("status", "=", "A"),
        ("company_id", "=", env.company.id),
    ], limit=2)
    if not records:
        raise DispatchAPIError("Configure una API GET activa llamada getdatosdespachos para esta empresa en API Administrator.")
    if len(records) != 1:
        raise DispatchAPIError("Existe más de una API GET activa llamada getdatosdespachos en esta empresa. Mantenga una sola.")
    return records[0].call_dispatch_api()
