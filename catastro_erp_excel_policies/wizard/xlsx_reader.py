"""Lector XLSX mínimo, sin dependencias externas, con límites de tamaño.

Lee la primera hoja del libro y sus valores cacheados; no evalúa fórmulas.
Solo admite los tipos numérico, cadena compartida, inline string y booleano.
"""
import io
import re
import zipfile
import xml.etree.ElementTree as ET

MAX_XLSX_BYTES = 8 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 24 * 1024 * 1024
MAX_DATA_ROWS = 10000
MAX_COLUMNS = 24

N = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
REL = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
P = '{http://schemas.openxmlformats.org/package/2006/relationships}'
_CELL_RE = re.compile(r'^([A-Z]+)([0-9]+)$')


def _col_index(cellref):
    match = _CELL_RE.match(cellref.upper())
    if not match:
        raise ValueError('Referencia de celda inválida: %s' % cellref)
    col = 0
    for letter in match.group(1):
        col = col * 26 + ord(letter) - 64
    return col - 1


def _shared_strings(z):
    if 'xl/sharedStrings.xml' not in z.namelist():
        return []
    root = ET.fromstring(z.read('xl/sharedStrings.xml'))
    return [''.join(t.text or '' for t in si.iter(N + 't')) for si in root.findall(N + 'si')]


def _first_sheet_path(z):
    wb = ET.fromstring(z.read('xl/workbook.xml'))
    sheet = wb.find(N + 'sheets/' + N + 'sheet')
    if sheet is None:
        raise ValueError('El Excel no tiene hojas de trabajo.')
    rel_id = sheet.attrib.get(REL + 'id')
    relationships = ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
    targets = {
        item.attrib.get('Id'): item.attrib.get('Target')
        for item in relationships.findall(P + 'Relationship')
    }
    target = targets.get(rel_id)
    if not target:
        raise ValueError('No se pudo localizar la primera hoja del Excel.')
    path = target.lstrip('/') if target.startswith('/') else 'xl/' + target
    path = path.replace('xl/xl/', 'xl/')
    if '..' in path.split('/') or not path.startswith('xl/worksheets/'):
        raise ValueError('Ruta interna de Excel no permitida.')
    return path


def read_first_sheet(payload):
    if not payload or len(payload) > MAX_XLSX_BYTES:
        raise ValueError('El archivo XLSX debe tener como máximo 8 MB.')
    try:
        z = zipfile.ZipFile(io.BytesIO(payload))
    except (zipfile.BadZipFile, OSError) as exc:
        raise ValueError('El archivo no es un XLSX válido.') from exc
    with z:
        if sum(i.file_size for i in z.infolist()) > MAX_UNCOMPRESSED_BYTES:
            raise ValueError('El Excel descomprimido es demasiado grande.')
        shared = _shared_strings(z)
        root = ET.fromstring(z.read(_first_sheet_path(z)))
        data = root.find(N + 'sheetData')
        if data is None:
            raise ValueError('El Excel no contiene filas.')
        matrix = []
        for row in data.findall(N + 'row'):
            if len(matrix) >= MAX_DATA_ROWS + 1:
                raise ValueError('El Excel supera el máximo de 10.000 productos.')
            cols = {}
            for cell in row.findall(N + 'c'):
                idx = _col_index(cell.attrib.get('r', 'A1'))
                if idx >= MAX_COLUMNS:
                    continue
                typ = cell.attrib.get('t')
                value_node = cell.find(N + 'v')
                if typ == 'inlineStr':
                    text = ''.join(n.text or '' for n in cell.iter(N + 't'))
                elif value_node is None:
                    text = ''
                elif typ == 's':
                    try:
                        text = shared[int(value_node.text or '0')]
                    except (ValueError, IndexError):
                        raise ValueError('Índice de texto compartido inválido.')
                else:
                    text = value_node.text or ''
                cols[idx] = str(text).strip()
            if cols:
                matrix.append([cols.get(i, '') for i in range(max(cols) + 1)])
        if not matrix:
            raise ValueError('La primera hoja del Excel está vacía.')
        return matrix
