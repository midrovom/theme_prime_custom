import csv
import io
import re
import unicodedata
import zipfile
from posixpath import normpath
from xml.etree import ElementTree as ET


_SPREADSHEET_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_OFFICE_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"


def normalize_product_name(value):
    """Normalize product descriptions for exact name matching.

    Matching intentionally ignores codes and formatting differences. It is not
    fuzzy matching: after normalization the complete product name must be equal.
    """
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.upper()
    # Treat punctuation, line breaks and repeated spaces as separators.
    text = re.sub(r"[^A-Z0-9]+", " ", text)
    return " ".join(text.split())


def _header_key(value):
    return normalize_product_name(value).replace(" ", "")


def _column_index(cell_reference):
    match = re.match(r"([A-Z]+)", cell_reference or "")
    if not match:
        return 0
    result = 0
    for char in match.group(1):
        result = result * 26 + (ord(char) - 64)
    return max(result - 1, 0)


def _xlsx_shared_strings(archive):
    path = "xl/sharedStrings.xml"
    if path not in archive.namelist():
        return []
    root = ET.fromstring(archive.read(path))
    ns = {"m": _SPREADSHEET_NS}
    values = []
    for item in root.findall("m:si", ns):
        values.append("".join(node.text or "" for node in item.findall(".//m:t", ns)))
    return values


def _xlsx_first_sheet_path(archive):
    workbook_path = "xl/workbook.xml"
    rels_path = "xl/_rels/workbook.xml.rels"
    names = set(archive.namelist())
    if workbook_path in names and rels_path in names:
        workbook = ET.fromstring(archive.read(workbook_path))
        ns = {"m": _SPREADSHEET_NS, "r": _OFFICE_REL_NS}
        sheet = workbook.find("m:sheets/m:sheet", ns)
        if sheet is not None:
            relation_id = sheet.attrib.get("{%s}id" % _OFFICE_REL_NS)
            rels = ET.fromstring(archive.read(rels_path))
            for relation in rels.findall("{%s}Relationship" % _PACKAGE_REL_NS):
                if relation.attrib.get("Id") == relation_id:
                    target = relation.attrib.get("Target", "")
                    if target.startswith("/"):
                        target = target.lstrip("/")
                    else:
                        target = normpath("xl/%s" % target)
                    if target in names:
                        return target
    sheets = sorted(
        name for name in names
        if name.startswith("xl/worksheets/") and name.endswith(".xml")
    )
    if not sheets:
        raise ValueError("El archivo XLSX no contiene hojas de cálculo.")
    return sheets[0]


def _parse_xlsx(data):
    rows = []
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        shared = _xlsx_shared_strings(archive)
        sheet_path = _xlsx_first_sheet_path(archive)
        root = ET.fromstring(archive.read(sheet_path))
        ns = {"m": _SPREADSHEET_NS}
        for row in root.findall(".//m:sheetData/m:row", ns):
            values = {}
            max_index = -1
            for cell in row.findall("m:c", ns):
                index = _column_index(cell.attrib.get("r"))
                max_index = max(max_index, index)
                cell_type = cell.attrib.get("t")
                if cell_type == "inlineStr":
                    value = "".join(
                        node.text or "" for node in cell.findall(".//m:t", ns)
                    )
                else:
                    value_node = cell.find("m:v", ns)
                    raw = value_node.text if value_node is not None else ""
                    if cell_type == "s" and raw not in (None, ""):
                        try:
                            value = shared[int(raw)]
                        except (ValueError, IndexError):
                            value = raw
                    else:
                        value = raw or ""
                values[index] = value
            if max_index >= 0:
                row_values = [values.get(index, "") for index in range(max_index + 1)]
                if any(str(value).strip() for value in row_values):
                    rows.append(row_values)
    return rows


