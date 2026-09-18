# Conedera — Catastro Comercial para Odoo 18 Community

Módulo móvil de Catastro Comercial que reutiliza `res.partner`, Equipos de Ventas y `sale.order` de Odoo.

## Flujo principal

1. **Nuevo catastro** busca globalmente por RUC, cédula o nombre.
2. Si existe un cliente, reutiliza la misma ficha; nunca crea un segundo Catastro para la misma identificación.
3. Si el Catastro pertenece a otro vendedor, permite **solicitar reasignación** en vez de duplicarlo.
4. El líder del Equipo de Ventas origen o un Administrador aprueba/rechaza la transferencia.
5. La reasignación conserva la misma ficha, visitas, fotos, proformas, productos y bitácora.
6. El comercial completa y registra el Catastro; después queda protegido y requiere habilitación temporal para modificar el maestro.

## Jerarquía

- Comercial: sus Catastros.
- Líder del Equipo de Ventas: Catastros del equipo que lidera.
- Administrador de Ventas: todos.

## Funciones

- CAPA / capacidad de compra.
- Número de tiendas/locales.
- Tipos de negocio múltiples y marcas de celulares opcionales.
- Horarios estructurados.
- Visitas con encuesta, fotografía móvil y GPS opcional mientras el despliegue siga en HTTP.
- Proformas estándar de Odoo vinculadas al cliente/visita.
- Bitácora móvil.
- Resumen e historial de productos proformados.
- Solicitudes auditadas de edición y reasignación.
- Protección de datos durante upgrades mediante Data Guard.

## Versión

`18.0.1.8.1`

Consulte `ACTUALIZACION_18.0.1.8.1.md`, `CHANGELOG_18.0.1.8.1.md` y `VALIDATION_18.0.1.8.1.md`.
