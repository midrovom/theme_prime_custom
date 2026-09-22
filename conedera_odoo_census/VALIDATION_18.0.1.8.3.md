# Reporte de validación — 18.0.1.8.3

## Resultado

**Validación estática: APROBADA.**

- Python compilable/parseable: **45 archivos**.
- XML parseable: **20 archivos**.
- IDs XML explícitos únicos: **127**.
- Botones `type="object"` comprobados contra métodos Python: **53**.
- ACL revisadas: **24 filas**.
- JavaScript backend: **3 archivos**, sintaxis validada con `node --check`.
- Manifiesto: versión **18.0.1.8.3**, rutas `data` y assets existentes.

## Casos corregidos y verificados por estructura/código

1. **Selector móvil de Equipo comercial**
   - `census_team_id` es editable mientras `census_locked=False`.
   - usa `census_allowed_team_ids` para mostrar solo equipos habilitados donde el vendedor es líder/miembro;
   - `Sitio web` y `Punto de Venta` se excluyen por XML ID y no pueden habilitarse para Catastro;
   - el backend vuelve a validar equipo, membresía, estado y compañía antes de registrar.

2. **Sin dashboard gráfico de `crm.team`**
   - `views/crm_team_views.xml` contiene vistas primarias propias;
   - no hereda `sales_team.crm_team_view_form` ni el kanban/dashboard estándar;
   - no solicita `dashboard_graph_data`;
   - evita el camino que produce `Undefined graph model for Sales Team: Sitio web`.

3. **Compatibilidad con el addon externo Ventas en Ruta**
   - `action_register_census` y `action_finish_census_edit` ya no devuelven `tag=reload`;
   - reabren explícitamente `view_partner_form_census_mobile`;
   - los cambios internos de bloqueo se limitan a columnas Conedera mediante `_census_internal_control_update`;
   - el módulo no importa, consulta ni concede permisos a `route.sale.visit`. La única mención del nombre del modelo está en documentación/comentarios de compatibilidad.

4. **Usuarios y permisos**
   - el asistente permite elegir rol + Equipo comercial;
   - Comercial se agrega como miembro; Supervisor se establece como líder y miembro;
   - el upgrade es aditivo: no elimina grupos pertenecientes a otros addons.

5. **Conservación de datos**
   - migración 18.0.1.8.3 con Data Guard pre/post;
   - no contiene `DELETE FROM`, `TRUNCATE`, `DROP TABLE` ni `DROP COLUMN`;
   - la reparación de equipos no cambia vendedor ni elimina visitas/proformas/fotos/bitácora.

## Pruebas de regresión incluidas

Se añadieron casos para:

- vendedor seleccionando equipo válido en Catastro borrador;
- intento de cambiar equipo después del bloqueo;
- `Registrar y proteger` devolviendo la vista aislada del Catastro en vez de `reload`;
- asignación de Equipo comercial desde `Usuarios y permisos`;
- se conservan además las pruebas previas de RUC único/global, reasignación, fotos, productos proformados, GPS opcional, CAPA y Data Guard.

## Límite de esta validación

Este entorno no ejecuta tu instancia real de Odoo 18, PostgreSQL ni el addon privado **Ventas en Ruta**. Por ello la comprobación definitiva es ejecutar `-u conedera_odoo_census` en una copia/backup de tu base y probar el flujo móvil. La versión está diseñada específicamente para no depender de `route.sale.visit`.
