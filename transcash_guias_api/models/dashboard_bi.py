# -*- coding: utf-8 -*-
"""BI v2.2 (en el conector ERP). Datos reales de modelos operativos, por compañías permitidas.

Separamos universo de guías, hojas de ruta y embarques para incluir preparación,
sin denominar 'viajes realizados' a los embarques todavía no despachados.
"""
from collections import Counter, defaultdict
from datetime import datetime, timedelta, time
import pytz

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError

MAX_RECORDS = 15000
MAX_LINES = 60000


class TranscashDashboardBI(models.AbstractModel):
    _name = 'tc.logistica.bi.service'
    _description = 'BI logistico único en complemento ERP'

    def _check_bi_access(self):
        user = self.env.user
        if user.share or not (
            user.has_group('logistica_transcash.group_transcash_dashboard')
            or user.has_group('logistica_transcash.group_logistica_manager')
            or user.has_group('logistica_transcash.group_transcash_contabilidad')
            or user.has_group('base.group_system')
        ):
            raise AccessError(_('No está autorizado para consultar los indicadores logísticos.'))
        allowed = self.env.companies.ids
        if not allowed:
            raise AccessError(_('No hay empresas autorizadas.'))
        return allowed

    def _get_security_flags(self):
        user = self.env.user
        finance = user.has_group('logistica_transcash.group_transcash_contabilidad') or user.has_group('logistica_transcash.group_logistica_manager') or user.has_group('base.group_system')
        commercial = user.has_group('base.group_system') or user.has_group('transcash_guias_api.group_tc_sync_admin')
        return finance, commercial

    @api.model
    def get_dashboard(self, periodo='semana', fecha_desde=None, fecha_hasta=None, fecha_base='registro'):
        companies = self._check_bi_access()
        finance, commercial = self._get_security_flags()
        if periodo not in ('dia', 'semana', 'mes'):
            raise UserError(_('La agrupación de fechas es inválida.'))
        if fecha_base not in ('registro', 'prevista', 'salida'):
            raise UserError(_('Seleccione un criterio de fecha válido.'))
        today = fields.Date.context_today(self)
        try:
            d0 = fields.Date.to_date(fecha_desde) if fecha_desde else today - timedelta(days=89)
            d1 = fields.Date.to_date(fecha_hasta) if fecha_hasta else today
        except (TypeError, ValueError):
            raise UserError(_('Fechas inválidas.'))
        if not d0 or not d1 or d1 < d0 or (d1-d0).days > 366:
            raise UserError(_('Seleccione un intervalo entre 1 y 367 días.'))
        try:
            tz = pytz.timezone(self.env.user.tz or 'America/Guayaquil')
        except pytz.UnknownTimeZoneError:
            tz = pytz.timezone('America/Guayaquil')
        f0 = tz.localize(datetime.combine(d0, time.min)).astimezone(pytz.UTC).replace(tzinfo=None)
        f1 = tz.localize(datetime.combine(d1 + timedelta(days=1), time.min)).astimezone(pytz.UTC).replace(tzinfo=None)
        field_g = {'registro':'create_date','prevista':'fecha_prevista','salida':'embarque_id.fecha_salida'}[fecha_base]
        field_e = {'registro':'create_date','prevista':'fecha_traslado_prevista','salida':'fecha_salida'}[fecha_base]
        # fecha_traslado_prevista es computado, NO searchable. Para prevista
        # seleccionamos embarques por creación y detallamos la limitación.
        if fecha_base == 'prevista':
            field_e = 'create_date'
        field_r = 'create_date' if fecha_base != 'salida' else 'embarque_id.fecha_salida'

        def fetch(model, date_field):
            records = self.env[model].sudo().search([
                ('company_id','in',companies), (date_field, '>=', f0),
                (date_field, '<', f1)], order='id desc', limit=MAX_RECORDS+1)
            if len(records) > MAX_RECORDS:
                raise UserError(_('Más de %s registros de %s: acorte el rango de fechas.') % (MAX_RECORDS, model))
            return records

        guias = fetch('transcash.guia', field_g)
        rutas = fetch('transcash.hoja.ruta', field_r)
        embarques = fetch('transcash.embarque', field_e)
        guias_ids = guias.ids
        lineas = self.env['transcash.guia.linea'].sudo().search([
            ('guia_id','in',guias_ids), ('vigente_erp','=',True)], limit=MAX_LINES+1) if guias_ids else self.env['transcash.guia.linea']
        if len(lineas) > MAX_LINES:
            raise UserError(_('Demasiados productos en el periodo. Acorte las fechas.'))
        roturas = self.env['transcash.rotura'].sudo().search([
            ('guia_id','in',guias_ids), ('estado','!=','rechazada')]) if guias_ids else self.env['transcash.rotura']
        rotura_por_guia = defaultdict(list)
        for r in roturas:
            rotura_por_guia[r.guia_id.id].append(r)
        por_guia = defaultdict(list)
        for lin in lineas:
            por_guia[lin.guia_id.id].append(lin)

        def metricas(g):
            ls = por_guia.get(g.id)
            if ls is None:
                ls = g.linea_ids.filtered('vigente_erp')
            kg_lineas = sum(max(0, l.peso_kg or 0) for l in ls)
            return {'kg': kg_lineas if kg_lineas else max(0, g.peso_kg or 0),
                    'm2': sum(l.cantidad for l in ls if l.unidad == 'm2'),
                    'metros_lineales':sum(l.cantidad for l in ls if l.unidad == 'metro'),
                    'unidades': sum(l.cantidad for l in ls if l.unidad == 'unidad'),
                    'pallets': sum(max(0, l.pallets_info or 0) for l in ls),
                    'cajas': sum(max(0, l.cajas_info or 0) for l in ls),
                    'productos': len(ls)}

        def sum_metrics(rows):
            keys = ('kg','m2','metros_lineales','unidades','pallets','cajas','productos')
            acc = {k:0.0 for k in keys}
            for g in rows:
                m = metricas(g)
                for k in keys: acc[k] += m[k]
            return {k: round(v,3) for k,v in acc.items()}

        def label_date(dt):
            if not dt: return ''
            v = fields.Datetime.to_datetime(dt)
            return pytz.UTC.localize(v).astimezone(tz).strftime('%Y-%m-%d')

        def series_key(dt):
            date = fields.Datetime.to_datetime(dt)
            if not date: return None
            d = pytz.UTC.localize(date).astimezone(tz).date()
            if periodo == 'dia': return d.strftime('%Y-%m-%d')
            if periodo == 'semana':
                y, w, _ = d.isocalendar()
                return '%04d-S%02d' % (y,w)
            return d.strftime('%Y-%m')

        trend = defaultdict(lambda: {'guias':0,'rutas':0,'viajes':0,'salidas':0})
        for g in guias:
            key = series_key(g.embarque_id.fecha_salida if fecha_base == 'salida' else g[field_g])
            if key: trend[key]['guias'] += 1
        for r in rutas:
            key = series_key(r.create_date if fecha_base != 'salida' else r.embarque_id.fecha_salida)
            if key: trend[key]['rutas'] += 1
        for e in embarques:
            key = series_key(e[field_e])
            if key:
                trend[key]['viajes'] += 1
                if e.fecha_salida: trend[key]['salidas'] += 1
        status_guia = Counter(g.state for g in guias)
        status_ruta = Counter(r.state for r in rutas)
        status_embarque = Counter(e.state for e in embarques)
        total_carga = sum_metrics(guias)
        guias_incidencia = {g.id for g in guias if g.incidencia_estado != 'ninguna' or g.resultado_recepcion == 'con_novedades' or rotura_por_guia[g.id]}
        guias_rotura = {x for x in rotura_por_guia}
        abiertos = [g for g in guias if g.incidencia_estado == 'abierta']
        entregadas = ('revision','entregada','lista_pago','facturada','pagada')
        kpis = {
            'guias':len(guias), 'guias_sin_ruta': sum(bool(not g.hoja_ruta_id and g.state == 'registrada') for g in guias),
            'guias_en_ruta': status_guia.get('ruta',0),
            'guias_entregadas': sum(g.state in entregadas for g in guias),
            'rutas':len(rutas), 'rutas_borrador':status_ruta.get('borrador',0),
            'viajes':len(embarques), 'viajes_preparacion':status_embarque.get('preparacion',0),
            'viajes_en_ruta':status_embarque.get('ruta',0),
            'viajes_entregados':status_embarque.get('entregado',0),
            'salidas_reales': sum(bool(e.fecha_salida) for e in embarques),
            'kg':total_carga['kg'], 'toneladas':round(total_carga['kg']/1000,3),
            'm2':total_carga['m2'],'metros_lineales':total_carga['metros_lineales'], 'unidades':total_carga['unidades'],
            'pallets':total_carga['pallets'], 'cajas':total_carga['cajas'],
            'guias_novedad':len(guias_incidencia), 'novedades_abiertas':len(abiertos),
            'guias_rotura':len(guias_rotura), 'reportes_rotura':len(roturas),
            'pct_guias_rotura': round(100*len(guias_rotura)/len(guias),1) if guias else 0,
            'roturas_pendientes': sum(r.estado == 'pendiente' for r in roturas),
            'roturas_aprobadas': sum(r.estado == 'aprobada' for r in roturas),
            'cantidad_rota_m2': round(sum(max(0,r.cantidad or 0) for r in roturas if r.linea_id.unidad == 'm2'),3),
            'cantidad_rota_unidades': round(sum(max(0,r.cantidad or 0) for r in roturas if r.linea_id.unidad == 'unidad'),3),
        }

        destinations = defaultdict(lambda: {'nombre':'', 'guias':0, 'viajes':set(), 'kg':0.0,'m2':0.0,'unidades':0.0,'novedades':0,'roturas':0, 'guias_rotura':0, 'roturas_pendientes':0, 'roturas_aprobadas':0, 'cantidad_rota_m2':0.0, 'cantidad_rota_unidades':0.0})
        carriers = defaultdict(lambda: {'nombre':'', 'guias':0, 'viajes':set(), 'kg':0.0,'m2':0.0,'unidades':0.0,'novedades':0,'roturas':0, 'guias_rotura':0, 'roturas_pendientes':0, 'roturas_aprobadas':0, 'cantidad_rota_m2':0.0, 'cantidad_rota_unidades':0.0})
        drivers = defaultdict(lambda: {'nombre':'', 'guias':0, 'viajes':set(), 'kg':0.0,'m2':0.0,'unidades':0.0,'novedades':0,'roturas':0, 'guias_rotura':0, 'roturas_pendientes':0, 'roturas_aprobadas':0, 'cantidad_rota_m2':0.0, 'cantidad_rota_unidades':0.0})
        guide_rows = []
        for g in guias:
            m = metricas(g)
            destination = g.destino_id.display_name or g.destino_ciudad or g.destino or 'Destino no homologado'
            # Prioridad: vínculo en guía; como respaldo, el transportista y
            # chofer del embarque o ruta. Evita agrupar como 'Sin transporte'
            # una entrega ya asignada correctamente en el modelo operativo.
            carrier_partner = (g.proveedor_id or
                               (g.embarque_id and g.embarque_id.proveedor_id) or
                               (g.hoja_ruta_id and g.hoja_ruta_id.proveedor_id))
            driver_user = (g.chofer_usuario_id or
                           (g.embarque_id and g.embarque_id.chofer_usuario_id) or
                           (g.hoja_ruta_id and g.hoja_ruta_id.chofer_usuario_id))
            driver_partner = (g.chofer_contacto_id if 'chofer_contacto_id' in g._fields else False)
            carrier = carrier_partner.display_name if carrier_partner else 'Sin transportista'
            driver = (driver_user.name if driver_user else False) or (driver_partner.name if driver_partner else False) or 'Sin usuario chofer'
            # Clave estable por identificación cuando exista: dos contactos
            # duplicados con igual RUC no se presentan como proveedores distintos.
            carrier_vat = (carrier_partner.vat or '') if carrier_partner else ''
            carrier_vat = ''.join(ch for ch in carrier_vat.upper() if ch.isalnum())
            carrier_key = carrier_vat or (carrier_partner and carrier_partner.id) or carrier
            driver_doc = g.ruc_chofer or ((driver_partner.vat or '') if driver_partner else '')
            driver_doc = ''.join(ch for ch in str(driver_doc).upper() if ch.isalnum())
            driver_key = (driver_doc or (driver_partner and ('contacto:%s' % driver_partner.id)) or
                          (driver_user and ('usuario:%s' % driver_user.id)) or driver)
            tuples = ((destinations,(g.destino_id.codigo if g.destino_id else (g.destino_codigo or destination)), destination),
                      (carriers,'prov:%s' % carrier_key, carrier),
                      (drivers,'driver:%s' % driver_key, driver))
            for agg,key,name in tuples:
                obj=agg[key]; obj['nombre']=name; obj['guias']+=1
                for item in ('kg','m2','unidades'): obj[item] += m[item]
                if g.embarque_id: obj['viajes'].add(g.embarque_id.id)
                # Una incidencia = una guía con novedad; una rotura = un reporte,
                # NO el número de guías que tuvieron algún daño.
                reports = rotura_por_guia.get(g.id, [])
                obj['novedades'] += int(g.id in guias_incidencia)
                obj['guias_rotura'] += int(bool(reports))
                obj['roturas'] += len(reports)
                obj['roturas_pendientes'] += sum(r.estado == 'pendiente' for r in reports)
                obj['roturas_aprobadas'] += sum(r.estado == 'aprobada' for r in reports)
                obj['cantidad_rota_m2'] += sum(max(0, r.cantidad or 0) for r in reports if r.linea_id.unidad == 'm2')
                obj['cantidad_rota_unidades'] += sum(max(0, r.cantidad or 0) for r in reports if r.linea_id.unidad == 'unidad')
            if len(guide_rows) < 300:
                guide_rows.append({
                    'id':g.id, 'modelo':'transcash.guia', 'clave':str(g.id), 'nombre':g.name,
                    'estado':dict(g._fields['state'].selection).get(g.state,g.state),
                    'documento':g.numero_documento or '', 'destino':destination,
                    'transportista':carrier, 'chofer':driver,
                    'ruta':g.hoja_ruta_id.name or 'Sin ruta', 'viaje':g.embarque_id.name or 'Sin embarque',
                    'fecha':label_date(g.embarque_id.fecha_salida if fecha_base == 'salida' else g[field_g]),
                    'novedades':int(g.id in guias_incidencia),
                    'roturas':len(rotura_por_guia[g.id]), **m})


        # Los embarques pueden haberse creado en el rango y contener guías más
        # antiguas. Se incorporan a los contadores únicos de viajes sin duplicar
        # la cantidad de guías filtradas por el criterio de fecha elegido.
        for shipment in embarques:
            for agg, key, label in (
                (carriers, 'prov:%s' % (shipment.proveedor_id.id or 'ninguno'), shipment.proveedor_id.display_name or 'Sin transportista'),
                (drivers, 'driver:%s' % (shipment.chofer_usuario_id.id or 'ninguno'), shipment.chofer_usuario_id.name or 'Sin chofer')):
                acc = agg[key]
                acc['nombre'] = label
                acc['viajes'].add(shipment.id)
            visited_destinations = set()
            for g in shipment.guia_ids:
                key = (g.destino_id.codigo if g.destino_id else (g.destino_codigo or g.destino_ciudad or g.destino or 'Destino sin homologar'))
                if key not in visited_destinations:
                    visited_destinations.add(key)
                    acc = destinations[key]
                    acc['nombre'] = g.destino_id.display_name or g.destino_ciudad or g.destino or key
                    acc['viajes'].add(shipment.id)

        def grouped(aggregation):
            return sorted(({
                'clave':key, 'nombre':v['nombre'], 'guias':v['guias'], 'viajes':len(v['viajes']),
                'kg':round(v['kg'],2), 'm2':round(v['m2'],3),'unidades':round(v['unidades'],3),
                'novedades':v['novedades'], 'roturas':v['roturas'],
                'guias_rotura':v['guias_rotura'], 'roturas_pendientes':v['roturas_pendientes'],
                'roturas_aprobadas':v['roturas_aprobadas'],
                'cantidad_rota_m2':round(v['cantidad_rota_m2'],3),
                'cantidad_rota_unidades':round(v['cantidad_rota_unidades'],3),
                'pct_novedad':round(100*v['novedades']/v['guias'],1) if v['guias'] else 0,
                'pct_rotura':round(100*v['guias_rotura']/v['guias'],1) if v['guias'] else 0,
            } for key,v in aggregation.items()), key=lambda a:(-a['guias'],a['nombre']))

        route_rows = []
        for r in rutas[:300]:
            rg = r.seleccion_guia_ids if r.state == 'borrador' else r.guia_ids
            m = sum_metrics(rg)
            route_rows.append({
                'id':r.id,'modelo':'transcash.hoja.ruta','clave':str(r.id),'nombre':r.name,
                'estado':dict(r._fields['state'].selection).get(r.state,r.state),
                'destino':r.destino_nombre or r.destino_id.name or '',
                'transportista':r.proveedor_id.display_name or '',
                'chofer':r.chofer_usuario_id.name or '', 'guias':len(rg),
                'viaje':r.embarque_id.name or 'Por embarcar', 'fecha':label_date(r.create_date), **m})
        shipment_rows = []
        for e in embarques[:300]:
            m = sum_metrics(e.guia_ids)
            shipment_rows.append({
                'id':e.id,'modelo':'transcash.embarque','clave':str(e.id), 'nombre':e.name,
                'estado':dict(e._fields['state'].selection).get(e.state,e.state),
                'transportista':e.proveedor_id.display_name or '',
                'chofer':e.chofer_usuario_id.name or '',
                'guias':len(e.guia_ids), 'rutas':len(e.ruta_ids),
                'fecha':label_date(e.fecha_salida or e.create_date), **m})
        incident_rows = []
        for g in guias:
            if g.id not in guias_incidencia: continue
            if len(incident_rows) >= 300: break
            incident_rows.append({'id':g.id,'modelo':'transcash.guia','clave':str(g.id),
                'nombre':g.name,'destino':g.destino_ciudad or g.destino or '',
                'estado':dict(g._fields['incidencia_estado'].selection).get(g.incidencia_estado,g.incidencia_estado),
                'reportes':len(rotura_por_guia[g.id]),'roturas_pendientes':sum(r.estado == 'pendiente' for r in rotura_por_guia[g.id]),
                'roturas_aprobadas':sum(r.estado == 'aprobada' for r in rotura_por_guia[g.id]),
                'cantidad_rota_m2':round(sum(r.cantidad for r in rotura_por_guia[g.id] if r.linea_id.unidad == 'm2'),3),
                'cantidad_rota_unidades':round(sum(r.cantidad for r in rotura_por_guia[g.id] if r.linea_id.unidad == 'unidad'),3),
                'transportista':g.proveedor_id.display_name or 'Sin transportista',
                'chofer':g.chofer_usuario_id.name or (g.chofer_contacto_id.name if 'chofer_contacto_id' in g._fields and g.chofer_contacto_id else '') or 'Sin usuario chofer',
                'fecha':label_date(g.create_date)})
        data = {
            'fechas':{'desde':d0.isoformat(), 'hasta':d1.isoformat(), 'agrupacion':periodo, 'base':fecha_base},
            'permisos':{'finanzas':finance,'comercial':commercial,'auditoria_menus':self.env.user.has_group('base.group_system'),
                        'operacion': self.env.user.has_group('logistica_transcash.group_logistica_manager') or self.env.user.has_group('logistica_transcash.group_transcash_consulta') or self.env.user.has_group('logistica_transcash.group_transcash_operador_rutas') or self.env.user.has_group('logistica_transcash.group_logistica_bodega') or self.env.user.has_group('base.group_system')},
            'kpis':kpis,'guias':guide_rows,'rutas':route_rows,'embarques':shipment_rows,
            'incidencias':incident_rows, 'destinos':grouped(destinations),
            'transportistas':grouped(carriers), 'choferes':grouped(drivers),
            'tendencia':[{'periodo':key, **values} for key,values in sorted(trend.items())],
            'estados_guias':[{'clave':key,'nombre':dict(guias._fields['state'].selection).get(key,key),'cantidad':val} for key,val in sorted(status_guia.items())],
            'estados_rutas':[{'clave':key,'nombre':dict(rutas._fields['state'].selection).get(key,key),'cantidad':val} for key,val in sorted(status_ruta.items())],
            'estados_embarques':[{'clave':key,'nombre':dict(embarques._fields['state'].selection).get(key,key),'cantidad':val} for key,val in sorted(status_embarque.items())],
            'notas':[
                'Origen: tablas operativas de Odoo 18, NO registros de prueba ni solo guías importadas en tc.guide.',
                'Por defecto el periodo filtra fecha de creación; incluye guías y embarques aún sin iniciar traslado.',
                'Los viajes programados no equivalen a viajes realizados; las salidas reales tienen indicador independiente.',
                'Fecha prevista en embarques usa fecha de creación porque su fecha prevista es un campo calculado no buscable.',
                'Kg: suma de pesos de líneas, o peso de cabecera cuando no hay peso informado en líneas. m², metros lineales y unidades no se mezclan.',
                'El total de rutas en borrador puede incluir guías seleccionadas que aún no están confirmadas.',
                'Las tablas detalladas muestran hasta 300 registros recientes; los indicadores usan todos los del periodo.',
                'Los rankings de destino/chofer/transportista agrupan guías; un viaje puede tener varios destinos.',
                'Novedades = guías con incidencia o recepción con novedades. Roturas = reportes de daño no rechazados; una guía puede registrar varios.',
                'Las cantidades dañadas en m² y unidades se reportan por separado. No sumamos unidades incompatibles.',
                'La clasificación por proveedor corresponde al TRANSPORTISTA, no al fabricante/proveedor del producto.',
            ],
        }
        if finance:
            liqu = fetch('transcash.pago.liquidacion','create_date')
            estados = Counter(l.estado for l in liqu)
            currencies = defaultdict(lambda:{'acordado':0.0,'pagado':0.0,'pendiente':0.0})
            for l in liqu:
                key = l.moneda_id.name or 'SIN-MONEDA'
                currencies[key]['acordado'] += l.total_acordado
                currencies[key]['pagado'] += l.total_pagado
                currencies[key]['pendiente'] += l.saldo_pendiente
            by_currency = [{'moneda':key, **{k:round(v,2) for k,v in values.items()}}
                           for key,values in sorted(currencies.items())]
            data['resumen_financiero_por_moneda'] = by_currency
            data['divisa'] = by_currency[0]['moneda'] if len(by_currency) == 1 else (self.env.company.currency_id.name if not by_currency else '')
            data['permisos']['monedas_multiples'] = len(currencies) > 1
            consolidated = next(iter(currencies.values()),{}) if len(currencies) <= 1 else {}
            kpis.update({'liquidaciones':len(liqu), 'liquidaciones_pendientes': sum(l.estado != 'pagada' for l in liqu),
                         'fletes_aprobados':round(consolidated.get('acordado',0),2),
                         'total_pagado':round(consolidated.get('pagado',0),2),
                         'saldo_pendiente':round(consolidated.get('pendiente',0),2)})
            if len(currencies) > 1:
                data['notas'].append('Hay varias divisas: se muestran importes separados por moneda; no se suman monedas distintas.')
            data['liquidaciones'] = [{
                'id':l.id,'modelo':'transcash.pago.liquidacion','clave':str(l.id),'nombre':l.name,
                'estado':dict(l._fields['estado'].selection).get(l.estado,l.estado),
                'transportista':l.proveedor_id.display_name or '', 'moneda':l.moneda_id.name or '',
                'guias':len(l.linea_ids), 'total':round(l.total_acordado,2),
                'pagado':round(l.total_pagado,2), 'pendiente':round(l.saldo_pendiente,2),
                'fecha':label_date(l.create_date)} for l in liqu[:300]]
            data['estados_liquidaciones'] = [{'clave':k,'nombre':dict(liqu._fields['estado'].selection).get(k,k),'cantidad':n} for k,n in sorted(estados.items())]
        if commercial:
            # Relaciones 1:1 entre fichas PRIVADAS y líneas operativas; no se
            # necesita ni se permite almacenar marca/proveedor en el modelo
            # público transcash.guia.linea.
            Private = self.env['tc.guide.line.private'].sudo()
            details = {}
            if lineas:
                linked = Private.search([('company_id', 'in', companies),
                                         ('operational_line_id', 'in', lineas.ids)])
                details.update({private.operational_line_id.id: private for private in linked})

                # Compatibilidad con guías previas a v2.3 que aún no han pasado
                # por la conciliación; unir por ID externo + ID de línea.
                missing = lineas.filtered(lambda ln: ln.id not in details and ln.guia_id.external_id_erp)
                if missing:
                    extids = list(set(missing.mapped('guia_id.external_id_erp')))
                    staged = self.env['tc.guide'].sudo().search([
                        ('company_id', 'in', companies), ('external_id', 'in', extids)])
                    private_rows = Private.search([('line_id.guide_id', 'in', staged.ids)]) if staged else Private.browse()
                    fallback = {(pr.line_id.guide_id.company_id.id,
                                 pr.line_id.guide_id.external_id,
                                 pr.line_id.external_line_id): pr for pr in private_rows}
                    for line in missing:
                        key = (line.guia_id.company_id.id,
                               line.guia_id.external_id_erp, line.external_line_id)
                        if key in fallback:
                            details[line.id] = fallback[key]

            damages_by_line = defaultdict(list)
            for damage in roturas:
                damages_by_line[damage.linea_id.id].append(damage)

            brands = defaultdict(lambda: {
                'nombre': '', 'codigo': '', 'guias': set(), 'guias_incidencia': set(),
                'reportes': 0, 'pendientes': 0, 'aprobadas': 0,
                'cantidad_m2': 0.0, 'cantidad_unidades': 0.0,
                'cantidad_rota_m2': 0.0, 'cantidad_rota_unidades': 0.0,
                'peso_kg': 0.0,
            })
            suppliers = defaultdict(lambda: {
                'nombre': '', 'codigo': '', 'guias': set(), 'guias_incidencia': set(),
                'reportes': 0, 'pendientes': 0, 'aprobadas': 0,
                'cantidad_m2': 0.0, 'cantidad_unidades': 0.0,
                'cantidad_rota_m2': 0.0, 'cantidad_rota_unidades': 0.0,
                'peso_kg': 0.0,
            })
            for line in lineas:
                guide = line.guia_id
                private = details.get(line.id)
                # Los maestros privados son la referencia estructurada;
                # los valores originales sirven de respaldo auditable.
                brand_code = (private.brand_id.code or private.brand_code_raw) if private else ''
                brand_name = (private.brand_id.name or private.brand_name_raw) if private else ''
                supplier_code = (private.supplier_id.external_code or private.supplier_code_raw) if private else ''
                supplier_name = (private.supplier_id.name or private.supplier_name_raw) if private else ''
                for bucket, code, name in (
                    (brands, brand_code or 'SIN-CODIGO', brand_name or 'Marca sin informar'),
                    (suppliers, supplier_code or 'SIN-CODIGO', supplier_name or 'Proveedor sin informar'),
                ):
                    # No mezclar accidentalmente maestros de diferentes empresas.
                    row = bucket[(guide.company_id.id, code)]
                    row['codigo'] = code
                    row['nombre'] = name
                    row['guias'].add(guide.id)
                    # Solo atribuir al fabricante/Marca el daño documentado
                    # sobre SU línea. Novedades generales del viaje no prueban
                    # que todos los fabricantes de esa guía tengan una falla.
                    if damages_by_line[line.id]:
                        row['guias_incidencia'].add(guide.id)
                    row['peso_kg'] += max(0.0, line.peso_kg or 0.0)
                    if line.unidad == 'm2':
                        row['cantidad_m2'] += line.cantidad or 0.0
                    elif line.unidad == 'unidad':
                        row['cantidad_unidades'] += line.cantidad or 0.0
                    for damage in damages_by_line[line.id]:
                        row['reportes'] += 1
                        row['pendientes'] += int(damage.estado == 'pendiente')
                        row['aprobadas'] += int(damage.estado == 'aprobada')
                        if line.unidad == 'm2':
                            row['cantidad_rota_m2'] += damage.cantidad
                        elif line.unidad == 'unidad':
                            row['cantidad_rota_unidades'] += damage.cantidad

            def private_rows(bucket):
                return sorted(({
                    'clave': '%s:%s' % key,
                    'codigo': value['codigo'], 'nombre': value['nombre'],
                    'guias': len(value['guias']),
                    'incidencias': len(value['guias_incidencia']),
                    'reportes': value['reportes'],
                    'pendientes': value['pendientes'],
                    'aprobadas': value['aprobadas'],
                    'cantidad_m2': round(value['cantidad_m2'], 3),
                    'cantidad_unidades': round(value['cantidad_unidades'], 3),
                    'cantidad_rota_m2': round(value['cantidad_rota_m2'], 3),
                    'cantidad_rota_unidades': round(value['cantidad_rota_unidades'], 3),
                    'peso_kg': round(value['peso_kg'], 3),
                } for key, value in bucket.items()),
                    key=lambda row: (-row['reportes'], -row['incidencias'], -row['guias'], row['nombre']))

            data['marcas'] = private_rows(brands)
            data['proveedores_producto'] = private_rows(suppliers)
            data['notas'].append('Análisis comercial: solo daños registrados en la línea del producto se atribuyen a su marca/proveedor. Las incidencias generales de viaje no se imputan a todos sus fabricantes. Roturas rechazadas excluidas.')
        return data

    @api.model
    def audit_menus(self):
        self._check_bi_access()
        if not self.env.user.has_group('base.group_system'):
            raise AccessError(_('La revisión técnica de menús es exclusiva de Administración.'))
        root = self.env.ref('logistica_transcash.menu_transcash_root')
        menus = self.env['ir.ui.menu'].sudo().search([('id','child_of',root.id),('active','=',True)], order='sequence,id')
        result = []
        for menu in menus:
            if menu == root: continue
            action = menu.action
            kind = action._name if action else ''
            model = (action.res_model if kind == 'ir.actions.act_window' else '') if action else ''
            exists = bool(model in self.env.registry.models) if model else True
            if not action:
                status = 'Carpeta'
            elif not exists:
                status = 'Modelo no instalado'
            elif kind == 'ir.actions.act_window' and not (action.view_mode or '').strip():
                status = 'Sin modo de vista'
            elif kind == 'ir.actions.act_window':
                status = 'Acción y modelo válidos'
            elif kind == 'ir.actions.client' and action.tag in ('transcash_dashboard','tc_logistica_bi_v22'):
                status = 'Dashboard registrado'
            else:
                status = 'Acción definida · probar apertura'
            result.append({'id':menu.id,'clave':str(menu.id),'nombre':menu.complete_name,
                'accion':action.name if action else 'Carpeta',
                'modelo':model or kind or 'Carpeta',
                'estado':status,
                'action_id':action.id if action else False,
                'tipo':kind,
                'visible':bool(menu.active)})
        return result
