"""Progress presentation for a transaction-by-transaction import runner."""

ACTIVE_STATES = frozenset(("queued", "loading"))
FINISHED_STATES = frozenset(("ready", "archived"))


def progress_values(state, loaded=0, total=0, total_rows=0):
    loaded, total, total_rows = int(loaded or 0), int(total or 0), int(total_rows or 0)
    done = state in FINISHED_STATES
    percent = 100.0 if done else min(99.9, max(0.0, 100.0 * loaded / total)) if total else 0.0
    if done:
        message = "Importación terminada: %s facturas y %s registros de origen." % (loaded, total_rows)
    elif state == "queued":
        message = "Archivo recibido. Pendiente de validar y preparar los registros."
    elif state == "loading":
        message = "Importadas %s de %s facturas." % (loaded, total)
    elif state == "receiving":
        message = "La API todavía está enviando los bloques del archivo."
    else:
        message = "La importación se detuvo. Revise el detalle del error."
    return {"progress_percent": round(percent, 1), "progress_message": message,
            "done": done, "can_continue": state in ACTIVE_STATES, "failed": state == "error"}
