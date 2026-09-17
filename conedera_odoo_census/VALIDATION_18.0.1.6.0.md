# Validación estática — Odoo 18 Community 18.0.1.6.0

OK: Manifiesto 18.0.1.6.0 parseado
OK: 28 archivos Python compilan
OK: 14 XML parsean y 82 IDs externos son únicos
OK: Assets backend existen físicamente
OK: JavaScript pasa node --check
OK: 37 botones object apuntan a métodos Python
OK: Foto: captura móvil, persistencia /web/image, ampliación y fallback presentes
OK: Guardar/Finalizar son acciones táctiles grandes en móvil
OK: Data Guard 1.6 presente y sin SQL destructivo
OK: Foto sigue almacenada como fields.Image attachment=True
OK: Tarjeta kanban de visita muestra foto guardada

**RESULTADO: PASSED**

Limitación: no hay un runtime Odoo 18 + PostgreSQL en este entorno; el upgrade real debe ejecutarse con `-u conedera_odoo_census` sobre backup/copia antes de producción.
