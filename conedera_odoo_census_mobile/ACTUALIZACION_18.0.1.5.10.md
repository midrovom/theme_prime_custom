# Catastro PWA 18.0.1.5.10 — corrección de cotizador y recargo en precios por línea

## Cambios

- Maquetación robusta para descripciones y códigos extensos en móvil y escritorio; cada producto tiene foto y datos en una fila, controles en otra.
- Condiciones de pago al principio de la cotización, antes del catálogo. Se muestran solo las configuradas en Catastro → Configuración → Condiciones de pago PWA, por empresa. No se incluyen porcentajes predeterminados.
- Recargo aplicado al `price_unit` de **cada producto** tras computar precios de lista y `negotiable_price` y solicitar los descuentos Loyalty al servidor; no se crea una línea de servicio.
- Se registran en `sale.order.line`: `catastro_payment_base_price_unit`, `catastro_payment_surcharge_percent`, `catastro_payment_surcharge_unit_amount` y `catastro_payment_surcharge_applied`.
- El detalle de proforma muestra precio base, porcentaje de recargo, valor unitario del recargo y precio final. La PWA presenta estimaciones antes de impuestos; los importes definitivos los calcula Odoo.
- El puente Loyalty anterior es compatible y puede permanecer instalado, pero ya no es requisito para calcular el nuevo recargo por producto. En las llamadas de la PWA se restaura primero el precio base, se calcula Loyalty y luego se reaplica el recargo.
- `negotiable_price` es el campo personalizado existente, no se crea ni reemplaza. Solo es editable por el grupo negociador.
- Los descuentos se aplican mediante el motor nativo de Odoo. Para cambios desde formularios nativos u otros módulos debe probarse la recomputación según los módulos personalizados instalados.

## Instalación

1. Respalde base de datos y addons. Haga la actualización primero en pruebas.
2. Reemplace solo `conedera_odoo_census_mobile`, sin desinstalarlo; reinicie Odoo y actualice el módulo (-u conedera_odoo_census_mobile).
3. Si usa `sale_loyalty`, mantenga instalado `catastro_pwa_loyalty_bridge` y compruebe descuentos y recargos reales en pruebas.
4. Configure las condiciones de pago por empresa y sus porcentajes, además del plazo de pago nativo cuando corresponda. Ya NO es necesario asignar producto de recargo.
5. Abra `/catastro/app?version=18.0.1.5.10` y revise una proforma real por cada condición de pago.

## Límites

- El stock sigue siendo informativo y no reserva existencia. Se sigue validando por bodega al guardar.
- Las promociones Loyalty dependen de `sale_loyalty` y sus reglas; no se inventan descuentos. Las reglas específicas de otras personalizaciones deben verificarse en la base real.
- Operaciones offline pendientes conservan el `payment_option_id` y el servidor aplicará su porcentaje vigente al sincronizar. Si cambió el porcentaje desde el registro offline, conviene revisar el borrador antes de confirmar.
- En borradores antiguos de la 1.5.8/1.5.9 con recargo como servicio, se migra al nuevo esquema cuando se recalcula el recargo, sin modificar cotizaciones ya confirmadas.
