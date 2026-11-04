# Catastro PWA 18.0.1.5.2 — Reparación del arranque

## Diagnóstico confirmado en el código de 18.0.1.5.1

- `init()` esperaba `indexedDB.open()` antes de dibujar la pantalla. Si otra pestaña mantiene la versión anterior de la base, el navegador puede disparar `onblocked` y la promesa anterior esperaba indefinidamente: se mostraba "Cargando…".
- Las llamadas `fetch` a Odoo no tenían timeout y podían mantener "Sincronizando…" sin salida.
- Si `app.js` no cargaba por una caché desactualizada o error de recursos, no había una vigilancia independiente que mostrase instrucciones de recuperación.
- El Service Worker podía almacenar una navegación autenticada sin validar si la respuesta era una redirección.

## Cambios

1. Límite de 9 s al abrir IndexedDB y mensaje específico para base bloqueada; `onblocked` detectado. No se borra ni migra de forma destructiva el almacenamiento.
2. Pantalla independiente `boot_guard.js`: si el módulo JS falla o no completa el inicio en 13 s, muestra acciones Reintentar, Reparar caché de interfaz y Abrir Odoo. La reparación elimina SOLO los archivos CacheStorage de Catastro y desregistra SOLO los SW del ámbito `/catastro/`; **NO borra IndexedDB ni las operaciones pendientes**. Requiere estar en línea.
3. Peticiones a Odoo con límite de espera, verificación de que devuelven JSON y explicación de fallo de sesión/red. Sin duplicar operaciones: el servidor mantiene idempotencia mediante `client_uuid`.
4. Service Worker v8: solicita recursos frescos, no almacena redirecciones, activa solo si CSS/JS esenciales están disponibles, mantiene acceso offline a los recursos descargados.
5. Render local inmediatamente después de abrir IndexedDB, antes de descargar datos o registrar Service Worker.
6. Conserva botón Cotizar, navegación independiente `/catastro/app`, catastro, visitas, protección, solicitudes, offline, cola y cotizaciones. No modifica el módulo base.

## Despliegue

1. Copiar de seguridad del servidor y **sincronizar previamente los pendientes del dispositivo si la versión anterior permite abrir**. No desinstalar los módulos. Si hay datos pendientes, no usar "Borrar datos del sitio" o borrar IndexedDB.
2. Sustituir solo la carpeta `conedera_odoo_census_mobile`, reiniciar Odoo y actualizar módulo a 18.0.1.5.2.
3. Con Internet y sesión activa, abrir `/catastro/app?version=18.0.1.5.2`. Cerrar otras pestañas PWA antiguas antes de la primera carga.
4. Si aparece la pantalla de recuperación, pulsar Reintentar; después Reparar caché de interfaz solo con conexión. Si la base está bloqueada, cerrar otras ventanas de Catastro y reintentar.
5. Validar usuario, empresa y operaciones pendientes; después Cotizar, Guardar borrador, Finalizar y proteger y Visitas.

## Limitaciones

Pruebas locales con API simulada no equivalen a instalarlo sobre la base real. Para localizar la causa exacta en un servidor dado, revisar la consola del navegador (Network/Console) y logs de Odoo. Los campos de cotizaciones personalizados por otros módulos de Ventas siguen requiriendo su código para integrarse dentro de la PWA.
