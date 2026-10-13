# Cambios — versión 18.0.2.0.0

- Separación de funciones: solicitante, aprobador, Tesorería y Cobros a proveedores.
- Restricción para impedir la autoaprobación por parte de quien solicitó o tiene asignado el requerimiento como vendedor.
- Bandejas independientes para aprobación, pagos al beneficiario y cobro a proveedores.
- Las líneas usan No. de producto y Program type manuales; eliminado el acoplamiento al catálogo `product.product` y la dependencia `product`.
- La persona solicitante y el vendedor responsable se manejan por separado.
- El método transferencia/cruce se captura por movimiento y por vendedor.
- Cada movimiento tiene referencia y evidencia propia; las evidencias generales siguen disponibles.
- Cobros parciales quedan en Pendiente de cobro; se cierra cuando se registra el total esperado.
- Traducciones es/es_EC actualizadas y reporte adaptado a los campos manuales.
- Se mantiene el proceso contable manual: no se crean facturas, pagos ni conciliaciones desde este módulo.
- Migración para actualizar bases de la versión 18.0.1: conserva números/códigos anteriores como texto, elimina columnas heredadas y limpia los grupos implícitos para mantener separadas las responsabilidades.
