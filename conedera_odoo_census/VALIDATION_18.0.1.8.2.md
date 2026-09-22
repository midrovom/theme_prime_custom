# Reporte de validación — 18.0.1.8.2

Validación estática ejecutada sobre el árbol final antes de empaquetar:

- 42 archivos Python compilados correctamente.
- 20 XML parseados correctamente.
- 124 IDs XML explícitos sin duplicados.
- 24 entradas ACL parseadas.
- 53 botones `type="object"` comprobados contra métodos Python existentes.
- 3 archivos JavaScript pasaron `node --check`.
- Manifiesto y rutas de data/assets validados.
- `census_team_id` es de solo lectura en la ficha de Catastro.
- La acción de Equipos comerciales lleva `in_sales_app=True`.
- `crm.team.census_enabled` tiene default `False` fuera del flujo de Catastro.
- Los equipos técnicos `sales_team.salesteam_website_sales` y `sales_team.pos_sales_team` están bloqueados para Catastro.
- Existen grupos separados Comercial / Supervisor / Administrador.
- Existe asistente `Usuarios y permisos` y ACL exclusiva para Administrador de Catastro.
- Administrador de Catastro tiene ACL controlada para `crm.team` y `crm.team.member`.
- La migración 18.0.1.8.2 asigna permisos a usuarios heredados y repara equipos técnicos/históricos.
- La migración 18.0.1.8.2 mantiene Data Guard y no contiene `DELETE FROM`, `TRUNCATE`, `DROP TABLE` ni `DROP COLUMN`.
- Los checks runtime ya no dependen implícitamente de `sales_team.group_sale_manager`; utilizan los roles explícitos del Catastro.

## Límite de esta validación

Este entorno no ejecuta un servidor Odoo 18 Community + PostgreSQL con la base real del cliente. Por lo tanto, el upgrade CLI `-u conedera_odoo_census` en una copia/backup de la base sigue siendo la prueba de integración definitiva.
