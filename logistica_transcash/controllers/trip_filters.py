"""V5.29. Filtros de embarques: condiciones consultables y seguras por perfil.

Los filtros sólo restringen consultas. El dominio de propiedad/compañía se
aplica ANTES en el controlador y NUNCA se reemplaza por estos dominios.
"""
FILTERS = (
    ('curso', 'En curso'),
    ('revision', 'En revisión'),
    ('incidencias', 'Novedades del cliente'),
    ('entregados', 'Entregados'),
    ('todos', 'Todos'),
)


def available_filters(internal=False, supplier=False):
    """Chofer: sólo operación. Proveedor: revisión de SU factura, no del cliente."""
    if internal:
        return FILTERS
    hidden = ('incidencias',) if supplier else ('revision', 'incidencias')
    return tuple(item for item in FILTERS if item[0] not in hidden)


def resolve_filter(requested, internal=False, supplier=False):
    alias = {'pendientes': 'curso', 'en_curso': 'curso'}
    name = alias.get(requested, requested) if requested else 'curso'
    return name if name in dict(available_filters(internal, supplier)) else 'curso'


def filter_domain(name, supplier=False):
    """Dominios de Odoo 18 sobre campos almacenados, sin filtrar registros en sudo."""
    if name == 'curso':
        return [('state', 'in', ['preparacion', 'embarcado', 'ruta'])]
    if name == 'entregados':
        return [('state', '=', 'entregado')]
    if name == 'revision':
        # Portal transportista sólo ve sus facturas en revisión (dominio de
        # proveedor y compañía ya aplicado en el controlador).
        if supplier:
            return [('liquidacion_linea_id', 'any', [('liquidacion_id.estado', 'in', ['revision', 'observada'])])]
        # Personal interno: carga objetada, flete por aprobar o factura observada.
        return ['|', '|', ('objecion_pendiente', '=', True),
                '&', ('state', '=', 'entregado'), ('estado_aprobacion', '=', 'pendiente'),
                ('liquidacion_linea_id', 'any', [('liquidacion_id.estado', 'in', ['revision', 'observada'])])]
    if name == 'incidencias':
        # Ambas situaciones proceden de la recepción del destinatario.
        # Las roturas pendientes también abren incidencia_estado en la guía.
        return [('guia_ids', 'any', ['|', ('incidencia_estado', '=', 'abierta'),
                                    ('resultado_recepcion', '=', 'con_novedades')])]
    return []
