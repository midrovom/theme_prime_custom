# Logística Transcash V5.3 — Cliente, visor multimedia y flujo guiado

## Funciones

- **Cliente/Destinatario:** acceso con usuario Odoo de tipo **Portal**, asociado al mismo contacto comercial que `destinatario_id`. Existe grupo opcional **Cliente / Destinatario - WebApp (Portal)** para identificar la cuenta sin darle acceso al backend. La comprobación real de permisos se hace por guía y usuario; el grupo por sí solo no permite ver otras guías.
- **Consultar:** `/transcash/guias` → solo guías de su destinatario. Ve datos, productos, multimedia de carga, ruta, descarga y eventos públicos para cliente. **No ve otros destinatarios ni todas las guías del embarque.**
- **Recepción:** solo cuando llega a destino, puede adjuntar fotos/videos, registrar novedades y roturas por SKU. En `revision` puede aprobar u objetar evidencias del chofer, y confirmar la entrega física con nombre/observaciones. La aceptación de la carga en bodega sigue siendo exclusiva de Bodega: el cliente acepta la **recepción en destino**.
- **Backoffice:** botón **Ver fotos y videos** en la ficha de guía, galería privada que reproduce video y presenta imágenes sin descargar. En la ficha de Evidencia, vista previa multimedia nativa y botón **Ver foto / reproducir video**. El control de empresa/grupo se verifica en el servidor. Los archivos siguen privados. Algunos formatos MOV/HEIC requieren codecs que no traen todos los navegadores; para reproducción universal se recomienda MP4 (H.264) y JPG/PNG.
- **Chofer:** nueva sección **¿Qué hacemos ahora?** con acciones contextuales y grandes: iniciar carga, evidencia, finalizar carga, marcar embarque completo, confirmar llegada, evidencia de descarga, novedades y roturas. Un panel adicional en el embarque lleva a la primera guía pendiente.

## Actualización desde V5.2 en VPS

1. Respaldar base de datos y filestore; comprobar que no queden evidencias offline por sincronizar en los teléfonos.
2. Sustituir carpeta `logistica_transcash` existente por la nueva. No desinstalar.
3. Reiniciar Odoo y **Actualizar** el módulo desde Aplicaciones (es imprescindible actualizar las vistas y el XML de seguridad).
4. Recargar con Ctrl+F5 y abrir la PWA con señal para recibir el JS/CSS nuevo.
5. Abrir `Logística Transcash > Guías`, seleccionar una guía con evidencias y pulsar **Ver fotos y videos**. Abrir una evidencia y comprobar el widget inline.
6. Crear un contacto cliente, conceder **Portal**, comprobar que el `destinatario_id` de la guía coincide con su empresa y probar en una ventana privada `/transcash/guias`.

## Pruebas recomendadas

- Chofer, cliente y operador interno ven solo los datos previstos para su perfil.
- Cliente no puede abrir `/transcash/embarques` ni aceptar una evidencia de carga.
- Cliente sí puede adjuntar evidencia de recepción y novedades en `destino` / `revision` (y después de entrega antes de aprobación total, cuando aplique).
- Foto JPG/PNG y video MP4 se ven **sin descarga** en Odoo; videos se reproducen con HTTP 206 cuando el navegador solicita Range.
- Las credenciales privadas, la tarifa y las guías de otros destinatarios no se exponen.
- Evidencias offline pendientes se sincronizan antes de cerrar definitivamente carga o recepción.

## Estado de validación

Revisión estática de Python, JS, XML, estructura y ZIP. Las pruebas de Odoo no se ejecutan hasta instalar el módulo en una base real de Odoo 18. Ejecutar el suite con `--test-enable` en staging antes de producción.
