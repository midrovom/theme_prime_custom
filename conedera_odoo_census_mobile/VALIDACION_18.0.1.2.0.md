# Verificación de integración Conedera PWA 18.0.1.2.0

Modulo base inspeccionado: `conedera_odoo_census 18.0.1.8.7`. La PWA es un complemento heredado, sin modificaciones a modelos del modulo base.

| Integración | Esquema/modelo original | Implementación PWA |
|---|---|---|
| Buscar RUC/cedula/nombre | `conedera.census.customer.lookup.wizard.search_global_candidates` | Ruta JSON global con `status`, `can_use`, `can_open`, `can_request` |
| Validar duplicados | `_census_global_partners_by_identity`, `res.partner` | Comparación de RUC global al sincronizar y nombre exacto antes de crear |
| Reutilizar contacto | `conedera.census.customer.lookup.wizard.action_use_selected` | Validación `can_use` y activación auditada sin duplicar |
| Solicitar reasignación | `conedera.census.reassignment.request` | Ruta online sujeta a reglas del modelo original |
| Solicitar edición | `conedera.census.unlock.request` | Ruta online, estado en campos calculados del catastro |
| Rechazo con motivo | `census_latest_unlock_review_note` | Visualización directa y botón Actualizar |
| Edición de campos protegidos | `_check_census_master_write` | Verificada en escritura, incluido reemplazo de horarios |
| Horarios | `conedera.partner.opening.hour` | Múltiples franjas por día y edición conservadora |
| Visitas | `conedera.census.visit` | Banderas `yes/no`, GPS, foto, observaciones y próxima visita |
| Capacidades offline | IndexedDB y Service Worker | Cola UUID, UI offline, control de cambios de usuario |
| PWA instalable | Manifest + iconos + Service Worker | PNG 192/512, maskable, escritorio/movil, HTTPS obligatorio |

## Pruebas estáticas ejecutadas

- Compilación `compileall` del complemento.
- `node --check` en el JavaScript de interfaz y de Service Worker.
- Pruebas de lógica UI Node VM: panel desktop, creación, coincidencias, horarios múltiples, cierre 24:00, errores por solapamiento, rechazo con motivo, GPS, cambio de usuario.
- Revisión de referencias XML, manifiesto y apertura del ZIP sin errores.

## Pruebas obligatorias en un servidor Odoo antes de producción

- Instalar/actualizar ambos módulos en una copia de la base, sin eliminar el original.
- Probar usuarios con permisos: Comercial, Supervisor y Administrador, incluidas reglas de compañía.
- Comprobar que el servidor renderice el nuevo PWA y no quede el Service Worker anterior.
- Comprobar todos los registros mediante relectura en el modelo base y comparar datos de horarios antes/después.
- Ejecutar caso offline en dispositivo real HTTPS (solo PWA cacheada) y verificar reintentos con UUID y permisos.

No se ejecutaron pruebas contra un servidor real Odoo ni PostgreSQL en este entorno.
