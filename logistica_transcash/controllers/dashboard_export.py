"""Excel export for dashboard aggregates (never grants access to raw private guides)."""
from io import BytesIO

from odoo import http
from odoo.exceptions import AccessError, UserError
from odoo.http import request


class TranscashDashboardExport(http.Controller):
    @http.route('/transcash/dashboard/export/xlsx', type='http', auth='user',
                methods=['GET'], csrf=False)
    def export(self, dataset='all', periodo='semana', desde=None, hasta=None, q='', sort='', **kw):
        allowed = {'all', 'tendencia', 'transportistas', 'choferes', 'destinos',
                   'marcas', 'proveedores_producto'}
        if dataset not in allowed:
            return request.not_found()
        # get_dashboard validates dashboard-only group, internal account, range, companies.
        try:
            data = request.env['transcash.dashboard.service'].get_dashboard(periodo, desde, hasta)
        except (AccessError, UserError) as exc:
            return request.make_response(str(exc), status=403)

        try:
            import xlsxwriter
        except ImportError:
            return request.make_response('Falta instalar la dependencia Python xlsxwriter en Odoo.', status=503)

        output = BytesIO()
        book = xlsxwriter.Workbook(output, {'in_memory': True, 'strings_to_formulas': False,
                                           'strings_to_urls': False})
        title_fmt = book.add_format({'bold': True, 'font_size': 16, 'font_color': '#193348'})
        header_fmt = book.add_format({'bold': True, 'bg_color': '#0C192B',
                                      'font_color': '#FFFFFF', 'border': 0})
        num_fmt = book.add_format({'num_format': '#,##0.00'})
        sections = {
            'tendencia': ('Viajes por periodo', [('periodo','Periodo'), ('viajes','Viajes')]),
            'transportistas': ('Transportistas', [('nombre','Empresa transportista'), ('viajes','Viajes'),
                ('guias','Guías'), ('novedades','Guías con novedades'), ('roturas','Guías con rotura'),
                ('pct_novedad','% novedades'), ('pct_rotura','% roturas')]),
            'choferes': ('Choferes', [('nombre','Chofer'), ('viajes','Viajes'),
                ('guias','Guías'), ('novedades','Guías con novedades'), ('roturas','Guías con rotura'),
                ('pct_novedad','% novedades'), ('pct_rotura','% roturas')]),
            'destinos': ('Destinos', [('nombre','Destino'), ('viajes','Viajes'),
                ('guias','Guías'), ('peso_kg','Peso kg'), ('novedades','Guías con novedades'),
                ('roturas','Guías con rotura'), ('pct_novedad','% novedades'),
                ('pct_rotura','% roturas')]),
            'marcas': ('Marcas', [('nombre','Marca'), ('reportes','Reportes'),
                ('guias','Guías con roturas'), ('guias_transportadas','Guías con marca'),
                ('pct_guias_danadas','% guías afectadas'), ('kg_estimados','Kg dañados estimados'),
                ('cantidades','Cantidades por UDM')]),
            'proveedores_producto': ('Proveedores producto', [('nombre','Proveedor de producto'),
                ('reportes','Reportes'), ('guias','Guías con roturas'),
                ('guias_transportadas','Guías con producto'),
                ('pct_guias_danadas','% guías afectadas'), ('kg_estimados','Kg dañados estimados'),
                ('cantidades','Cantidades por UDM')]),
        }
        sheets = list(sections) if dataset == 'all' else [dataset]
        for section in sheets:
            tab, fields = sections[section]
            ws = book.add_worksheet(tab[:31])
            ws.hide_gridlines(2)
            ws.write(0, 0, 'TRANSCASH · ' + tab, title_fmt)
            dates = data['fechas']
            ws.write_string(1, 0, 'Del %s al %s · %s' % (
                dates['desde'], dates['hasta'], dates['agrupacion']))
            ws.write_row(3, 0, [label for _,label in fields], header_fmt)
            ws.freeze_panes(4, 1)
            rows = list(data.get(section, []))
            if dataset != 'all':
                query = str(q or '')[:120].lower().strip()
                if query:
                    rows = [r for r in rows if query in str(r.get('nombre', '')).lower()]
                if sort in {'novedades','roturas','pct_novedad','pct_rotura','viajes',
                            'guias','reportes','kg_estimados','peso_kg'}:
                    rows.sort(key=lambda r: (-float(r.get(sort, 0) or 0),
                                             str(r.get('nombre', ''))))
            for row_idx, record in enumerate(rows, start=4):
                for col_idx, (key, _label) in enumerate(fields):
                    val = record.get(key)
                    if isinstance(val, (int, float)) and not isinstance(val, bool):
                        ws.write_number(row_idx, col_idx, val, num_fmt)
                    else:
                        # write_string prevents spreadsheet-formula injection from ERP names.
                        ws.write_string(row_idx, col_idx, str(val if val is not None else ''))
            ws.set_column(0, 0, 34)
            if len(fields) > 1:
                ws.set_column(1, len(fields)-1, 17)
            ws.autofilter(3, 0, max(4, len(rows)+3), len(fields)-1)
        if dataset == 'all':
            sheet = book.add_worksheet('Resumen KPI')
            sheet.write(0, 0, 'TRANSCASH · Indicadores principales', title_fmt)
            sheet.write_row(2, 0, ['Métrica','Valor'], header_fmt)
            labels = {
                'viajes':'Viajes únicos','guias':'Guías transportadas', 'kg':'Kilos transportados',
                'toneladas':'Toneladas transportadas','guias_novedad':'Guías con novedades',
                'guias_rotura':'Guías con roturas','novedades_abiertas':'Novedades abiertas',
                'pct_guias_rotura':'% guías con roturas',
                'kg_rotura_estimados':'Kg rotura estimados',
            }
            for i, (key, label) in enumerate(labels.items(), 3):
                sheet.write_string(i, 0, label)
                sheet.write_number(i, 1, data['kpis'].get(key, 0), num_fmt)
            sheet.set_column(0, 0, 31)
            sheet.set_column(1, 1, 21)
        book.close()
        filename = 'transcash_%s.xlsx' % dataset
        return request.make_response(output.getvalue(), headers=[
            ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
            ('Content-Disposition', 'attachment; filename="%s"' % filename),
            ('Cache-Control', 'private, no-store'),
            ('X-Content-Type-Options', 'nosniff'),
        ])
