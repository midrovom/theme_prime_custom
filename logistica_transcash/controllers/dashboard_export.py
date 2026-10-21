"""Excel de los datasets del dashboard, con revisión de rol y compañías."""
from io import BytesIO
from odoo import http
from odoo.exceptions import AccessError, UserError
from odoo.http import request


class TranscashDashboardExport(http.Controller):
    @http.route('/transcash/dashboard/export/xlsx', type='http', auth='user', methods=['GET'], csrf=False)
    def export(self, dataset='all', periodo='semana', desde=None, hasta=None,
               base='registro', q='', sort='', **kw):
        sections = {
            'tendencia': ('Evolución', [('periodo','Periodo'), ('guias','Guías'), ('rutas','Rutas'), ('viajes','Viajes programados'), ('salidas','Salidas reales')]),
            'guias': ('Guías', [('nombre','Guía'),('estado','Estado'),('documento','Documento'),('destino','Destino'),('transportista','Transportista'),('chofer','Chofer'),('ruta','Hoja de ruta'),('viaje','Embarque'),('kg','Kg'),('m2','m²'),('metros_lineales','m lineales'),('unidades','Unidades'),('pallets','Pallets'),('cajas','Cajas')]),
            'rutas': ('Hojas de ruta', [('nombre','Ruta'),('estado','Estado'),('destino','Destino'),('transportista','Transportista'),('chofer','Chofer'),('guias','Guías'),('kg','Kg'),('m2','m²'),('metros_lineales','m lineales'),('unidades','Unidades'),('pallets','Pallets'),('cajas','Cajas')]),
            'embarques': ('Embarques', [('nombre','Embarque'),('estado','Estado'),('transportista','Transportista'),('chofer','Chofer'),('guias','Guías'),('rutas','Rutas'),('kg','Kg'),('m2','m²'),('metros_lineales','m lineales'),('unidades','Unidades'),('pallets','Pallets'),('cajas','Cajas')]),
            'destinos': ('Destinos', [('nombre','Destino'),('guias','Guías'),('viajes','Viajes'),('kg','Kg'),('m2','m²'),('metros_lineales','m lineales'),('unidades','Unidades'),('novedades','Novedades'),('roturas','Roturas')]),
            'transportistas': ('Transportistas', [('nombre','Empresa transportista'),('guias','Guías'),('viajes','Viajes'),('kg','Kg'),('m2','m²'),('metros_lineales','m lineales'),('unidades','Unidades'),('novedades','Novedades'),('roturas','Roturas')]),
            'choferes': ('Choferes', [('nombre','Chofer'),('guias','Guías'),('viajes','Viajes'),('kg','Kg'),('m2','m²'),('metros_lineales','m lineales'),('unidades','Unidades'),('novedades','Novedades'),('roturas','Roturas')]),
            'incidencias': ('Incidencias', [('nombre','Guía'),('destino','Destino'),('estado','Incidencia'),('reportes','Reportes'),('fecha','Fecha')]),
            'liquidaciones': ('Liquidaciones', [('nombre','Liquidación'),('estado','Estado'),('transportista','Transportista'),('moneda','Moneda'),('total','Acordado'),('pagado','Pagado'),('pendiente','Saldo'),('fecha','Fecha')]),
            'marcas': ('Marcas privado', [('codigo','Código marca'),('nombre','Nombre marca'),('guias','Guías'),('reportes','Reportes')]),
            'proveedores_producto': ('Proveedores producto', [('codigo','Código proveedor'),('nombre','Proveedor de producto'),('guias','Guías'),('reportes','Reportes')]),
        }
        if dataset not in sections and dataset != 'all':
            return request.not_found()
        try:
            data = request.env['transcash.dashboard.service'].get_dashboard(periodo, desde, hasta, base)
        except (AccessError, UserError) as exc:
            return request.make_response(str(exc), status=403)
        perms = data['permisos']
        if dataset == 'liquidaciones' and not perms['finanzas']:
            return request.make_response('No autorizado a consultar finanzas.', status=403)
        if dataset in ('marcas','proveedores_producto') and not perms['comercial']:
            return request.make_response('No autorizado a consultar datos comerciales.', status=403)
        try:
            import xlsxwriter
        except ImportError:
            return request.make_response('Instale xlsxwriter en el Python de Odoo.', status=503)
        output = BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory':True, 'strings_to_urls':False,
                                                'strings_to_formulas':False})
        header = workbook.add_format({'bold':True,'bg_color':'#17283D','font_color':'#FFFFFF'})
        title = workbook.add_format({'bold':True,'font_size':15})
        number = workbook.add_format({'num_format':'#,##0.000'})
        names = [x for x in sections if x in data] if dataset == 'all' else [dataset]
        for key in names:
            sheet_title, cols = sections[key]
            ws = workbook.add_worksheet(sheet_title[:31])
            ws.hide_gridlines(2)
            ws.write_string(0,0,'TRANSCASH · ' + sheet_title,title)
            ws.write_string(1,0,'%s — %s · %s · %s' % (data['fechas']['desde'],
                 data['fechas']['hasta'],data['fechas']['agrupacion'],data['fechas']['base']))
            ws.write_row(3,0,[label for _,label in cols],header)
            rows = list(data.get(key,[]))
            if dataset != 'all':
                term = str(q or '')[:120].lower().strip()
                if term:
                    rows = [r for r in rows if term in ' '.join(str(v) for v in r.values()).lower()]
                allowed_sort = {f for f,_ in cols}
                if sort in allowed_sort:
                    rows.sort(key=lambda r: (r.get(sort) is None,
                        -r.get(sort) if isinstance(r.get(sort),(int,float)) else str(r.get(sort) or '')))
            for i, row in enumerate(rows,4):
                for j,(field,_label) in enumerate(cols):
                    value=row.get(field)
                    if isinstance(value,(int,float)) and not isinstance(value,bool):
                        ws.write_number(i,j,value,number)
                    else:
                        ws.write_string(i,j,str(value or ''))
            ws.freeze_panes(4,1)
            ws.set_column(0,0,34)
            ws.set_column(1,max(1,len(cols)-1),20)
            ws.autofilter(3,0,max(4,3+len(rows)),len(cols)-1)
        if dataset == 'all':
            ws = workbook.add_worksheet('KPIs')
            ws.write(0,0,'TRANSCASH · Indicadores',title)
            ws.write_row(2,0,['Indicador','Valor'],header)
            for i,(key,value) in enumerate(data['kpis'].items(),3):
                ws.write_string(i,0,key.replace('_',' ').capitalize())
                ws.write_number(i,1,float(value or 0),number)
            ws.set_column(0,0,38)
            ws.set_column(1,1,22)
        workbook.close()
        return request.make_response(output.getvalue(), headers=[
            ('Content-Type','application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
            ('Content-Disposition','attachment; filename="transcash_dashboard_%s.xlsx"' % dataset),
            ('Cache-Control','private, no-store'), ('X-Content-Type-Options','nosniff'),
        ])
