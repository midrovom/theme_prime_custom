# Descuento Loyalty negociable por producto (Odoo 18)

Módulo independiente. **No modifica** `sale_loyalty`, `catastro_pwa_loyalty_bridge`, el puente Radis ni `stock_api_assing`.

## Dependencias
- `conedera_odoo_census_mobile` **18.0.1.5.29** o más reciente.
- `catastro_pwa_loyalty_bridge` **18.0.1.0.2** (promociones porcentuales por producto).
- Odoo `sale_loyalty` (dependencia transitiva).
- Se mantiene `catastro_pwa_loyalty_warehouse` si ya está instalado: las bodegas restringen la elegibilidad desde el motor original.

## Uso

Cuando Odoo devuelve una promoción porcentual compatible del 15 %, el usuario puede ofrecer 0–15 %, por ejemplo 8 %, en la tarjeta o revisión. El catálogo consulta el **precio con impuestos a Odoo** para el descuento ofrecido, en vez de hacer cálculos de IVA en el navegador. En Odoo se guarda el descuento efectivo en `sale.order.line.discount` junto con el valor ofrecido y la recompensa de origen para auditoría. `negotiable_price` y `price_unit` no se cambian manualmente por este módulo.

- El máximo proviene del `loyalty.reward.discount` en el servidor y la elegibilidad la sigue determinando `catastro_pwa_loyalty_bridge` (cliente, cantidades, compañía, fechas, bodega, etc.).
- El porcentaje propuesto se valida otra vez en el **servidor**, al guardar o editar un borrador.
- Se combinan multiplicativamente descuentos anteriores si existieran: un descuento base del 10 % con promoción ofrecida del 8 % resulta en un descuento efectivo del 17,2 %, no 18 %. El nuevo campo almacena el **8 % ofrecido**, no el 17,2 % combinado.
- Si se pierde la elegibilidad al recalcular, la promoción se elimina y el descuento base se restaura mediante el puente Loyalty original.
- Si no se indica porcentaje se sigue utilizando el máximo de la promoción como anteriormente.
- El perfil Tienda puede ofrecer menos del máximo sin permiso para `negotiable_price`.

## Limitaciones y validaciones

El nuevo comportamiento se aplica a las promociones automáticas de descuento porcentual *por productos específicos* que ya admite el puente. No convierte cupones, puntos, dinero, regalos o recompensas globales. Las proformas con líneas Reward especiales siguen sujetas a las restricciones anteriores de Radis.

**Antes de instalar en producción** probar: 1) oferta 15 %, elegir 8 % y guardar; 2) cambio de cantidad/bodega que vuelve la oferta inelegible; 3) edición y duplicación de borradores; 4) listas de precios, impuestos, recargo por forma de pago y Loyalty por bodega; 5) XML de factura Ecuador / SRI; 6) envío Radis de `discount_percent` efectivo con el ERP receptor.

No se ha validado con el PostgreSQL ni con las personalizaciones exactas del servidor de producción.
