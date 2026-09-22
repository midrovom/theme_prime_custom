# Validación 18.0.1.8.7

Validación estática ejecutada sobre el código fuente antes de empaquetar.

## Resultado

- Manifest: versión 18.0.1.8.7 y rutas de data/assets válidas.
- 53 archivos Python compilan correctamente.
- 20 archivos XML parsean correctamente.
- 128 IDs XML explícitos sin duplicados.
- `__init__.py` raíz contiene únicamente `from . import models`.
- `action_census_customer_lookup` carga antes de las vistas que lo usan en botones `header`.
- Botón **Nuevo catastro** presente en Kanban y Lista con `display=always`.
- Menú raíz **Catastro Comercial** abre `action_census_partners`.
- Submenú principal renombrado a **Catastros**.
- Botón **Refrescar estado** apunta a `action_refresh_census_unlock_status`.
- Estado Pendiente/Aprobada/Rechazada/Vencida visible en la ficha.
- Rechazo requiere motivo mediante `conedera.census.unlock.reject.wizard`.
- ACL del wizard de rechazo presente para Supervisor (Administrador lo hereda).
- La lista de solicitudes ya no fuerza el filtro Pendientes y contiene filtros para Rechazadas/Vencidas.
- Migración 18.0.1.8.7 con Data Guard y sin `DELETE FROM`, `TRUNCATE`, `DROP TABLE` ni `DROP COLUMN`.
- JavaScript existente validado con `node --check`.

## Limitación

No se dispone en este entorno de un runtime completo Odoo 18 + PostgreSQL para ejecutar `TransactionCase` ni instalar el módulo. La validación definitiva debe hacerse con `-u conedera_odoo_census` en una base de prueba/backup del servidor.
