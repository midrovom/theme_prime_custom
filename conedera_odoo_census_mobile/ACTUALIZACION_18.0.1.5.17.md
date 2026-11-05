# Catastro PWA 18.0.1.5.17 — acceso a cotizaciones

Se incorpora el acceso visible **Cotizar** en la navegación móvil y escritorio. Desde esa pantalla se puede:

- Cotizar a un catastro protegido, buscando por nombre o RUC.
- Cotizar a Consumidor Final sin catastro cuando el usuario tenga el grupo **Catastro PWA: cotizador de tienda**, la empresa activa tenga configurado su contacto de Consumidor Final y el usuario tenga permiso de creación en Ventas.
- Entender por qué la venta directa no aparece: falta permiso o configuración, sin ocultar la opción.

El formulario de catastro sigue mostrando el botón Crear cotización después de Finalizar y proteger. No se modifican cálculos, inventario, Loyalty, auditorías ni almacenamiento offline.

## Instalación

1. Respaldar base y verificar operaciones offline pendientes.
2. Reemplazar únicamente `conedera_odoo_census_mobile`.
3. Reiniciar todos los procesos Odoo y actualizar el módulo en Aplicaciones.
4. Abrir `/catastro/app?version=18.0.1.5.17`.
5. Si desea venta directa, en Odoo active el grupo **Catastro PWA: cotizador de tienda** al usuario, configure Consumidor Final para la compañía activa y otorgue permisos de Ventas para crear cotizaciones.

**Nota:** No se ha ejecutado esta actualización en la base de datos de producción.
