# Conedera - Catastro Comercial 18.0.1.4.0

Módulo para Odoo 18 Community. Mantiene una ficha única `res.partner` por cliente, bitácora comercial, visitas, proformas y análisis por producto.

## Flujo de alta
1. **Nuevo catastro**.
2. Ingresar RUC/cédula (preferido) o nombre.
3. Validar.
4. Si existe: se muestran sus datos y se abre la misma ficha para completar el catastro.
5. Si no existe: se habilita la creación.

La comparación de RUC/cédula normaliza espacios, puntos y guiones para reducir duplicados.

## Bitácora móvil
La pestaña Bitácora usa una línea de tiempo Kanban de solo lectura que combina:
- visitas comerciales;
- proformas/cotizaciones.

Cada tarjeta abre el registro original.

## Productos proformados
Desde la ficha del cliente se resume por producto:
- cantidad proformada;
- número de proformas;
- importe proformado;
- precio promedio neto ponderado por cantidad;
- precio mínimo/máximo neto;
- última fecha.

Al pulsar el producto se abre el detalle por fecha, de más reciente a más antigua.
Las proformas canceladas no se incluyen.

La ficha estándar del producto muestra, para la compañía activa y convertidos a su moneda:
- cantidad proformada;
- importe proformado;
- precio promedio proformado;
- última proforma;
- botón al historial.
