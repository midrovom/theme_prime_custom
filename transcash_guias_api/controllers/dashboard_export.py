# -*- coding: utf-8 -*-
"""Exportación del BI único. Nunca usa sudo sin validar rol y empresas."""
from io import BytesIO

from odoo import http
from odoo.exceptions import AccessError, UserError
from odoo.http import request


class TranscashBIExport(http.Controller):
    @http.route('/transcash/bi/export/xlsx', type='http', auth='user', methods=['GET'], csrf=False)
    def export(self, dataset='all', periodo='semana', desde=None, hasta=None,
               base='registro', q='', sort='', **kwargs):
        columns = {
            'guias': [('nombre', 'Guía'), ('estado', 'Estado'), ('documento', 'Documento'),
                      ('destino', 'Destino'), ('transportista', 'Transportista'), ('chofer', 'Chofer'),
                      ('ruta', 'Ruta'), ('viaje', 'Embarque'), ('kg', 'Kg'), ('m2', 'm²'),
                      ('metros_lineales', 'Metros lineales'), ('unidades', 'Unidades'),
                      ('pallets', 'Pallets'), ('cajas', 'Cajas'), ('roturas', 'Reportes rotura')],
            'rutas': [('nombre', 'Ruta'), ('estado', 'Estado'), ('destino', 'Destino'),
                      ('transportista', 'Transportista'), ('chofer', 'Chofer'), ('guias', 'Guías'),
                      ('kg', 'Kg'), ('m2', 'm²'), ('unidades', 'Unidades'), ('viaje', 'Embarque')],
            'embarques': [('nombre', 'Viaje'), ('estado', 'Estado'), ('transportista', 'Transportista'),
                          ('chofer', 'Chofer'), ('guias', 'Guías'), ('rutas', 'Rutas'),
                          ('kg', 'Kg'), ('m2', 'm²'), ('unidades', 'Unidades')],
            'transportistas': [('nombre', 'Transportista'), ('guias', 'Guías'), ('viajes', 'Viajes'),
                               ('kg', 'Kg'), ('m2', 'm²'), ('unidades', 'Unidades'),
                               ('novedades', 'Guías con incidencia'), ('pct_novedad', '% incidencias'),
                               ('guias_rotura', 'Guías con daños'), ('roturas', 'Reportes roturas'),
                               ('roturas_pendientes', 'Roturas pendientes'),
                               ('roturas_aprobadas', 'Roturas aprobadas'),
                               ('cantidad_rota_m2', 'm² dañados'),
                               ('cantidad_rota_unidades', 'Unidades dañadas'),
                               ('pct_rotura', '% guías con daño')],
            'choferes': [('nombre', 'Chofer'), ('guias', 'Guías'), ('viajes', 'Viajes'),
                        ('kg', 'Kg'), ('m2', 'm²'), ('unidades', 'Unidades'),
                        ('novedades', 'Guías con incidencia'), ('pct_novedad', '% incidencias'),
                        ('guias_rotura', 'Guías con daños'), ('roturas', 'Reportes roturas'),
                        ('roturas_pendientes', 'Roturas pendientes'),
                        ('roturas_aprobadas', 'Roturas aprobadas'),
                        ('cantidad_rota_m2', 'm² dañados'),
                        ('cantidad_rota_unidades', 'Unidades dañadas'),
                        ('pct_rotura', '% guías con daño')],
            'destinos': [('nombre', 'Destino'), ('guias', 'Guías'), ('viajes', 'Viajes'),
                         ('kg', 'Kg'), ('m2', 'm²'), ('unidades', 'Unidades'),
                         ('novedades', 'Guías con incidencia'), ('pct_novedad', '% incidencias'),
                         ('guias_rotura', 'Guías con daños'), ('roturas', 'Reportes roturas'),
                         ('roturas_pendientes', 'Roturas pendientes'),
                         ('roturas_aprobadas', 'Roturas aprobadas'),
                         ('cantidad_rota_m2', 'm² dañados'),
                         ('cantidad_rota_unidades', 'Unidades dañadas'),
                         ('pct_rotura', '% guías con daño')],
            'incidencias': [('nombre', 'Guía'), ('destino', 'Destino'),
                            ('transportista', 'Transportista'), ('chofer', 'Chofer'),
                            ('estado', 'Estado incidencia'), ('reportes', 'Reportes rotura'),
                            ('roturas_pendientes', 'Pendientes'),
                            ('roturas_aprobadas', 'Aprobadas'),
                            ('cantidad_rota_m2', 'm² dañados'),
                            ('cantidad_rota_unidades', 'Unidades dañadas'), ('fecha', 'Fecha')],
            'liquidaciones': [('nombre', 'Liquidación'), ('estado', 'Estado'),
                              ('transportista', 'Transportista'), ('moneda', 'Moneda'),
                              ('total', 'Acordado'), ('pagado', 'Pagado'),
                              ('pendiente', 'Pendiente')],
            'marcas': [('codigo', 'Código'), ('nombre', 'Marca'),
                       ('guias', 'Guías'), ('reportes', 'Reportes rotura')],
            'proveedores_producto': [('codigo', 'Código'), ('nombre', 'Proveedor de producto'),
                                    ('guias', 'Guías'), ('reportes', 'Reportes rotura')],
            'tendencia': [('periodo', 'Periodo'), ('guias', 'Guías'),
                          ('rutas', 'Rutas'), ('viajes', 'Embarques'), ('salidas', 'Salidas reales')],
        }
        if dataset != 'all' and dataset not in columns:
            return request.not_found()
        # Validación de rol, empresas, fecha y permisos en el servicio antes de exportar.
        try:
            data = request.env['tc.logistica.bi.service'].get_dashboard(
                periodo, desde, hasta, base)
        except (AccessError, UserError) as exc:
            return request.make_response(str(exc), status=403)
        except Exception:
            return request.make_response('Error obteniendo indicadores; consulte el log Odoo.', status=500)

        allowed = set(columns)
        if not data['permisos'].get('finanzas'):
            allowed.discard('liquidaciones')
        if not data['permisos'].get('comercial'):
            allowed.difference_update(('marcas', 'proveedores_producto'))
        if dataset != 'all' and dataset not in allowed:
            return request.make_response('Sin permiso para exportar estos datos.', status=403)
        try:
            import xlsxwriter
        except ImportError:
            return request.make_response('Se requiere el paquete xlsxwriter.', status=503)
        output = BytesIO()
        book = xlsxwriter.Workbook(output, {'in_memory': True,
                                           'strings_to_formulas': False,
                                           'strings_to_urls': False})
        heading = book.add_format({'bold': True, 'font_color': '#163C50', 'font_size': 14})
        header = book.add_format({'bold': True, 'bg_color': '#12394C', 'font_color': '#FFFFFF'})
        decimal = book.add_format({'num_format': '#,##0.000'})
        pages = sorted(allowed) if dataset == 'all' else [dataset]
        for page in pages:
            items = data.get(page, [])
            if not isinstance(items, list):
                continue
            if dataset != 'all' and q:
                pattern = str(q).strip().casefold()[:120]
                items = [r for r in items if pattern in ' '.join(str(v) for v in r.values()).casefold()]
            if dataset != 'all' and sort and sort in {key for key, _ in columns[page]}:
                items.sort(key=lambda r: (0 if isinstance(r.get(sort), (int, float)) else 1,
                                         -(r.get(sort) or 0) if isinstance(r.get(sort), (int, float)) else str(r.get(sort) or '')))
            ws = book.add_worksheet(page[:31])
            ws.write_string(0, 0, 'TRANSCASH · %s' % page.upper(), heading)
            ws.write_string(1, 0, '%s a %s · %s · fecha: %s' % (
                data['fechas']['desde'], data['fechas']['hasta'], periodo, base))
            names = columns[page]
            ws.write_row(3, 0, [label for _, label in names], header)
            ws.freeze_panes(4, 1)
            for rowidx, record in enumerate(items, 4):
                for colidx, (key, _) in enumerate(names):
                    val = record.get(key)
                    if isinstance(val, (int, float)) and not isinstance(val, bool):
                        ws.write_number(rowidx, colidx, val, decimal)
                    else:
                        ws.write_string(rowidx, colidx, str(val) if val is not None else '')
            ws.set_column(0, 0, 34)
            ws.set_column(1, len(names) - 1, 19)
            ws.autofilter(3, 0, max(3, 3 + len(items)), len(names) - 1)
        if dataset == 'all':
            ws = book.add_worksheet('KPIs')
            ws.write_string(0, 0, 'TRANSCASH · KPIs operativos', heading)
            ws.write_row(2, 0, ['Indicador', 'Valor'], header)
            for i, (key, value) in enumerate(sorted(data['kpis'].items()), 3):
                ws.write_string(i, 0, str(key))
                if isinstance(value, (int, float)):
                    ws.write_number(i, 1, value, decimal)
                else:
                    ws.write_string(i, 1, str(value))
            ws.set_column(0, 0, 32)
            ws.set_column(1, 1, 24)
        book.close()
        return request.make_response(output.getvalue(), headers=[
            ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
            ('Content-Disposition', 'attachment; filename="transcash_bi_%s.xlsx"' % dataset),
            ('Cache-Control', 'private, no-store'),
            ('X-Content-Type-Options', 'nosniff'),
        ])
