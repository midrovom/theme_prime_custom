# Catastro PWA 18.0.1.5.6 — precio negociado personalizado

## Cambio puntual

La PWA envía el precio negociado de cada producto al campo existente `sale.order.line.negotiable_price`.
No define ningún campo nuevo y **ya no sobrescribe `sale.order.line.price_unit`**. Odoo y sus módulos
personalizados determinan el precio efectivo, descuentos, impuestos y total del borrador.

- La línea se crea con `negotiable_price` cuando el comercial ingresa un valor, incluyendo cero.
- Cuando el comercial deja el valor vacío, se omite ese campo y se aplican los valores nativos.
- Si no existe `negotiable_price` en `sale.order.line`, el guardado con precio negociado falla
  con un mensaje explícito, sin crear un borrador parcial.
- Si el campo no admite escritura, también se rechaza antes del guardado.
- Se mantiene compatibilidad con cotizaciones offline **pendientes** de versiones 1.5.5 y anteriores,
  cuyos datos utilizaban la clave `negotiated_price`; se convierte solo al campo existente.
- El detalle de cotización muestra `negotiable_price` cuando existe.

## Compatibilidad

No se modificaron el módulo base Catastro, identificadores, permisos, rutas, ni tablas existentes.
Antes de usar en producción confirme que su módulo personalizado define `negotiable_price`
en `sale.order.line` y verifique que sus reglas de precio se ejecutan al crear líneas por ORM.
Si el campo está realmente en `sale.order` (cabecera) o su lógica depende exclusivamente de
`@api.onchange`, será necesario adaptar el módulo personalizado; no se debe suponer su semántica.

## Verificación manual sugerida

1. Cotizar un producto con lista de precios automática y precio negociado vacío.
2. Cotizar otro con precio negociado no cero, y comprobar `negotiable_price` en Ventas.
3. Cotizar con precio negociado igual a 0 y confirmar que se conserva.
4. Verificar que la personalización determina `price_unit`, descuentos, impuestos y total.
5. Probar creación con varios productos y sincronización de pendientes previos.
