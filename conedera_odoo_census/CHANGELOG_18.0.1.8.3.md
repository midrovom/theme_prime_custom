# Conedera Catastro Comercial — 18.0.1.8.3

## Correcciones principales

### Equipo comercial en móvil

- El campo **Equipo comercial** vuelve a ser seleccionable mientras el Catastro está en borrador.
- El desplegable solo muestra equipos habilitados para Catastro donde el vendedor responsable sea líder o miembro.
- Después de **Registrar y proteger**, el equipo queda bloqueado y los cambios posteriores deben realizarse mediante el flujo de reasignación.
- Se mantienen bloqueados los equipos técnicos estándar `Sitio web` y `Punto de Venta`.
- `Catastro > Configuración > Equipos comerciales` usa vistas propias simples de lista/formulario y ya no hereda el dashboard de `crm.team`; de esta forma no solicita `dashboard_graph_data` y evita el error `Modelo gráfico sin definir para el equipo de ventas: Sitio web`.

### Usuarios y permisos

- El asistente **Usuarios y permisos** permite seleccionar, además del rol, el Equipo comercial del usuario.
- Para rol **Comercial**, el usuario se agrega como miembro del equipo.
- Para rol **Supervisor**, el usuario queda como líder del equipo y miembro si corresponde.
- La actualización vuelve a asegurar de forma aditiva los grupos de Catastro para usuarios de Ventas, líderes y administradores; no elimina grupos de otros addons.

### Compatibilidad con Ventas en Ruta

- `Registrar y proteger` y `Terminar edición` ya no devuelven un `reload` genérico de `res.partner`.
- Esas acciones reabren explícitamente la vista aislada `view_partner_form_census_mobile`.
- Los cambios internos de bloqueo (`census_locked`, equipo, fecha y habilitación temporal) se escriben únicamente sobre columnas del módulo mediante una actualización SQL controlada, después de validar permisos/equipo. Esto evita ejecutar hooks de terceros sobre `res.partner.write` que puedan requerir acceso a modelos opcionales como `route.sale.visit`.
- No se añade ninguna dependencia con **Ventas en Ruta** ni se conceden permisos globales sobre sus visitas.

### Conservación de datos

- No se eliminan Catastros, visitas, proformas, fotos, horarios, marcas ni relaciones existentes.
- La migración 18.0.1.8.3 solo deshabilita equipos técnicos para Catastro y repara asignaciones inválidas cuando existe un equipo comercial válido para el vendedor.
- Se mantiene el Data Guard pre/post upgrade.
