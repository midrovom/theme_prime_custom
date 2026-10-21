# TRANSCASH v1.32 — Período personalizado con mes en curso

- **Personalizado → Hasta** muestra el mes actual (por ejemplo, 2026-10 · en curso), aunque no haya terminado.
- Una sincronización de los cuatro endpoints incorpora los movimientos de dicho mes sin perder las estadísticas de los últimos 12 meses cerrados.
- **3, 6, 12 meses y Año actual** mantienen como referencia el último mes cerrado, sin inflar períodos incompletos.
- Una versión previa muestra octubre seleccionable, pero sin importes del mes hasta que se vuelva a sincronizar API Administrator; se muestra advertencia explícita.
- El mes abierto se marca y no se trata como cierre; la demanda diaria se estima sobre los días transcurridos y XYZ solo toma meses cerrados.
- Se conservan todos los filtros, dashboards, fotografías, exportación Excel y multiempresa.
