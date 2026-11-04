# Catastro PWA 18.0.1.5.8 — stock por ubicación, Loyalty y venta de tienda

## Compatibilidad y componentes

**No desinstalar el módulo base** `conedera_odoo_census` ni borrar la PWA existente o IndexedDB del navegador.

1. `conedera_odoo_census_mobile` versión **18.0.1.5.8**, complemento principal (actualización sobre 1.5.7).
2. `catastro_pwa_loyalty_bridge` versión **18.0.1.0.0**, complemento adicional, requiere `sale_loyalty`. Se instala cuando haya promociones Loyalty; es imprescindible si se combinan promociones con recargos por forma de pago. Evita que el recargo participe en el umbral o descuento de los programas Loyalty nativos.

Ambos usan los modelos oficiales de Ventas/Inventario; la PWA NO introduce otro `negotiable_price` ni modifica `price_unit` de las líneas de productos. Crea únicamente un registro nuevo de **condición de pago** y una línea de servicio separada de **recargo**.

## 1. Corrección de stock

**Antes (1.5.7):** una lectura de `product.qty_available` con `warehouse` en el contexto. Según ubicaciones, reglas y personalizaciones, podía dar cero mientras Inventario mostraba quants positivos.

**Ahora (1.5.8):** saldo físico sumado mediante `stock.quant` por variante `product.product`, compañía activa y ubicaciones de uso *internal* debajo de `stock.warehouse.view_location_id`. Se usa la misma cifra en catálogo, cantidades y validación inmediatamente anterior a `sale.order.create`. No suma otras bodegas; no descuenta reservas y no confirma la venta. La lectura de quants usa elevación de permisos exclusivamente para el producto, la compañía y el almacén que el usuario tiene derecho a consultar.

En la PWA, busque el producto, seleccione bodega y pulse **Comprobar stock de la bodega**. Se verá el saldo por bodega, el total de compañía y el nombre de la ubicación raíz. Si sigue apareciendo cero, inspeccione en Odoo: (a) ID de variante exacto, (b) la compañía, (c) la ubicación de los quants, (d) si la ubicación es interna y descendiente de la ubicación raíz de la bodega. No es correcto sumar existencias de otras bodegas para permitir esa proforma.

## 2. Loyalty (módulo nativo de Odoo 18)

- Activar promociones y Loyalty en Ventas e instalar `sale_loyalty` junto con `catastro_pwa_loyalty_bridge`.
- El cotizador permite introducir un código de promoción en el borrador. En la ficha de la proforma se consultan y aplican **recompensas reclamables reales** calculadas por Odoo: normas del programa, validez, productos, cliente y recompensas.
- El complemento puente utiliza el hook de Odoo 18 `_get_no_effect_on_threshold_lines` para excluir la línea de recargo del cálculo de umbrales/descuentos Loyalty.
- Las recompensas pueden ser descuentos por producto, globales o regalos, dependiendo exclusivamente de la **configuración del programa nativo**. Para aplicar solo descuentos a productos, crear recompensas de descuento con aplicabilidad **Productos específicos** en Odoo.
- En la PWA se crean **borradores**; usar confirmación nativa de Odoo para ejecutar los procesos de venta y contabilidad. La integración de programas personalizados adicionales depende de esos módulos.

## 3. Condiciones de pago y recargos

Administrador: **Catastro → Configuración → Condiciones de pago PWA**.

Crear una opción distinta para cada condición comercial, p. ej. "Efectivo", "Tarjeta", "Tarjeta 3 meses", "Tarjeta 6 meses". Definir **el porcentaje real** de recargo en cada opción, sin porcentajes de ejemplo codificados. Opcionalmente vincular el **plazo de pago Odoo** (`account.payment.term`). Las opciones con recargo > 0 requieren un **producto vendible de tipo servicio** de la misma compañía, con impuestos y cuenta contable configurados por Contabilidad.

