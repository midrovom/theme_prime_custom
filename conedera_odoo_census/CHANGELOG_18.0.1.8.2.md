# Conedera Catastro Comercial — 18.0.1.8.2

## Correcciones principales

- Corrige el error `Modelo gráfico sin definir para el equipo de ventas: Sitio web`.
- `Equipo comercial` deja de ser seleccionable manualmente en el Catastro; se calcula desde el vendedor y sus equipos habilitados.
- Los equipos técnicos estándar `Sitio web` y `Punto de Venta` no pueden habilitarse para Catastro.
- Las acciones de equipos se abren con contexto de Ventas (`in_sales_app=True`).
- Nuevo permiso explícito del módulo: **Comercial / Supervisor / Administrador**.
- Nuevo menú **Catastro Comercial > Configuración > Usuarios y permisos**.
- El Administrador de Catastro puede administrar equipos y miembros sin recibir permisos globales de Configuración de Odoo.
- En una actualización desde versiones anteriores se migran permisos existentes:
  - usuarios de Ventas -> Comercial;
  - líderes de equipos Catastro -> Supervisor;
  - administradores de Ventas y administradores del sistema -> Administrador de Catastro.
- El usuario administrador estándar recibe el rol Administrador también en una instalación nueva.
- Se recuperan de forma conservadora Catastros históricos sin vendedor/equipo válido.
- El botón se denomina **Registrar y proteger** y devuelve mensajes funcionales cuando falta un equipo o un rol.
- Se mantiene el Data Guard; la migración 1.8.2 no contiene operaciones destructivas sobre datos comerciales.

## Jerarquía

- **Comercial**: ve sus Catastros; registra visitas/proformas; no elimina Catastros.
- **Supervisor**: debe ser líder del Equipo comercial; ve el equipo y revisa solicitudes.
- **Administrador**: ve todos los Catastros y administra equipos/permisos/configuración.

## Configuración recomendada

1. Asignar roles en **Catastro Comercial > Configuración > Usuarios y permisos**.
2. Configurar equipos en **Catastro Comercial > Configuración > Equipos comerciales**.
3. Cada equipo de Catastro debe tener un líder y sus vendedores como miembros.
4. El equipo debe tener activado **Disponible para Catastro**.
