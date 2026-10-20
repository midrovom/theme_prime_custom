# -*- coding: utf-8 -*-
"""Exportación XLSX sin dependencias de terceros y sin ejecutar SQL nuevamente.

Los datos provienen exclusivamente del resultado validado y registrado en Odoo.
El archivo utiliza OpenXML con textos de tipo inlineStr: ningún texto del usuario
puede convertirse en fórmula ejecutable de Excel.
"""
import io
import math
from datetime import datetime
from xml.sax.saxutils import escape
from zipfile import ZipFile, ZIP_DEFLATED

MAX_EXPORT_ROWS = 1000


def _col(n):
    value = ''
    while n:
        n, rem = divmod(n - 1, 26)
        value = chr(65 + rem) + value
    return value


def _cell(pos, value, style=0):
    attr = ' r="%s" s="%s"' % (pos, style)
    if value is None:
        return '<c%s/>' % attr
    if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
        return '<c%s><v>%s</v></c>' % (attr, value)
    # Always inline strings. Escaping prevents XML injection; no Excel formulas.
    txt = escape(''.join(ch for ch in str(value)[:30000] if ord(ch) >= 32 or ch in "\t\n\r"))
    return '<c%s t="inlineStr"><is><t xml:space="preserve">%s</t></is></c>' % (attr, txt)


def build_result_xlsx(result, question, created=None):
    if not isinstance(result, dict) or not isinstance(result.get('filas'), list):
        raise ValueError('Resultado no válido para Excel.')
    rows = result['filas'][:MAX_EXPORT_ROWS]
    metrics = result.get('metricas') or [result.get('metrica') or 'valor']
    labels = result.get('etiquetas') or {}
    totals = result.get('totales') or {}
    if not isinstance(metrics, list) or len(metrics) > 20:
        raise ValueError('Cantidad de indicadores no válida.')
    measures = [str(k) for k in metrics if isinstance(k, str) and k]
    if not measures:
        raise ValueError('No hay indicadores para exportar.')
    period = result.get('periodo') or {}
    when = created or datetime.now()
    headers = ['SKU' if result.get('tipo_resultado') == 'listado_stock' else 'Grupo'] + [labels.get(m) or m for m in measures]
    end_col = _col(len(headers))
    sheet_rows = []
    def add_row(number, values, styles=None):
        s = styles or [0] * len(values)
        sheet_rows.append('<row r="%s">%s</row>' % (
            number, ''.join(_cell('%s%s' % (_col(i + 1), number), v, s[i])
                            for i, v in enumerate(values))))

    add_row(1, ['TRANSCASH · RESULTADO DE CONSULTA'], [1])
    add_row(2, [str(question)[:500]], [2])
    add_row(3, ['Período: %s a %s' % (period.get('desde') or '-', period.get('hasta') or '-')], [2])
    add_row(4, ['Generado: %s' % when.strftime('%Y-%m-%d %H:%M')], [2])
    add_row(6, headers, [3] * len(headers))
    values = [('PRODUCTOS ENCONTRADOS: %s' % result.get('total_filas', len(rows))) if result.get('tipo_resultado') == 'listado_stock' else 'TOTAL'] + [totals.get(m) for m in measures]
    styles = [7] + [5 if m == 'margen' else 4 if m in ('ventas', 'costo_ventas', 'compras', 'utilidad', 'stock_valor', 'precio_promedio') else 6 for m in measures]
    add_row(7, values, styles)
    for j, item in enumerate(rows, start=8):
        item_values = (item.get('metricas') or {}) if isinstance(item, dict) else {}
        vals = [item.get('grupo', '')] + [item_values.get(m) for m in measures]
        add_row(j, vals, [0] + styles[1:])

    last = max(7, 7 + len(rows))
    columns = '<col min="1" max="1" width="43" customWidth="1"/>' + ''.join(
        '<col min="%s" max="%s" width="21" customWidth="1"/>' % (i, i)
        for i in range(2, len(headers)+1))
    worksheet = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                 '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                 '<dimension ref="A1:%s%s"/><sheetViews><sheetView workbookViewId="0">'
                 '<pane ySplit="6" topLeftCell="A7" activePane="bottomLeft" state="frozen"/>'
                 '</sheetView></sheetViews><sheetFormatPr defaultRowHeight="17"/>'
                 '<cols>%s</cols><sheetData>%s</sheetData>'
                 '<autoFilter ref="A6:%s%s"/>'
                 '<pageMargins left="0.25" right="0.25" top="0.5" bottom="0.5" header="0.2" footer="0.2"/>'
                 '</worksheet>') % (end_col, last, columns, ''.join(sheet_rows), end_col, last)
    styles_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
 <numFmts count="3"><numFmt numFmtId="164" formatCode="&quot;$&quot;#,##0.00;[Red](&quot;$&quot;#,##0.00)"/><numFmt numFmtId="165" formatCode="0.00&quot;%&quot;"/><numFmt numFmtId="166" formatCode="#,##0.00"/></numFmts>
 <fonts count="3"><font><sz val="10"/><name val="Calibri"/></font><font><b/><sz val="16"/><color rgb="FFFFFFFF"/><name val="Calibri"/></font><font><b/><sz val="10"/><color rgb="FFFFFFFF"/><name val="Calibri"/></font></fonts>
 <fills count="4"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF15395B"/><bgColor indexed="64"/></patternFill></fill><fill><patternFill patternType="solid"><fgColor rgb="FF237A75"/><bgColor indexed="64"/></patternFill></fill></fills>
 <borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>
 <cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
 <cellXfs count="8"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1"/><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="2" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1"/><xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/><xf numFmtId="165" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/><xf numFmtId="166" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/><xf numFmtId="0" fontId="0" fillId="3" borderId="0" xfId="0" applyFill="1"/></cellXfs>
</styleSheet>'''
    output = io.BytesIO()
    with ZipFile(output, 'w', ZIP_DEFLATED) as f:
        f.writestr('[Content_Types].xml', '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/></Types>''')
        f.writestr('_rels/.rels', '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>''')
        f.writestr('xl/workbook.xml', '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Resultado" sheetId="1" r:id="rId1"/></sheets></workbook>''')
        f.writestr('xl/_rels/workbook.xml.rels', '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>''')
        f.writestr('xl/styles.xml', styles_xml)
        f.writestr('xl/worksheets/sheet1.xml', worksheet)
    return output.getvalue()