El porcentaje se calcula sobre el **subtotal después de Loyalty y antes de impuestos** (sin incluir otra línea de recargo), mediante una línea dedicada. Se trata de una **condición comercial**, no de un cobro bancario o confirmación de un pago con tarjeta. El pago debe registrarse por el circuito existente de Odoo.

Si `sale_loyalty` está instalado y la forma de pago incluye recargo > 0, la PWA **bloquea el guardado** hasta instalar `catastro_pwa_loyalty_bridge`, para impedir promociones con base incorrecta.

## 4. Perfiles de usuario y consumidor final

- Grupo **Catastro PWA: negociar precios** (`group_quote_negotiator`): puede usar `sale.order.line.negotiable_price` existente y seleccionar lista de precios. Se valida de nuevo al guardar; el resto de usuarios no puede enviar negociaciones aunque manipule el navegador.
- Grupo **Catastro PWA: cotizador de tienda** (`group_quote_retail`): permite cotizar un cliente *Consumidor Final* configurado, sin catastro previo, sin privilegio implícito de negociación. También requiere permisos nativos para crear cotizaciones en Ventas.
- Administrador: **Catastro → Configuración → Consumidor final por empresa**. Seleccionar un `res.partner` existente usado para el consumidor final en esa compañía.
- El empleado solo de tienda entra desde **Cotizador de tienda** o `/catastro/app`. No descarga catálogos de catastros ajenos. Si su grupo de Ventas permite modificación de precios en el **formulario Odoo nativo**, esa restricción debe configurarse también en sus personalizaciones de Ventas; la protección PWA no modifica las vistas de módulos externos.

## Actualización (staging antes de producción)

1. Hacer backup de base de datos y carpeta de complementos; sincronizar operaciones offline si hay alguna.
2. Sustituir únicamente `conedera_odoo_census_mobile` por la nueva carpeta, conservando su nombre técnico.
3. Colocar `catastro_pwa_loyalty_bridge` en `addons_path` si `sale_loyalty` está instalado y se desean promociones/recargos conjuntos. Actualizar lista de aplicaciones e instalar/actualizar también el puente.
4. Reiniciar Odoo y actualizar el módulo principal; los XML nuevos crean grupos, controles y opciones administrativas. No desinstalar los módulos existentes.
5. Recargar `/catastro/app?version=18.0.1.5.8` (en HTTPS) sin eliminar IndexedDB ni datos del sitio.
6. Configurar opciones de pago y la cuenta/servicio de recargo; otorgar grupos de Tienda y Negociación solo a usuarios autorizados.

## Pruebas de aceptación pendientes en Odoo real

- Bodega A tiene stock, Bodega B no: el diagnóstico muestra las cifras correctas por variante; el catálogo solo presenta productos con stock positivo en A. Carga simultánea de existencias y reservados: usar **a mano físico**, no cantidad libre ni pronosticada.
- Cotizar más de lo existente en la misma bodega: Odoo rechaza antes de crear `sale.order`.
- Un empleado de tienda no ve `negotiable_price` ni puede enviar ese valor por RPC; el personal autorizado sí.
- Consumidor Final puede crear proforma con lista del cliente, sin `census_originated=True` y sin visita.
- Odoo `sale_loyalty` descuenta un producto y conserva un recargo financiero independiente. Simular cupón, descuento específico y recargo sobre subtotal ya descontado.
- Confirmar que el impuesto del recargo se calcula según el servicio y la posición fiscal; verificar totales en Odoo antes de confirmar.
- Usuario de otra compañía no puede usar bodegas ni condiciones de pago ajenas.
- La PWA anterior conserva operaciones offline pendientes; probar sincronización de una cotización antigua sin condición de pago.

### Limitación de pruebas

Se verificaron sintaxis Python/JavaScript, parseo XML, integridad de los ZIP y pruebas controladas del DOM en 390/1280 píxeles y de agregación de quants por almacén. **No se ejecutó una instalación ni cálculos reales de Loyalty/Contabilidad con su servidor PostgreSQL o sus personalizaciones**. Es imprescindible ensayar primero en una base clonada.
