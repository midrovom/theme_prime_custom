"""Al migrar, bloquear re-liquidación de embarques con estado financiero legado."""

def migrate(cr, version):
    cr.execute("""SELECT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='transcash_embarque' AND column_name='pago_estado')""")
    if cr.fetchone()[0]:
        cr.execute("""UPDATE transcash_embarque
            SET legado_liquidacion_bloqueada = TRUE
            WHERE pago_estado IN ('autorizado','facturado','pagado')""")
