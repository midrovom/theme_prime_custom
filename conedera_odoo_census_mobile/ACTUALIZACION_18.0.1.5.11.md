# Catastro - App de Campo 18.0.1.5.11

## Cambio del recargo por forma de pago

- **No se requiere producto de tipo servicio.** El campo histórico
  `catastro.quote.payment.option.surcharge_product_id` sigue existiendo para leer
  configuraciones antiguas, pero NO se muestra, no se valida y no interviene en
  los cálculos. Las condiciones de pago solo requieren nombre, empresa y
  porcentaje (`surcharge_percent`); `payment_term_id` es opcional.
- Cada producto de la cotización utiliza `price_unit = precio_base + recargo`,
  con redondeo en la moneda de la cotización. Se conservan en `sale.order.line`:
  `catastro_payment_base_price_unit` (precio unitario base),
  `catastro_payment_surcharge_percent` (porcentaje exacto),
  `catastro_payment_surcharge_unit_amount` (incremento por unidad) y
  `catastro_payment_surcharge_applied` (indicador). No se crea ningún producto
  ni línea de servicio. `negotiable_price` sigue siendo el campo de otra
  personalización y NO se redefine.
- Aplicar de nuevo el recargo al mismo borrador no lo duplica. Las líneas de
  premio/descuento `sale_loyalty` se excluyen del recargo. Antes de recalcular
  premios se restaura el precio base y luego se aplica de nuevo el recargo.

## Perfiles y Loyalty

- `Catastro PWA: cotizador de tienda`: el cliente Consumidor Final se fija por
  empresa; incluso si el usuario pertenece además a Negociación, las
  cotizaciones de Tienda NO aceptan `negotiable_price` ni listas personalizadas.
- Usuarios sin grupo `Catastro PWA: negociar precios`: no pueden enviar
  `negotiable_price`, precios o descuentos manuales a través de la PWA.
- El uso de promociones/cupones Loyalty NO exige el grupo Negociación; exige
  que el módulo nativo `sale_loyalty` esté instalado, haya programas de Ventas
  aplicables al cliente y que la persona pueda crear y editar cotizaciones.
  Las reglas de Loyalty se verifican en Odoo, no en JavaScript.
- La restricción de perfiles descrita aplica a **la PWA**. Los permisos sobre
  los formularios nativos de Ventas dependen de los módulos de seguridad del
  servidor; este complemento no cambia todos los ACL de `sale.order.line`.

## Importante al actualizar desde 1.5.8 / 1.5.9 / 1.5.10

La pantalla "Configure un producto de tipo servicio para el recargo" pertenece
al código anterior. Si persiste, significa que los archivos antiguos siguen
siendo atendidos (proceso Odoo no reiniciado, módulo sin actualizar, o caché
PWA). El arranque del 1.5.11 incluye un `pwa_server_version` en las capacidades
para advertir cuando la interfaz y el backend no coinciden.

1. Respalde la base y sincronice las operaciones pendientes de la PWA.
2. Sustituya **solo** la carpeta `conedera_odoo_census_mobile` del addons_path;
   verifique que no quede otra copia con el mismo nombre en otro addons_path.
3. Reinicie Odoo y ejecute **Actualizar** en Aplicaciones para instalar campos
   e interfaz nuevos, manteniendo el módulo base sin cambios.
4. Abra `/catastro/app?version=18.0.1.5.11`, actualice la caché de interfaz
   desde la app (sin borrar almacenamiento del sitio, IndexedDB ni la cola).
5. Desde Configuración → Condiciones de pago PWA, cree/edite opciones como
   Efectivo (0 %), Tarjeta (su porcentaje real), 3 meses, 6 meses. **No se
   necesita elegir servicio**. Pruebe con un borrador por perfil antes de
   dar acceso a producción.

## Verificación en Odoo

- Recargo 5 % sobre base 100 y cantidad 2 (ejemplo): `price_unit = 105`,
  `catastro_payment_base_price_unit = 100`,
  `catastro_payment_surcharge_percent = 5`,
  `catastro_payment_surcharge_unit_amount = 5`; subtotal antes de impuestos
  210, salvo otras reglas de descuentos/impuestos.
- Repita `catastro_recompute_surcharge()` y confirme que no aumente a 110,25.
- En Tienda, pruebe cupón aplicable sin el grupo Negociación y confirme que
  `negotiable_price` no es editable y no se envía.
- En el borrador final, compare `price_unit`, el premio Loyalty, los impuestos
  y el total con el formulario nativo de `sale.order`.
- La instalación real debe validarse en un entorno de pruebas de Odoo 18 con
  las personalizaciones comerciales del servidor. Los tests del paquete no
  son una prueba de integración con PostgreSQL y `sale_loyalty` instalado.
