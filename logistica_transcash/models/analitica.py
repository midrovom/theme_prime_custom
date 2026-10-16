"""Resumen auditable e indicadores de lectura sin dependencias contables."""
from collections import Counter, defaultdict
from datetime import datetime, time, timedelta
import pytz

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError
from odoo.tools import drop_view_if_exists


class TranscashNovedadResumen(models.Model):
    _name = 'transcash.novedad.resumen'
    _description = 'Control consolidado de novedades de transporte'
    _auto = False
    _order = 'fecha_cierre_chofer desc, id desc'

    guia_id = fields.Many2one('transcash.guia', readonly=True)
    embarque_id = fields.Many2one('transcash.embarque', readonly=True)
    company_id = fields.Many2one('res.company', readonly=True)
    proveedor_id = fields.Many2one('res.partner', string='Empresa transporte', readonly=True)
    chofer_usuario_id = fields.Many2one('res.users', string='Chofer', readonly=True)
    destinatario_id = fields.Many2one('res.partner', readonly=True)
    destino = fields.Char(readonly=True)
    fecha_cierre_chofer = fields.Datetime(readonly=True)
    resultado_recepcion = fields.Selection([('pendiente','Pendiente'), ('conforme','Conforme'),
        ('con_novedades','Con novedades'),('historica','Histórica')], readonly=True)
    incidencia_estado = fields.Selection([('ninguna','Sin incidencia'), ('abierta','Abierta'),
        ('resuelta','Resuelta')], readonly=True)
    reportes_rotura = fields.Integer('Roturas registradas', readonly=True)
    reportes_pendientes = fields.Integer('Roturas por revisar', readonly=True)
    reportes_aprobados = fields.Integer('Roturas aprobadas', readonly=True)
    peso_roto_estimado_kg = fields.Float('Peso dañado estimado (kg)', readonly=True, digits=(16,3))
    ultima_rotura = fields.Datetime('Último reporte de daño', readonly=True)

    def init(self):
        drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute('''
            CREATE VIEW transcash_novedad_resumen AS
            SELECT g.id, g.id AS guia_id, g.embarque_id, g.company_id,
                g.proveedor_id, g.chofer_usuario_id, g.destinatario_id, g.destino,
                g.fecha_cierre_chofer, g.resultado_recepcion, g.incidencia_estado,
                COALESCE(x.reportes_rotura, 0) AS reportes_rotura,
                COALESCE(x.reportes_pendientes, 0) AS reportes_pendientes,
                COALESCE(x.reportes_aprobados, 0) AS reportes_aprobados,
                COALESCE(x.peso_roto_estimado_kg, 0) AS peso_roto_estimado_kg,
                x.ultima_rotura
            FROM transcash_guia g
            LEFT JOIN (
                SELECT r.guia_id,
                    count(*) FILTER (WHERE r.estado != 'rechazada') AS reportes_rotura,
                    count(*) FILTER (WHERE r.estado = 'pendiente') AS reportes_pendientes,
                    count(*) FILTER (WHERE r.estado = 'aprobada') AS reportes_aprobados,
                    SUM(CASE WHEN r.estado != 'rechazada' AND l.cantidad > 0
                        THEN r.cantidad * l.peso_kg / l.cantidad ELSE 0 END) AS peso_roto_estimado_kg,
                    MAX(r.create_date) AS ultima_rotura
                FROM transcash_rotura r
                JOIN transcash_guia_linea l ON l.id = r.linea_id
                GROUP BY r.guia_id
            ) x ON x.guia_id = g.id
            WHERE g.incidencia_estado <> 'ninguna'
                OR g.resultado_recepcion = 'con_novedades'
                OR COALESCE(x.reportes_rotura,0) > 0
        ''')

    def write(self, vals):
        raise AccessError(_('El resumen es solo de consulta.'))

    def unlink(self):
        raise AccessError(_('El resumen es solo de consulta.'))


