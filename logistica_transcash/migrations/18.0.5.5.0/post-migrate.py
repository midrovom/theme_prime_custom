"""Clasificar recepciones de versiones anteriores sin asumir que fueron conformes."""


def migrate(cr, version):
    cr.execute("""
        UPDATE transcash_guia
        SET resultado_recepcion = 'historica'
        WHERE fecha_entrega IS NOT NULL
          AND (resultado_recepcion IS NULL OR resultado_recepcion = 'pendiente')
    """)
