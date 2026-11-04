# Catastro PWA 18.0.1.5.5 — cotización rápida

Actualización del complemento técnico `conedera_odoo_census_mobile` para Odoo 18 Community. **No modifica** los módulos originales ni sus identificadores técnicos. Mantiene el acceso opcional por `/catastro/app` y el escritorio Odoo en `/web`.

## Nuevo catálogo en cada catastro

1. Abrir **Catastro → seleccionar catastro protegido → Crear cotización**.
2. Seleccionar, si se necesita, una lista de precios de Odoo. Por defecto se emplea la que Odoo asigna al cliente (`property_product_pricelist`). Solo se ofrecen listas visibles en la compañía activa.
3. Elegir, de forma opcional, un almacén visible en la compañía para consultar el stock. Sin seleccionar uno, se consulta la cantidad a mano de la compañía; el dato de existencia no reserva unidades.
4. Buscar por nombre o código; visualizar miniatura y abrir fotografía grande, con botones para ampliar o reducir.
5. Seleccionar múltiples productos, asignar la cantidad de cada uno y pulsar **Agregar seleccionados**. También existe **Agregar** individual. Al cambiar cantidades de líneas agregadas, la PWA vuelve a consultar a Odoo el precio por lista para esa cantidad.
6. Introducir un **precio negociado opcional por producto**. Se guarda sobre el campo nativo `sale.order.line.price_unit`, después de crear el pedido con sus cálculos comerciales. Los descuentos automáticos que Odoo aplique sobre esa línea siguen operando, de acuerdo con la configuración nativa; antes de enviar se debe revisar el importe neto.
7. Guardar **cotización en borrador**, nunca confirmarla automáticamente. Odoo calcula definitivamente impuestos, descuentos, precios y total, y ejecuta sus reglas, accesos y módulos heredados.

## Datos expuestos y permisos

- Catálogo: imagen del producto, precio de la lista y moneda aplicable, código, unidad, cantidad a mano.
- Existencias: `qty_available` de producto, con contexto de compañía y almacén. No es `free_qty` ni «disponible para prometer»; no sustituye la reserva de inventario. Si `stock` no está instalado o el usuario carece de permisos, muestra «no disponible», nunca cero ficticio.
- Fotografías: endpoint protegido, exige sesión Odoo, acceso a producto/catastro y aplica compañía. No se deja caché pública.
- Seguridad: no se usa `sudo` en los nuevos servicios ni se permiten almacenes, listas de precios, clientes o productos fuera del alcance del usuario. No se aceptan importes de lista ni impuestos calculados en el navegador. Los precios negociados se validan de nuevo en el servidor.
- Cotizaciones offline: operaciones pendientes conservan los importes de negociación indicados, pero stock y precio lista guardados en el dispositivo son solo referencias; los importes definitivos requieren validación/sincronización Odoo.
- Conservación de datos: no se cambia el esquema IndexedDB ni se borra la cola de pendientes. El cambio de versión de Service Worker solo actualiza los archivos de interfaz.

## Notas de integración

No se conocen todas las extensiones externas de `sale.order` y `sale.order.line` del servidor del cliente. La PWA usa los métodos y permisos nativos de Odoo al crear cotizaciones y modificar precios; **no pretende reproducir todos los campos personalizados de esos módulos en su propia pantalla**. Permanecen disponibles los enlaces al formulario completo de Odoo.

## Pruebas recomendadas antes de producción

1. Cliente con lista de precios estándar y cliente con lista especial; verificar moneda y cantidades mínimas.
2. Cotización con varios productos y cantidades diferentes. Verificar en Odoo el precio, impuestos, descuento, subtotal y total resultantes.
3. Precio negociado en una línea con descuento automático, para acordar si el precio ingresado debe representar precio unitario previo a descuentos o precio neto.
4. Existencias para almacén A frente a almacén B y una compañía distinta; verificar reglas de acceso.
5. Producto con imagen JPG/PNG, sin imagen y servicio sin stock.
6. Apertura celular/escritorio y ampliación de fotografía; actualización de PWA conservando registros offline.
7. Campos personalizados u obligaciones de los otros módulos de Ventas que no están adjuntos.

## Actualización

Respaldar Odoo, sustituir la carpeta `conedera_odoo_census_mobile` sin desinstalarla, reiniciar Odoo, **actualizar el módulo** (`-u conedera_odoo_census_mobile`) y acceder a `/catastro/app?version=18.0.1.5.5`. No borrar datos del navegador si existen operaciones pendientes.