class TranscashDashboard(models.AbstractModel):
    _name = 'transcash.dashboard.service'
    _description = 'Indicadores logísticos con acceso independiente'

    @api.model
    def get_dashboard(self, periodo='semana', fecha_desde=None, fecha_hasta=None):
        user = self.env.user
        if not user.has_group('logistica_transcash.group_transcash_dashboard') or user.share:
            raise AccessError(_('No tiene autorización para consultar el dashboard.'))
        if periodo not in ('dia', 'semana', 'mes'):
            raise UserError(_('Agrupación inválida.'))
        try:
            start = fields.Date.to_date(fecha_desde) if fecha_desde else fields.Date.today() - timedelta(days=89)
            end = fields.Date.to_date(fecha_hasta) if fecha_hasta else fields.Date.today()
        except (ValueError, TypeError):
            raise UserError(_('Rango de fechas inválido.'))
        if not start or not end or end < start or (end - start).days > 366:
            raise UserError(_('El rango permitido es de 1 a 367 días.'))
        allowed = self.env.companies.ids
        if not allowed:
            raise AccessError(_('No tiene compañías autorizadas.'))
        # Usamos sudo exclusivamente DESPUÉS de validar rol y fijar compañías.
        tz = pytz.timezone(user.tz or 'America/Guayaquil')
        dt_from = tz.localize(datetime.combine(start, time.min)).astimezone(pytz.UTC).replace(tzinfo=None)
        dt_to = tz.localize(datetime.combine(end + timedelta(days=1), time.min)).astimezone(pytz.UTC).replace(tzinfo=None)
        ships = self.env['transcash.embarque'].sudo().search([
            ('company_id','in',allowed),('fecha_salida','>=',dt_from),('fecha_salida','<',dt_to),
            ('state','in',('ruta','entregado'))], order='fecha_salida asc', limit=15001)
        if len(ships) > 15000:
            raise UserError(_('Hay más de 15.000 viajes en este periodo; seleccione un rango menor.'))
        guias = self.env['transcash.guia'].sudo().search([('embarque_id','in',ships.ids)]) if ships else self.env['transcash.guia']
        lines = self.env['transcash.guia.linea'].sudo().search([('guia_id','in',guias.ids),
            ('vigente_erp','=',True)]) if guias else self.env['transcash.guia.linea']
        damages = self.env['transcash.rotura'].sudo().search([('guia_id','in',guias.ids),
            ('estado','!=','rechazada')]) if guias else self.env['transcash.rotura']

        def series_key(date):
            if periodo == 'dia': return date.strftime('%Y-%m-%d')
            if periodo == 'semana':
                yr, wk, _ = date.isocalendar()
                return '%s-S%02d' % (yr,wk)
            return date.strftime('%Y-%m')
        trends = Counter(series_key(pytz.UTC.localize(fields.Datetime.to_datetime(e.fecha_salida)).astimezone(tz).date())
                         for e in ships)
        trip_map = {e.id: e for e in ships}
        guia_map = {g.id:g for g in guias}
        guide_lines = defaultdict(list)
        for l in lines: guide_lines[l.guia_id.id].append(l)
        damaged_guide_ids = {r.guia_id.id for r in damages}
        incident_guide_ids = {g.id for g in guias if g.incidencia_estado != 'ninguna' or
                              g.resultado_recepcion == 'con_novedades' or g.id in damaged_guide_ids}
        open_guide_ids = {g.id for g in guias if g.incidencia_estado == 'abierta' or g.roturas_pendientes}
        guides_by_trip = defaultdict(list)
        dest = defaultdict(lambda: {'name':'', 'viajes':set(), 'guias':0, 'novedades':0,
                                    'roturas':0, 'peso_kg':0.0})
        provider = defaultdict(lambda: {'name':'','viajes':set(), 'guias':0,'novedades':0,'roturas':0})
        driver = defaultdict(lambda: {'name':'','viajes':set(), 'guias':0,'novedades':0,'roturas':0})
        for e in ships:
            pr = provider[e.proveedor_id.id]
            pr['name'] = e.proveedor_id.display_name or 'Sin proveedor'
            pr['viajes'].add(e.id)
            dr = driver[e.chofer_usuario_id.id]
            dr['name'] = e.chofer_usuario_id.display_name or 'Sin chofer'
            dr['viajes'].add(e.id)
        weight_total = 0.0
        for g in guias:
            trip = trip_map.get(g.embarque_id.id)
            if not trip: continue
            guides_by_trip[trip.id].append(g)
            ls = guide_lines.get(g.id, [])
            # Evitar doble contabilización del peso: usar líneas si contienen pesos,
            # o el peso de cabecera SOLO cuando no hay peso de línea.
            line_weight = sum(max(0.0,l.peso_kg or 0) for l in ls)
            kg = line_weight if line_weight > 0 else max(0.0,g.peso_kg or 0)
            weight_total += kg
            key = (g.destino_codigo or g.destino_ciudad or g.destino or 'Destino sin código').strip()
            info=dest[key]; info['name']=key; info['viajes'].add(trip.id)
            info['guias'] += 1; info['peso_kg'] += kg
            novelty = g.id in incident_guide_ids
            damage = g.id in damaged_guide_ids
            info['novedades'] += int(novelty); info['roturas'] += int(damage)
            for info2 in (provider[trip.proveedor_id.id], driver[trip.chofer_usuario_id.id]):
                info2['guias'] += 1; info2['novedades'] += int(novelty); info2['roturas'] += int(damage)
        brand = defaultdict(lambda:{'name':'', 'reportes':0,'guias':set(),'expuestas':set(),'kg_estimados':0.,'cantidades':Counter()})
        supplier = defaultdict(lambda:{'name':'', 'reportes':0,'guias':set(),'expuestas':set(),'kg_estimados':0.,'cantidades':Counter()})
        # El denominador (guías con producto transportado) evita interpretar como
        # más riesgosa una marca únicamente por vender más volumen.
        for l in lines:
            key_brand = l.marca_codigo or l.marca_nombre or 'Marca no informada'
            key_supplier = l.proveedor_producto_codigo or l.proveedor_producto_nombre or 'Proveedor no informado'
            brand[key_brand]['name'] = l.marca_nombre or key_brand
            brand[key_brand]['expuestas'].add(l.guia_id.id)
            supplier[key_supplier]['name'] = l.proveedor_producto_nombre or key_supplier
            supplier[key_supplier]['expuestas'].add(l.guia_id.id)
        estimated_broken_kg = 0.0
        for r in damages:
            l = r.linea_id
            qty = r.cantidad or 0.
            kg = (qty * l.peso_kg / l.cantidad) if l.cantidad and l.peso_kg else 0.
            estimated_broken_kg += kg
            for collection,key in ((brand,l.marca_codigo or l.marca_nombre or 'Marca no informada'),
                                   (supplier,l.proveedor_producto_codigo or l.proveedor_producto_nombre or 'Proveedor no informado')):
                v=collection[key]; v['name'] = (l.marca_nombre if collection is brand else l.proveedor_producto_nombre) or key
                v['reportes'] += 1; v['guias'].add(r.guia_id.id)
                v['kg_estimados'] += kg; v['cantidades'][l.unidad] += qty
        # IMPORTANTE: la clave del grupo (ID de chofer o código de destino)
        # no debe sobrescribir la columna por la que se ordena el ranking.
        # Antes sucedía y provocaba KeyError/"Server Error" con viajes reales.
        def summary(info, sort_field):
            rows=[]
            for group_key, v in info.items():
                n=v['guias']
                rows.append({'clave':str(group_key),'nombre':v['name'],'viajes':len(v['viajes']), 'guias':n,
                    'novedades':v['novedades'], 'roturas':v['roturas'],
                    'pct_novedad':round(100*v['novedades']/n,1) if n else 0.,
                    'pct_rotura':round(100*v['roturas']/n,1) if n else 0.,
                    'peso_kg':round(v.get('peso_kg',0.),2)})
            return sorted(rows,key=lambda r:(-r[sort_field],-r['guias'],r['nombre']))[:30]
        def ranking(info):
            return sorted(({'clave':str(key),'nombre':v['name'],'reportes':v['reportes'], 'guias':len(v['guias']),
                'kg_estimados':round(v['kg_estimados'],2),
                'guias_transportadas':len(v['expuestas']),
                'pct_guias_danadas':round(100*len(v['guias'])/len(v['expuestas']),1) if v['expuestas'] else 0.,
                'cantidades':', '.join('%g %s' % (q,u) for u,q in sorted(v['cantidades'].items()))}
                for key,v in info.items()), key=lambda r:(-r['reportes'],-r['guias'],r['nombre']))[:30]
        points=[{'periodo':k,'viajes':n} for k,n in sorted(trends.items())]
        max_v=max(trends.values(),default=1)
        for p in points: p['porcentaje']=round(100*p['viajes']/max_v,1)
        return {'puede_consultar_novedades': user.has_group('logistica_transcash.group_transcash_consulta') or
                user.has_group('logistica_transcash.group_logistica_bodega'),
            'fechas':{'desde':start.isoformat(),'hasta':end.isoformat(),'agrupacion':periodo},
            'kpis':{'viajes':len(ships),'guias':len(guias),'kg':round(weight_total,2),
                    'toneladas':round(weight_total/1000,3),'guias_novedad':len(incident_guide_ids),
                    'guias_rotura':len(damaged_guide_ids),'novedades_abiertas':len(open_guide_ids),
                    'reportes_rotura':len(damages),'kg_rotura_estimados':round(estimated_broken_kg,2),
                    'pct_guias_rotura':round(100*len(damaged_guide_ids)/len(guias),1) if guias else 0.},
            'tendencia':points,'destinos':summary(dest,'viajes'),
            'transportistas':summary(provider,'novedades'), 'choferes':summary(driver,'novedades'),
            'marcas':ranking(brand),'proveedores_producto':ranking(supplier),
            'notas':[
                'Viajes: embarques con salida real en el periodo (estado En ruta o Entregado).',
                'Destinos: un embarque multidestino puede contarse en varios destinos; no sumar esos totales como viajes únicos.',
                'Kg transportados: suma de pesos declarados por producto; si faltan, usa el peso total de la guía. Los pallets y cajas informativos no se suman como kg.',
                'Roturas: reportes no rechazados. Las cantidades se muestran por unidad, sin mezclar m², metros ni unidades.',
                'Kg dañados estimados: prorrateo por peso de línea y cantidad reportada; solo cuando el ERP informa peso y cantidad.',
                'Las tasas por transportista, chofer, marca y proveedor se calculan sobre guías transportadas con esos productos, no sobre fotografías; comparar también volúmenes y destinos.',
                'Las agrupaciones diarias utilizan la zona horaria del usuario; el periodo usa la fecha de salida del embarque.',
            ]}
