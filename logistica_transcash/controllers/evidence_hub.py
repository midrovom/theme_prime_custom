"""Galería de evidencias unificada: datos preparados exclusivamente para registros autorizados.

La autorización de lectura se resuelve ANTES de llamar a estas funciones.
No se entregan valores, liquidaciones ni bitácoras de objeciones a la plantilla.
"""

ALLOWED_IMAGE = ('image/jpeg','image/png','image/webp','image/heic','image/heif')
ALLOWED_VIDEO = ('video/mp4','video/webm','video/quicktime','video/3gpp')


def gallery_for_trip(trip, guide=None, include_loading=True):
    """Devuelve solo referencias de media de una guía o del viaje ya autorizado."""
    guides = guide if guide else trip.guia_ids
    carga = []
    descarga = []
    firmas = []
    if trip and include_loading:
        # Un cliente nunca invoca esta rama: los videos pueden incluir a otros destinatarios.
        for route in trip.ruta_ids.sorted('id'):
            route_items = []
            for ev in route.evidencia_carga_ids.sorted('id'):
                if ev.mime not in ALLOWED_IMAGE + ALLOWED_VIDEO:
                    continue
                route_items.append({
                    'url': '/transcash/rutas/evidencia/%d' % ev.id,
                    'kind': 'video' if ev.mime in ALLOWED_VIDEO else 'foto',
                    'title': ev.nombre or 'Evidencia de carga',
                    'subtitle': '%s · %s' % (route.name, route.destino_nombre or ''),
                    'author': ev.usuario_id.name or 'Logística', 'date': str(ev.fecha or ''),
                })
            if route.video_mime in ALLOWED_VIDEO and route.fecha_video and route.state in ('cargada','aceptada'):
                route_items.append({
                    'url':'/transcash/rutas/%d/video' % route.id, 'kind':'video',
                    'title':route.video_nombre or 'Video de carga histórico',
                    'subtitle': '%s · %s' % (route.name,route.destino_nombre or ''),
                    'author':route.video_por_id.name or 'Logística', 'date':str(route.fecha_video or ''),
                })
            carga.extend(route_items)
    # Evidencias legadas de carga: solo del viaje completo o de la guía autorizada.
    for g in guides:
        for ev in g.evidencia_ids.sorted('id'):
            if ev.archivo_mime not in ALLOWED_IMAGE + ALLOWED_VIDEO:
                continue
            entry = {
                'url':'/transcash/evidencia/%d/archivo' % ev.id,
                'kind':'video' if ev.archivo_mime in ALLOWED_VIDEO else 'foto',
                'title': ev.archivo_nombre or dict(ev._fields['tipo'].selection).get(ev.tipo) or 'Evidencia',
                'subtitle':'Guía %s · %s' % (g.name,dict(ev._fields['tipo'].selection).get(ev.tipo) or ''),
                'author':ev.autor_usuario_id.name or 'Usuario', 'date':str(ev.create_date or ''),
            }
            if ev.tipo == 'carga':
                if include_loading or guide:
                    carga.append(entry)
            elif ev.tipo in ('llegada','cliente','novedad'):
                # Las observaciones internas del traslado no forman parte de la vista del destinatario.
                if include_loading or ev.tipo in ('llegada','cliente'):
                    descarga.append(entry)
        if g.firma_receptor_fecha:
            firmas.append({
                'url':'/transcash/guias/%d/firma' % g.id, 'kind':'firma',
                'title':'Firma de recepción', 'subtitle':'Guía %s' % g.name,
                'author':g.persona_presente_chofer or g.recibido_por or 'Receptor declarado',
                'date':str(g.firma_receptor_fecha or g.fecha_cierre_chofer or ''),
            })
    return {'gallery_carga':carga, 'gallery_descarga':descarga,
            'gallery_firmas':firmas, 'gallery_is_guide':bool(guide),
            'gallery_count':len(carga)+len(descarga)+len(firmas)}


def gallery_for_guide(guide, is_recipient_only=False):
    """El cliente obtiene SOLO su guía; nunca rutas completas ni datos de otro receptor."""
    return gallery_for_trip(guide.embarque_id, guide=guide,
                            include_loading=not is_recipient_only)
