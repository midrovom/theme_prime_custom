"""Progress presentation for a transaction-by-transaction import runner."""

ACTIVE_STATES = frozenset(("queued", "loading"))
FINISHED_STATES = frozenset(("ready", "archived"))


def progress_values(state, loaded=0, total=0, total_rows=0, input_type="xlsx"):
    loaded, total, total_rows = int(loaded or 0), int(total or 0), int(total_rows or 0)
    done = state in FINISHED_STATES
    percent = 100.0 if done else min(99.9, max(0.0, 100.0 * loaded / total)) if total else 0.0
    if done:
        message = ("Sincronización terminada: %s facturas y %s registros del ERP." if input_type == "api"
                   else "Importación terminada: %s facturas y %s registros de origen.") % (loaded, total_rows)
    elif state == "queued":
        message = "Datos recibidos del ERP. Validando y preparando las facturas." if input_type == "api" else "Archivo recibido. Pendiente de validar y preparar los registros."
    elif state == "loading":
        message = ("Actualizadas %s de %s facturas." if input_type == "api" else "Importadas %s de %s facturas.") % (loaded, total)
    elif state == "receiving":
        message = "Recibiendo datos del ERP." if input_type == "api" else "Recibiendo los registros de origen."
    else:
        message = "La importación se detuvo. Revise el detalle del error."
    return {"progress_percent": round(percent, 1), "progress_message": message,
            "done": done, "can_continue": state in ACTIVE_STATES, "failed": state == "error"}
