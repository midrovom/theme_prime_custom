"""Galería de evidencias unificada: datos preparados exclusivamente para registros autorizados.

La autorización de lectura se resuelve ANTES de llamar a estas funciones.
No se entregan valores, liquidaciones ni bitácoras de objeciones a la plantilla.
"""

ALLOWED_IMAGE = ('image/jpeg','image/png','image/webp','image/heic','image/heif')
ALLOWED_VIDEO = ('video/mp4','video/webm','video/quicktime','video/3gpp')


def _guide_is_closed(g):
    return bool(g.fecha_cierre_chofer or g.state in ('entregada', 'lista_pago', 'facturada', 'pagada'))


def _guide_entry(ev, g):
    return {
        'url': '/transcash/evidencia/%d/archivo' % ev.id,
        'kind': 'video' if ev.archivo_mime in ALLOWED_VIDEO else 'foto',
        'title': ev.archivo_nombre or dict(ev._fields['tipo'].selection).get(ev.tipo) or 'Evidencia',
        'subtitle': 'Guía %s · %s' % (g.name, dict(ev._fields['tipo'].selection).get(ev.tipo) or ''),
        'author': ev.autor_usuario_id.name or 'Usuario', 'date': str(ev.create_date or ''),
    }


def gallery_for_trip(trip, guide=None, include_loading=True):
    """Expediente por hoja de ruta: carga, descargas y firmas de sus guías.

    La autorización se ejecuta ANTES de llamar a esta función. Para un receptor
    se envía solo `guide` e `include_loading=False`; jamás se mezclan otras guías
    de la ruta ni videos generales de carga.
    """
    available_guides = guide if guide else (trip.guia_ids if trip else guide)
    groups = []
    known = set()
    routes = trip.ruta_ids.sorted('id') if trip else []
    if guide and guide.hoja_ruta_id and guide.hoja_ruta_id in routes:
        routes = guide.hoja_ruta_id
    if guide and not include_loading:
        # No revelar datos internos de planificación del camión al destinatario.
        routes = []

    def add_group(title, destination, guides, route=None):
        nonlocal groups
        guides = guides.sorted('id')
        closed = len(guides.filtered(_guide_is_closed))
        if route:
            # Misma fuente de verdad que el statusbar de Odoo y el resumen PWA.
            status = route.estado_operativo
            status_label = dict(route._fields['estado_operativo'].selection).get(status) or 'Estado pendiente'
            status_style = ('completa' if status == 'entregada' else
                            'parcial' if status == 'en_entrega' else 'pendiente')
        else:
            status_style = ('completa' if guides and closed == len(guides) else
                            'parcial' if closed else 'pendiente')
            status_label = ('Guía entregada' if guides and closed == len(guides) else
                            'En entrega' if closed else 'Pendiente')
        group = {
            'id': ('ruta-%d' % route.id) if route else 'sin-ruta',
            'name': title, 'destination': destination,
            'guide_count': len(guides), 'closed_count': closed,
            'state': status_style,
            'state_label': status_label,
            'carga': [], 'descarga': [], 'firmas': [], 'count': 0,
        }
        if route and include_loading:
            for ev in route.evidencia_carga_ids.sorted('id'):
                if ev.mime not in ALLOWED_IMAGE + ALLOWED_VIDEO:
                    continue
                group['carga'].append({
                    'url': '/transcash/rutas/evidencia/%d' % ev.id,
                    'kind': 'video' if ev.mime in ALLOWED_VIDEO else 'foto',
                    'title': ev.nombre or 'Evidencia de carga',
                    'subtitle': '%s · %s' % (route.name, route.destino_nombre or ''),
                    'author': ev.usuario_id.name or 'Logística', 'date': str(ev.fecha or ''),
                })
            if route.video_mime in ALLOWED_VIDEO and route.fecha_video and route.state in ('cargada', 'aceptada'):
                group['carga'].append({
                    'url': '/transcash/rutas/%d/video' % route.id,
                    'kind': 'video', 'title': route.video_nombre or 'Video de carga histórico',
                    'subtitle': '%s · %s' % (route.name, route.destino_nombre or ''),
                    'author': route.video_por_id.name or 'Logística',
                    'date': str(route.fecha_video or ''),
                })
        for g in guides:
            for ev in g.evidencia_ids.sorted('id'):
                if ev.archivo_mime not in ALLOWED_IMAGE + ALLOWED_VIDEO:
                    continue
                entry = _guide_entry(ev, g)
                if ev.tipo == 'carga':
                    # La carga de una guía heredada sólo se muestra si el
                    # usuario tiene permitido ver ese archivo individual.
                    if include_loading or guide:
                        group['carga'].append(entry)
                elif ev.tipo in ('llegada', 'cliente', 'novedad'):
                    if include_loading or ev.tipo in ('llegada', 'cliente'):
                        group['descarga'].append(entry)
            if g.firma_receptor_fecha:
                group['firmas'].append({
                    'url': '/transcash/guias/%d/firma' % g.id, 'kind': 'firma',
                    'title': 'Firma de recepción · Guía %s' % g.name,
                    'subtitle': 'Guía %s' % g.name,
                    'author': g.persona_presente_chofer or g.recibido_por or 'Receptor declarado',
                    'date': str(g.firma_receptor_fecha or g.fecha_cierre_chofer or ''),
                })
        group['count'] = sum(len(group[stage]) for stage in ('carga', 'descarga', 'firmas'))
        groups.append(group)

    for route in routes:
        # Nunca tomar guías de otro embarque por una relación histórica errónea.
        route_guides = available_guides.filtered(lambda g:
            g.hoja_ruta_id == route and (not trip or g.embarque_id == trip))
        if not route_guides:
            if not guide:  # Mostrar ruta sin documentación y sin guías, para seguimiento.
                add_group(route.name, route.destino_nombre or '', route_guides, route)
            continue
        known.update(route_guides.ids)
        add_group(route.name, route.destino_nombre or '', route_guides, route)

    ungrouped = available_guides.filtered(lambda g: g.id not in known)
    if ungrouped:
        if guide and not include_loading:
            add_group('Mi guía', '', ungrouped)
        else:
            add_group('Guías sin hoja de ruta' if not guide else 'Evidencias de la guía',
                      '', ungrouped)
    carga = [media for group in groups for media in group['carga']]
    descarga = [media for group in groups for media in group['descarga']]
    firmas = [media for group in groups for media in group['firmas']]
    return {
        'gallery_routes': groups, 'gallery_carga': carga,
        'gallery_descarga': descarga, 'gallery_firmas': firmas,
        'gallery_is_guide': bool(guide),
        'gallery_count': len(carga) + len(descarga) + len(firmas),
    }


def gallery_for_guide(guide, is_recipient_only=False):
    """El cliente ve únicamente su guía, no la carga compartida del vehículo."""
    return gallery_for_trip(guide.embarque_id, guide=guide,
                            include_loading=not is_recipient_only)
