# Transcash Guías API 18.0.2.32.0 — UX móvil

## Alcance
Se actualiza exclusivamente `transcash_guias_api` y sus recursos de interfaz. El módulo principal
`logistica_transcash` y los procesos de ruta, embarque, aceptación, entrega, finanzas, API y permisos no cambian.

## Evidencia de carga por hoja de ruta
En la PWA de Logística, la pantalla de preparación del embarque presenta tres opciones claramente
identificadas (tomar foto, grabar video, elegir archivo). Ahora el operador revisa el nombre y el tamaño
antes de pulsar **Enviar evidencia**. Se elimina `onchange="this.form.requestSubmit()"`, que enviaba
un archivo en cuanto se elegía. Se conservan la ruta POST, CSRF y `name="archivo"`, además de los
límites reales del servidor: fotos 20 MB; video 75 MB. Si JavaScript está deshabilitado, el envío por
POST sigue disponible con la validación nativa `required`.

## Evidencia de guía / rotura
En el modal que utilizan chofer y destinatario se refuerzan las instrucciones y se aumenta el área
pulsable de cámara, galería, cierre y confirmación. El modal ocupa toda la pantalla del teléfono y
mantiene los botones de confirmación visibles con scroll. El guardado offline existente de
`mobile.js` y `offline-app.js` no se reemplaza ni se intercepta.

## Base de experiencia app móvil
- Una columna para tarjetas de embarque y rutas en móviles.
- Sin desbordamiento previsto en formularios, tarjetas y multimedia.
- Campos de al menos 16 px para reducir zoom automático en iOS.
- Áreas táctiles grandes, navegación horizontal desplazable y márgenes de área segura.
- Modal adaptable a teclado / 100dvh, respeto a accesibilidad, foco visible y movimiento reducido.

## Comprobación manual requerida en servidor real
1. Actualizar SOLO `transcash_guias_api`, recargar navegador y PWA instalada.
2. A 320/360/390/430 px de ancho, abrir Logística → Embarques → Preparación → Paso 3.
   Verificar que cada opción de captura y su botón de envío caben en una sola columna.
3. Elegir foto: NO debe subirse inmediatamente. Debe verse nombre/tamaño y habilitarse Enviar.
   Repetir con video y galería; esperar confirmación del servidor y nueva evidencia en la ruta.
4. Probar archivo de más de 20 MB de foto o 75 MB de video; debe informar sin enviar.
5. Entrar como chofer/destinatario, abrir el modal de evidencia y la sección de roturas,
   probar cámara, galería, guardar, volver con el navegador y la sincronización sin conexión.
6. Verificar que rutas, viajes, guías, finanzas y todas las cuentas siguen accesibles según rol.

Validación local: Python AST, lxml XML, `node --check`, XPath real y ZIP.
No fue posible la prueba automática con navegador Chromium en este entorno (`ERR_BLOCKED_BY_ADMINISTRATOR`)
y no contamos con servidor Odoo para verificar el comportamiento con datos reales.
