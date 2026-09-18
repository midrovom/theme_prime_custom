# Conedera Catastro Comercial — Odoo 18 Community

Módulo móvil-first que reutiliza `res.partner`, `sale.order` y `sale.order.line` para mantener una ficha única de cliente, bitácora de visitas/proformas y analítica histórica de productos.

## Flujo
1. Nuevo catastro → validar RUC/cédula o nombre.
2. Reutilizar cliente existente si Odoo ya lo conoce.
3. Completar ficha de catastro.
4. Registrar visitas y evidencia fotográfica.
5. Crear proformas estándar de Odoo.
6. Consultar bitácora y productos cotizados desde la misma ficha.

## 18.0.1.5.0
Incluye consolidación por cliente comercial, cámara móvil, data guard de upgrades y corrección de reglas de visibilidad.

## 18.0.1.7.0 — control comercial

Esta versión incorpora jerarquía y control de cambios. El comercial trabaja únicamente con sus Catastros; el supervisor utiliza el liderazgo de Equipos de Ventas de Odoo para ver su equipo; Administrador de Ventas ve todo. Los Catastros registrados quedan protegidos y el comercial requiere una habilitación temporal aprobada para modificar el maestro. El alta empieza con búsqueda predictiva de un `res.partner` existente por RUC/cédula/nombre.
