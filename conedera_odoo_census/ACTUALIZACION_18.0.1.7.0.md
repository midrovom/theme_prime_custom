# Actualización 18.0.1.7.0 — Jerarquía, duplicados y control de cambios

## Qué cambia

- Alta predictiva: el primer campo de **Nuevo catastro** es un Many2one de `res.partner`. Permite escribir RUC, cédula o nombre y utiliza la búsqueda estándar de Odoo (incluye VAT/RUC).
- Si existen varias fichas visibles, el usuario selecciona cuál reutilizar. Si el documento ya tiene un Catastro asignado a otro comercial/equipo, se bloquea una nueva alta.
- Los contactos duplicados históricos pueden coexistir, pero solo una ficha puede quedar marcada como Catastro activo para un mismo RUC/cédula.
- **Supervisor automático por Equipo de Ventas (`crm.team`)**: el líder del equipo ve los Catastros de sus miembros y puede aprobar solicitudes de edición; no requiere un grupo adicional.
- Comercial: ve sus Catastros. Supervisor: ve su equipo. Administrador de Ventas: ve todos.
- Al completar un Catastro nuevo hay que pulsar **Registrar catastro**. Desde ese momento el maestro queda protegido.
- El comercial puede seguir agregando visitas/proformas, pero para editar datos maestros debe enviar **Solicitar edición**.
- El supervisor o administrador aprueba por 2 horas o rechaza desde **Catastro Comercial > Solicitudes de edición**.
- El comercial nunca puede eliminar/desactivar un Catastro. Supervisores tampoco pueden eliminarlo; solo Administrador de Ventas.
- Los Catastros existentes se migran como protegidos para conservar la trazabilidad.
- Data Guard pre/post upgrade conserva y compara conteos de Catastros, visitas, horarios, relaciones y proformas.

## Configuración de equipos

Use **Ventas > Configuración > Equipos de ventas**. En Odoo cada equipo tiene un líder y miembros.

1. Configure el supervisor como **Líder del equipo**.
2. Agregue los comerciales como miembros del equipo.
3. No necesita asignar un grupo adicional: el liderazgo del equipo determina automáticamente quién es supervisor.
4. El Administrador de Ventas estándar de Odoo ve todo.

Los nuevos Catastros toman el equipo principal del vendedor. Para casos especiales, el Administrador de Ventas puede corregir Vendedor/Equipo desde la ficha.

## Instalación recomendada

No desinstale el módulo.

```bash
sudo systemctl stop odoo18

rm -rf /opt/odoo18/odoo18/custom-addons/conedera_odoo_census
unzip conedera_odoo_census_18_community_18.0.1.7.0.zip \
  -d /opt/odoo18/odoo18/custom-addons/

sudo -u odoo18 /opt/odoo18/odoo18/odoo-bin \
  -c /etc/odoo18.conf \
  -d NOMBRE_DE_TU_BASE \
  -u conedera_odoo_census \
  --stop-after-init \
  --no-http
```

Si el comando termina sin traceback:

```bash
sudo systemctl start odoo18
```

## Pruebas funcionales después del upgrade

1. Comercial A entra a Catastro > Clientes: solo debe ver sus Catastros.
2. Supervisor del Equipo A: debe ver los Catastros de los miembros del Equipo A.
3. Administrador de Ventas: debe ver todos.
4. Nuevo catastro: escriba parte de un RUC/nombre en **Buscar cliente existente** y seleccione una coincidencia.
5. Con un RUC duplicado histórico, seleccione la ficha correcta; no debe crear otra si ya existe un Catastro activo.
6. En un Catastro protegido, el comercial debe ver datos maestros en solo lectura y sí poder registrar visita/proforma.
7. Comercial pulsa **Solicitar edición**, ingresa motivo.
8. Supervisor aprueba desde Solicitudes de edición.
9. Comercial vuelve al cliente: durante 2 horas puede editar datos maestros.
10. Comercial no debe poder borrar/archivar el Catastro.

## Conservación de datos

La migración 18.0.1.7.0 no ejecuta `DELETE`, `TRUNCATE`, `DROP TABLE` ni `DROP COLUMN`.
Antes del upgrade registra conteos de datos operativos y después verifica que ninguno disminuya; si disminuye, la actualización aborta y PostgreSQL revierte la transacción.