def _decode_csv(data):
    for encoding in ("utf-8-sig", "utf-16", "cp1252", "latin1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _parse_csv(data):
    text = _decode_csv(data)
    sample = text[:8192]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        reader = csv.reader(io.StringIO(text), dialect)
    except csv.Error:
        delimiter = ";" if sample.count(";") > sample.count(",") else ","
        reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    return [row for row in reader if any(cell.strip() for cell in row)]


def _parse_xls_optional(data):
    try:
        import xlrd  # optional; not required for XLSX/CSV
    except ImportError as exc:
        raise ValueError(
            "El formato .xls antiguo requiere la librería Python xlrd. "
            "Guarde el archivo como .xlsx o .csv para importarlo sin dependencias adicionales."
        ) from exc
    workbook = xlrd.open_workbook(file_contents=data)
    sheet = workbook.sheet_by_index(0)
    return [[sheet.cell_value(row, col) for col in range(sheet.ncols)] for row in range(sheet.nrows)]


def _product_header_score(value):
    key = _header_key(value)
    exact = {
        "NPRODUCTO", "PRODUCTO", "NOMBREPRODUCTO", "NOMBREDELPRODUCTO",
        "DESCRIPCION", "DESCRIPCIONPRODUCTO", "DESCRIPCIONDELPRODUCTO",
        "PRODUCTNAME", "PRODUCTDESCRIPTION", "DESCRIPTION",
        "ARTICULO", "NOMBREARTICULO", "DESCRIPCIONARTICULO",
        "ITEMDESCRIPTION", "ITEMNAME",
    }
    if key in exact:
        return 100
    if any(token in key for token in ("CODIGO", "CODPRODUCTO", "CODE", "SKU", "BARRA")):
        return 0
    if "PRODUCTO" in key and ("NOMBRE" in key or "DESCRIP" in key):
        return 95
    if "PRODUCTO" in key:
        return 85
    if "DESCRIP" in key:
        return 80
    if "NOMBRE" in key and ("ITEM" in key or "ARTICULO" in key):
        return 75
    return 0


def _code_header_score(value):
    key = _header_key(value)
    exact = {
        "CODPRODUCTO", "CODIGOPRODUCTO", "CODIGO", "CODE", "PRODUCTCODE",
        "SKU", "ITEMCODE", "CODARTICULO", "CODIGOARTICULO",
    }
    if key in exact:
        return 100
    if "COD" in key and ("PRODUCT" in key or "ARTIC" in key or key == "CODIGO"):
        return 80
    return 0


def _alpha_ratio(value):
    text = str(value or "")
    if not text:
        return 0.0
    alpha = sum(char.isalpha() for char in text)
    return alpha / max(len(text), 1)


def _infer_product_column(rows, start_row=1):
    max_columns = max((len(row) for row in rows), default=0)
    if max_columns == 1:
        return 0
    best_index = None
    best_score = -1.0
    sample_rows = rows[start_row:start_row + 80]
    for index in range(max_columns):
        values = [
            str(row[index]).strip() for row in sample_rows
            if index < len(row) and str(row[index]).strip()
        ]
        if not values:
            continue
        average_length = sum(len(value) for value in values) / len(values)
        average_alpha = sum(_alpha_ratio(value) for value in values) / len(values)
        # Product descriptions are generally longer and more textual than codes.
        score = average_length * (0.5 + average_alpha) + min(len(values), 20) * 0.05
        if score > best_score:
            best_score = score
            best_index = index
    return best_index


def extract_promotion_products(data, filename=""):
    """Return promotion rows using only the product-name column for matching.

    The optional source code is retained for audit but is never part of the
    comparison key. Duplicate names are removed after normalization.
    """
    if not data:
        raise ValueError("El archivo está vacío.")
    lower_name = (filename or "").lower()
    try:
        if data[:2] == b"PK" or lower_name.endswith(".xlsx"):
            rows = _parse_xlsx(data)
        elif lower_name.endswith(".xls"):
            rows = _parse_xls_optional(data)
        else:
            rows = _parse_csv(data)
    except (zipfile.BadZipFile, ET.ParseError, KeyError, IndexError) as exc:
        raise ValueError("El archivo no tiene una estructura XLSX/CSV válida.") from exc
    if not rows:
        raise ValueError("El archivo no contiene filas con datos.")

    header = rows[0]
    product_scores = [(_product_header_score(value), index) for index, value in enumerate(header)]
    product_score, product_index = max(product_scores, default=(0, None))
    code_scores = [(_code_header_score(value), index) for index, value in enumerate(header)]
    code_score, code_index = max(code_scores, default=(0, None))

    header_used = product_score > 0
    if not header_used:
        nonempty_header_columns = [index for index, value in enumerate(header) if str(value).strip()]
        if len(nonempty_header_columns) == 1 and max(len(row) for row in rows) == 1:
            product_index = nonempty_header_columns[0]
            header_used = False
        else:
            product_index = _infer_product_column(rows, start_row=1)
            header_used = True
    if product_index is None:
        raise ValueError(
            "No fue posible identificar la columna con el nombre del producto. "
            "Use un encabezado como nProducto, Producto, Nombre Producto o Descripción."
        )
    if code_score <= 0:
        code_index = None

    data_rows = rows[1:] if header_used else rows
    products = []
    seen = set()
    duplicates = 0
    empty = 0
    for source_row, row in enumerate(data_rows, start=2 if header_used else 1):
        value = row[product_index] if product_index < len(row) else ""
        product_name = str(value or "").strip()
        normalized = normalize_product_name(product_name)
        if not normalized:
            empty += 1
            continue
        if normalized in seen:
            duplicates += 1
            continue
        seen.add(normalized)
        source_code = ""
        if code_index is not None and code_index < len(row):
            source_code = str(row[code_index] or "").strip()
        products.append({
            "product_name": product_name,
            "normalized_name": normalized,
            "source_code": source_code,
            "source_row": source_row,
        })

    if not products:
        raise ValueError("No se encontraron nombres de producto válidos en el archivo.")

    if product_score > 0:
        selected_column = str(header[product_index] or "").strip() or "Producto"
    elif header_used:
        selected_column = "Columna %s (inferida por contenido)" % (product_index + 1)
    else:
        selected_column = "Columna %s" % (product_index + 1)
    return {
        "products": products,
        "selected_column": selected_column,
        "rows_read": len(data_rows),
        "duplicates": duplicates,
        "empty": empty,
    }
