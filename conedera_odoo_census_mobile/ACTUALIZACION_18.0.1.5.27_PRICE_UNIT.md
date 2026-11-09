# Catastro PWA 18.0.1.5.27 — Corrección de price_unit NULL

## Incidencia

La sincronización de una cotización podía generar `psycopg2.errors.NotNullViolation`
por insertar líneas `sale.order.line` sin `price_unit`, cuando un módulo de
Ventas no ejecutaba el cálculo diferido antes de la inserción.

## Corrección

- Inicializar `price_unit` **en el servidor**, antes de crear las líneas de
  una cotización y antes de agregar nuevos productos a un borrador.
- Obtener el importe de la lista de precios nativa del cliente y de la
  conversión impositiva nativa de Odoo, usando las mismas funciones que el
  catálogo. Se respeta la moneda y posición fiscal.
- Conservar `negotiable_price`, Loyalty, porcentaje de recargo por forma de
  pago, permisos por bodega y API Radis sin cambios.
- Se aceptan precios unitarios de cero cuando la lista devuelve cero;
  valores nulos o no numéricos muestran errores comprensibles.
- La lista de precios de la cotización coincide con la utilizada para
  calcular los precios iniciales de sus líneas.

## Recuperar la operación de la captura

1. Hacer copia de seguridad antes de actualizar.
2. Reemplazar la carpeta `conedera_odoo_census_mobile`, reiniciar todos los
   procesos de Odoo y actualizar el módulo a 18.0.1.5.27.
3. Abrir `/catastro/app?version=18.0.1.5.27` y entrar a Pendientes.
4. Sin borrar IndexedDB, pulsar «Sincronizar ahora» para reintentar la
   operación marcada `error`.
5. Verificar en Odoo el número y los importes de la proforma resultante.

Las operaciones con error permanecen con su UUID; los guardados exitosos
son idempotentes por `conedera.mobile.sync.log.client_uuid`. Un fallo durante
la creación revierte el pedido dentro del savepoint del controlador.

## Pruebas recomendadas en Odoo

- Crear proforma de Consumidor Final con precios normales, cantidades
  diferentes y promo Loyalty válida.
- Editar un borrador agregando una variante nueva.
- Probar precio de lista cero y `negotiable_price` autorizado.
- Verificar `price_unit` real, `discount`, impuesto, recargo y totales.
- Reintentar exactamente la operación de Pendientes; no crear una copia
  manual. Confirmar que solo haya una proforma para el UUID.

Nota: La prueba de Odoo/PostgreSQL y módulos comerciales reales no pudo
realizarse en este entorno; ejecutar primero en staging.
