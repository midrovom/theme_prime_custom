# Catastro PWA 18.0.1.5.29 — Loyalty negociable (porcentaje hasta el máximo)

- En cada promoción porcentual de producto, campo **Descuento a ofrecer** de 0 al máximo configurado en Loyalty.
- Actualización del precio con impuestos mediante vista previa de **Odoo** después de cambiar el descuento.
- Tanto Tienda como Campo pueden ofrecer un porcentaje inferior sin cambiar `negotiable_price` ni precios manuales.
- En el guardado y edición se envía `promo_offered_percent` separado de `promo_reward_id`.
- La interfaz solo habilita esta función si está instalado **catastro_pwa_loyalty_flexible 18.0.1.0.0**, complemento que hereda la lógica existente `catastro_pwa_loyalty_bridge`.
- Mantiene las versiones anteriores de PWA/cola offline, Radis, perfiles, rutas, accesos y comentarios.
- Requiere actualizar Odoo completo y luego el complemento, no solo recargar el navegador.

Pruebas mínimas obligatorias en servidor: oferta elegible con 15 % máximo → 8 % guardado, 0 %, 15 %, rechazo a 16 %, cambio de bodega que quita promoción, edición del borrador y facturación tributaria.
