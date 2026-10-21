# -*- coding: utf-8 -*-
"""Excel exports for visible authorized dashboard tables (standard library only)."""
import io
import math
import re
from datetime import datetime
from xml.sax.saxutils import escape
from zipfile import ZipFile, ZIP_DEFLATED

MAX_ROWS = 200000
MAX_COLS = 45


def _col(number):
    letters = ''
    while number:
        number, rest = divmod(number - 1, 26)
        letters = chr(65 + rest) + letters
    return letters


def _safe_text(value):
    # Excel treats leading "= + - @" as a formula if imported by another tool;
    # we always serialize text with t=inlineStr so it is never a formula.
    text = str(value if value is not None else '')[:32767]
    text = ''.join(c for c in text if c in '\t\n\r' or ord(c) >= 32)
    return escape(text, {'"': '&quot;', "'": '&apos;'})


def _cell(value, row_no, column, style=0):
    ref = '%s%s' % (_col(column), row_no)
    if isinstance(value, bool):
        value = str(value)
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return '<c r="%s" s="%s"><v>%s</v></c>' % (ref, style, value)
    if value is None:
        return '<c r="%s"/>' % ref
    return '<c r="%s" s="%s" t="inlineStr"><is><t xml:space="preserve">%s</t></is></c>' % (ref, style, _safe_text(value))


def build_table_xlsx(title, company, headers, rows, period='', filters=''):
    if not isinstance(headers, list) or not headers or len(headers) > MAX_COLS:
        raise ValueError('Columnas no válidas para exportar.')
    if not isinstance(rows, list) or len(rows) > MAX_ROWS:
        raise ValueError('La tabla supera el máximo de filas.')
    cols = len(headers)
    for row in rows:
        if not isinstance(row, list) or len(row) != cols:
            raise ValueError('Filas o columnas inconsistentes.')
    def xrow(index, vals, styles=None):
        return '<row r="%s">%s</row>' % (index, ''.join(_cell(v, index, i + 1, (styles or [0]*cols)[i]) for i, v in enumerate(vals)))
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    header_rows = [xrow(1, [str(title)[:180]] + [''] * (cols-1), [1]*cols),
                xrow(2, ['Empresa: %s' % company] + [''] * (cols-1)),
                xrow(3, ['Período: %s' % (period or 'Último corte')] + [''] * (cols-1)),
                xrow(4, ['Filtros: %s' % (filters or 'Sin filtros')] + [''] * (cols-1)),
                xrow(5, ['Generado: %s' % now] + [''] * (cols-1)),
                xrow(7, headers, [2]*cols)]
    end = max(7, 7 + len(rows))
    lastcol = _col(cols)
    columns = ''.join('<col min="%s" max="%s" width="%s" customWidth="1"/>' % (i,i,46 if i<=2 else 20) for i in range(1,cols+1))
    sheet_prefix = ('''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><dimension ref="A1:%s%s"/>
<sheetViews><sheetView workbookViewId="0"><pane ySplit="7" topLeftCell="A8" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>
<sheetFormatPr defaultRowHeight="17"/><cols>%s</cols><sheetData>''') % (lastcol, end, columns)
    sheet_suffix = '</sheetData><autoFilter ref="A7:%s%s"/></worksheet>' % (lastcol, end)
    def body_rows():
        for i, row in enumerate(rows, start=8):
            cell_styles=[]
            for h,v in zip(headers,row):
                h=str(h).lower()
                if isinstance(v,(int,float)) and not isinstance(v,bool):
                    cell_styles.append(4 if ('margen' in h or '%' in h or 'participación' in h) else (3 if any(term in h for term in ['venta', 'utilidad', 'compras', 'costo', 'precio', 'capital', 'valor', '$', 'inversión']) and not any(x in h for x in ['cantidad vendida', 'cantidad comprada']) else 5))
                else:
                    cell_styles.append(0)
            yield xrow(i,row,cell_styles)
    styles="""<?xml version="1.0" encoding="UTF-8" standalone="yes"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<numFmts count="3"><numFmt numFmtId="164" formatCode="&quot;$&quot;#,##0.00"/><numFmt numFmtId="165" formatCode="0.00&quot;%&quot;"/><numFmt numFmtId="166" formatCode="#,##0.00"/></numFmts>
<fonts count="3"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="15"/><color rgb="FFFFFFFF"/><name val="Calibri"/></font><font><b/><sz val="10"/><color rgb="FFFFFFFF"/><name val="Calibri"/></font></fonts>
<fills count="4"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF123650"/></patternFill></fill><fill><patternFill patternType="solid"><fgColor rgb="FF168B82"/></patternFill></fill></fills>
<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>
<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
<cellXfs count="6"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1"/><xf numFmtId="0" fontId="2" fillId="3" borderId="0" xfId="0" applyFont="1" applyFill="1"/><xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/><xf numFmtId="165" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/><xf numFmtId="166" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/></cellXfs></styleSheet>"""
    buffer=io.BytesIO()
    with ZipFile(buffer, 'w', ZIP_DEFLATED, compresslevel=5) as archive:
        archive.writestr('[Content_Types].xml', """<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/></Types>""")
        archive.writestr('_rels/.rels', """<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>""")
        archive.writestr('xl/workbook.xml', """<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Datos" sheetId="1" r:id="rId1"/></sheets></workbook>""")
        archive.writestr('xl/_rels/workbook.xml.rels', """<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>""")
        archive.writestr('xl/styles.xml', styles)
        with archive.open('xl/worksheets/sheet1.xml','w',force_zip64=True) as writer:
            writer.write(sheet_prefix.encode('utf-8'))
            for line in header_rows:
                writer.write(line.encode('utf-8'))
            for line in body_rows():
                writer.write(line.encode('utf-8'))
            writer.write(sheet_suffix.encode('utf-8'))
    return buffer.getvalue()
