"""Streaming XLSX reader. No Excel dependency is needed on the Odoo server."""
from datetime import datetime, timedelta, timezone
from io import BytesIO
from posixpath import dirname, normpath, join
from zipfile import ZipFile, BadZipFile
import xml.etree.ElementTree as ET

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
REQUIRED = {"TipoFactura", "NumeroFactura", "FechaFactura", "CodBodega", "Facturado", "DespachoFisico", "Pendiente"}
DATE_COLUMNS = {"FechaFactura", "UltimoDespacho"}
CRITICAL_COLUMNS = REQUIRED | DATE_COLUMNS | {"Ciudad", "Cond_Entrega", "AjusteDevolucion", "Despachado", "PesoPendiente", "PesoDespacho", "PesoFacturado", "PesoAjusteDevolucion", "CajasPendientes", "PalletsPendientes"}
MAX_FILE = 40 * 1024 * 1024
MAX_UNCOMPRESSED = 300 * 1024 * 1024
MAX_ROWS = 500_000


def excel_date(value, date1904=False):
    if value in (None, ""):
        return None
    base = datetime(1904, 1, 1) if date1904 else datetime(1899, 12, 30)
    return (base + timedelta(days=float(value))).date().isoformat()


def iter_xlsx_rows(payload):
    if len(payload) > MAX_FILE:
        raise ValueError("El Excel supera 40 MiB. Utilice la API por bloques.")
    try:
        archive = ZipFile(BytesIO(payload))
    except BadZipFile as exc:
        raise ValueError("El archivo no es un XLSX válido.") from exc
    with archive as z:
        if sum(i.file_size for i in z.infolist()) > MAX_UNCOMPRESSED:
            raise ValueError("El contenido expandido del XLSX supera 300 MiB.")
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        prop = wb.find("m:workbookPr", NS)
        date1904 = prop is not None and prop.get("date1904") in ("1", "true")
        sheets = wb.findall("m:sheets/m:sheet", NS)
        if not sheets:
            raise ValueError("El libro no contiene hojas.")
        # The supplied export has one sheet. Reject ambiguous multi-sheet uploads.
        visible = [s for s in sheets if s.get("state", "visible") == "visible"]
        if len(visible) != 1:
            raise ValueError("Suba un XLSX con una sola hoja visible de datos.")
        rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        targets = {r.get("Id"): r.get("Target") for r in rels}
        target = targets[visible[0].get(REL)]
        path = target.lstrip("/") if target.startswith("/") else normpath(join("xl", target))
        if not path.startswith("xl/") or ".." in path.split("/"):
            raise ValueError("Ruta de hoja inválida.")
        strings = []
        if "xl/sharedStrings.xml" in z.namelist():
            with z.open("xl/sharedStrings.xml") as src:
                for _, element in ET.iterparse(src, events=("end",)):
                    if element.tag == "{%s}si" % NS["m"]:
                        strings.append("".join(t.text or "" for t in element.findall(".//m:t", NS)))
                        element.clear()
        headers = None
        count = 0
        with z.open(path) as src:
            for _, element in ET.iterparse(src, events=("end",)):
                if element.tag != "{%s}row" % NS["m"]:
                    continue
                cells = {}
                row_errors = {}
                for cell in element.findall("m:c", NS):
                    ref = cell.get("r", "")
                    col = "".join(c for c in ref if c.isalpha())
                    val = cell.find("m:v", NS)
                    value = val.text if val is not None else None
                    kind = cell.get("t")
                    if kind == "s" and value is not None:
                        value = strings[int(value)]
                    elif kind == "inlineStr":
                        value = "".join(t.text or "" for t in cell.findall(".//m:t", NS))
                    elif kind == "e":
                        field_name = headers.get(col) if headers else None
                        if not field_name or field_name in CRITICAL_COLUMNS:
                            raise ValueError("La celda %s (%s) contiene un error de Excel: %s." % (ref, field_name or "encabezado", value))
                        # Descriptive fields (e.g. Ubicaciones) do not own KPI
                        # calculations. Preserve their error and provenance.
                        row_errors[ref] = {"column": field_name, "error": value or "#ERROR"}
                    elif cell.find("m:f", NS) is not None and value is None:
                        raise ValueError("La fórmula de %s no tiene resultado guardado. Recalcule y guarde el Excel." % ref)
                    if value is not None:
                        cells[col] = value
                element.clear()
                if not cells:
                    continue
                if headers is None:
                    headers = {k: str(v).strip() for k, v in cells.items()}
                    if len(set(headers.values())) != len(headers):
                        raise ValueError("Existen encabezados duplicados.")
                    missing = REQUIRED - set(headers.values())
                    if missing:
                        raise ValueError("Faltan columnas: %s" % ", ".join(sorted(missing)))
                    continue
                record = {headers[k]: v for k, v in cells.items() if k in headers}
                if row_errors:
                    record["__excel_errors__"] = row_errors
                if not any(record.values()):
                    continue
                for key in DATE_COLUMNS:
                    if record.get(key) and str(record[key]).replace(".", "", 1).isdigit():
                        record[key] = excel_date(record[key], date1904)
                count += 1
                if count > MAX_ROWS:
                    raise ValueError("El archivo supera 500.000 líneas.")
                yield record
        if headers is None:
            raise ValueError("La hoja está vacía.")
