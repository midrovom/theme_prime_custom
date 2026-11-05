# Catastro - App de Campo 18.0.1.5.14

## Correcciones

1. **Versión**. La 1.5.13 exponía erróneamente `pwa_server_version = 18.0.1.5.12` aunque el manifiesto y los archivos de navegador ya eran 1.5.13. El controlador, el manifiesto, `app.js`, las referencias a recursos y la caché del Service Worker coinciden ahora en 18.0.1.5.14. Si después de actualizar el servidor todavía responde una versión anterior, hay que comprobar el reinicio de todos los procesos y la ruta activa de `addons_path`.
2. **Editar cotizaciones borrador**. Desde el detalle de una cotización en estado `draft`, el botón **Editar borrador** permite cambiar cantidades, añadir o quitar productos y modificar la condición de pago, sin crear un pedido nuevo. La actualización es ONLINE; se hace por RPC sobre el mismo `sale.order`, validando estado, permisos, compañía, cliente, bodega, stock físico y fecha de modificación. Se protegen las recompensas Loyalty, las líneas especiales y el `negotiable_price` personalizado. No se reconstruye la proforma desde cero. En caso de cambio concurrente, Odoo rechaza el guardado. En casos especiales (SKU repetidos, campos personalizados), completar la edición desde el formulario nativo de Odoo.
3. **40 productos**. Con la búsqueda vacía el catálogo prioriza las últimas 40 referencias cotizadas para ese cliente con stock disponible en la bodega; si no alcanza, completa hasta 40 con productos disponibles. La búsqueda por nombre/SKU sigue operando sobre productos vendibles fuera de esas 40 referencias. El resumen de productos ya cotizados en catastros se acota a 40 referencias recientes por cliente para reducir datos transferidos.

## Instalación segura

- Respaldar base de datos y código. Sincronizar primero las operaciones offline pendientes.
- Reemplazar la carpeta existente `conedera_odoo_census_mobile` (NO desinstalar el módulo).
- Reiniciar el **servicio Odoo completo**, incluidos todos los workers y procesos que atienden el servidor. Actualizar la lista de aplicaciones y **actualizar el módulo** `conedera_odoo_census_mobile` en la base correcta (o ejecutar `-u conedera_odoo_census_mobile -d NOMBRE_BD --stop-after-init` en la configuración de despliegue correspondiente).
- Abrir `/catastro/app?version=18.0.1.5.14` conectado y verificar que la interfaz y el servidor señalen la misma versión.
- Probar en entorno de homologación con un borrador y una recompensa Loyalty existente. No borrar IndexedDB ni desinstalar la PWA si contiene operaciones sin sincronizar.

## Alcance de verificación

Comprobadas sintaxis Python/JavaScript, archivos XML, compatibilidad de versiones, integridad del ZIP y pruebas visuales de edición en Chromium (360, 390, 768 y 1280 px) con respuestas simuladas. **No se ha instalado ni ejecutado la actualización contra el PostgreSQL / Odoo de producción**. Validar en servidor real antes de uso operativo.
