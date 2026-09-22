# Conedera — Catastro Comercial para Odoo 18 Community

Versión: **18.0.1.8.3**

Módulo de Catastro Comercial móvil integrado con Contactos y Ventas estándar de Odoo.

Funciones principales:

- una ficha de Catastro por cliente/RUC/cédula;
- búsqueda/reutilización de clientes existentes;
- CAPA, tiendas, tipos de negocio, marcas y horario estructurado;
- visitas con encuesta, foto y GPS opcional mientras se use HTTP;
- proformas estándar `sale.order` y bitácora comercial;
- análisis de productos/cantidades/precios proformados;
- jerarquía Comercial / Supervisor / Administrador;
- equipos comerciales reutilizando `crm.team`;
- solicitudes auditadas de edición y reasignación;
- protección de Catastros registrados;
- Data Guard en upgrades.

## Permisos

Se administran dentro del propio módulo:

**Catastro Comercial > Configuración > Usuarios y permisos**

Los equipos se administran en:

**Catastro Comercial > Configuración > Equipos comerciales**

Los equipos técnicos `Sitio web` y `Punto de Venta` están excluidos. En 1.8.3 la selección de equipo se hace desde el Catastro/Permisos sin abrir el tablero gráfico estándar, y el bloqueo del Catastro usa una vista aislada para no depender de módulos externos como Ventas en Ruta.
