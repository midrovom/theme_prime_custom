# stock_api_assing – Odoo 18.0.2.0.0

Migrado desde el ZIP original de Odoo 16 (`stock_api_assing(1).zip`).
Se mantiene el nombre técnico, modelos, campos anteriores y XML IDs activos.
Requiere `api_administrator` compatible con Odoo 18 (modelo `api.administrator`,
campos name, company_id, type, status, is_stock_update, url, end_point,
user_id, password, warehouse_id, price_list_id y vista view_api_adminitrator_form).
La dependencia no se incluye en el ZIP y no se ha modificado Balance.

## Actualización
1. Respaldar base y filestore y probar en una copia de la base. Desactivar temporalmente los cron de stock antes de la primera prueba.
2. Sustituir la carpeta stock_api_assing completa (no desinstalar), reiniciar y actualizar el módulo.
3. Revisar las API GET activas, empresa, bodega y lista de precios. Las dos acciones planificadas originales conservan sus XML IDs y sus parámetros existentes mediante noupdate. En instalaciones nuevas se crean para compañías 1 y 2 cada 30 minutos; comprobar los IDs reales. Las instalaciones existentes pueden requerir ajustar manualmente el cron de acuerdo con su configuración.
4. Revisar que los productos existentes tengan Sincronizado con API, referencia interna y Rastrear inventario. Ejecutar manualmente la sincronización y revisar el historial. La acción manual procesa las API activas de la empresa, igual que el original.
5. Activar los cron cuando el resultado sea correcto.

## Decisiones de compatibilidad
- Productos almacenables en Odoo 18: type=consu, is_storable=True.
- Ajuste de inventario ORM (stock.quant.inventory_quantity + action_apply_inventory), solo si cambia la cantidad. Esto puede crear movimientos de inventario y, según la configuración de valoración, asientos contables. No reemplaza conteos manuales pendientes, lotes/series, paquetes o propietarios; esos casos aparecen como fallidos.
- Stock es una cantidad absoluta de la ubicación principal de cada bodega configurada, tal como en el contrato original. No interpreta el arreglo Bodegas. Configurar una API por bodega si los saldos son diferentes. No se modifican productos no marcados ni archivados.
- Por seguridad, la puesta a cero de productos ausentes es opcional por API y está desactivada inicialmente. Solo activarla para una respuesta completa de la bodega, nunca para una API paginada/parcial. Se omite si falla algún producto. El campo histórico check_update se conserva para compatibilidad pero ya no controla el reseteo.
- El historial detalla recibidos, insertados, actualizados (existentes procesados, aunque no cambien), omitidos, fallidos, ajustes y ausentes puestos a cero. Los errores de un artículo se aíslan mediante savepoints, pero una interrupción del proceso antes del commit final todavía puede revertir la transacción.
- Se conserva la exportación a Radis y la selección de productos por bodega. Se sustituye el widget JavaScript de Odoo 16 por la selección múltiple estándar de Odoo 18; los precios negociables usan el motor de impuestos de la nueva versión. Se mantiene el estado async.
- No se activa automáticamente el módulo en nuevas instalaciones. No se ejecuta automáticamente el método histórico que publica productos.

## Validación
Validación estática de Python, XML, manifiesto y archivos referenciados. Se revisaron las vistas y métodos nativos de la rama 18.0 de Odoo. No se dispone de instancia Odoo/PostgreSQL con la dependencia personalizada ni de credenciales de la API, por lo que es necesario probar la instalación, sincronización y cotizaciones en una copia antes de producción.
