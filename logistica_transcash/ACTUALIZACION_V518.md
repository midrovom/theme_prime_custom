# TRANSCASH V5.18 — Armado por transporte y bitácora de carga

**Origen:** V5.17. **Odoo:** 18. **Módulo:** `logistica_transcash`.

## Qué se solucionó

- Antes de seleccionar rutas para el embarque, la WebApp obliga a escoger la agrupación real del vehículo (compañía, **empresa transportista, chofer, tipo de vehículo y placa**). No aparecen rutas de otras agrupaciones. El asistente de escritorio Odoo también filtra y limpia las rutas que no coinciden.
- La validación definitiva permanece en el servidor: no permite mezclar vehículos, empresas de transporte, choferes, placas o compañías, aunque se altere el formulario.
- Una vez armado el viaje, su ficha abre un **control de carga por cada hoja de ruta** con tres acciones: **Tomar foto**, **Grabar video** y **Seleccionar archivo**. Los dos primeros botones solicitan al navegador móvil el dispositivo de captura (`capture=environment`), cuando está soportado. En ordenador funciona la selección de archivos.
- Cada fotografía/video genera un registro **independiente e inmutable** con fecha/hora, usuario interno que lo subió, hoja de ruta, embarque, tipo MIME y nombre. Los operadores no pueden eliminar o modificar registros ya cargados; pueden agregar evidencia adicional mientras el viaje siga en preparación.
- La evidencia mínima es **una foto O un video por ruta**, no necesariamente video. No se puede **liberar al chofer** hasta documentar todas las rutas; el botón se deshabilita y el modelo vuelve a comprobarlo en el servidor.
- El chofer, desde su PWA, puede revisar las fotos y reproducir los videos de carga antes de aceptar el embarque. Solo Logística documenta la carga. El chofer sigue registrando en destino el nombre de receptor, la firma y la evidencia de entrega según versiones anteriores.
- Los videos históricos de carga y sus metadatos permanecen intactos. No se recalculan tarifas, no se modifican guías ni liquidaciones y sigue existiendo **un único importe de flete por embarque**.

## Secuencia de trabajo del operador

1. Ingresar con **Operador de Logística** o **Jefe de Logística** a `/transcash/operacion`.
2. Crear y confirmar una o varias hojas de ruta, asignando **chofer, empresa transportista, tipo y placa** y las guías de cada destino.
3. Elegir **Armar embarque**. Escoger la agrupación planificada: la lista solo incluye rutas compatibles; seleccionar rutas y el destino de cobro del viaje.
4. En el detalle de embarque, ver qué rutas tienen evidencia pendiente. Por **cada ruta**, usar cámara de foto, grabadora de video o selección de archivo. La subida requiere conexión con el servidor.
5. Una vez completadas todas, pulsar **Enviar embarque al chofer para aceptación**. Si una ruta no tiene archivo el servidor no permite el cambio de estado.
6. El chofer consulta la evidencia, acepta e inicia traslado; continúa entrega y recepción posteriores.

**Límites:** fotografía hasta 20 MB; video hasta 75 MB. Se admite JPG, PNG, WebP, HEIC/HEIF, MP4, WebM y MOV (la reproducción HEIC/MOV depende del navegador). Los límites también deben permitirse en el proxy: revisar `client_max_body_size` de Nginx, tiempos de espera y capacidad de PostgreSQL/filestore. No borres la caché PWA con evidencias offline aún pendientes de sincronización.

## Visibilidad y acceso

| Perfil | Preparar ruta | Armar embarque | Subir foto/video de carga | Consultar evidencia de carga | Aceptar viaje | Entrega en destino |
|---|---|---|---|---|---|---|
| Operador Logística | Sí | Sí | Sí | Sí | No | No |
| Jefe Logística | Sí | Sí | Sí | Sí | No | No |
| Chofer Portal asignado | No | No | No | Sí | Sí | Sí |
| Cliente destinatario | No | No | No | No, solo evidencias de sus guías autorizadas | No | Confirmar/objetar recepción |
| Proveedor transportista | No | No | No | Consulta permitida de las rutas propias | No | No |

Los medios se sirven por rutas privadas con comprobación de grupo, conductor/transportista y compañía. Las reglas de escritura no dependen del botón visible.

## Comprobaciones funcionales necesarias en Odoo 18

1. Intentar agrupar dos rutas de **transportistas distintos**: no deben aparecer juntas ni confirmarse forzando RPC.
2. Intentar agrupar dos rutas con **choferes distintos**: deben bloquearse.
3. Intentar agrupar **camión y mula** o distinta placa: deben bloquearse.
4. Crear embarque de 2 rutas, subir solo 1 foto a la primera y pulsar liberar: debe ser imposible.
5. Subir foto desde cámara del celular a la segunda: se habilita liberar. Verificar la bitácora (operador/fecha).
6. Ingresar como chofer asignado, visualizar ambos archivos y aceptar. Ingresar como otro chofer: no debe poder consultarlos.
7. Intentar subir nueva evidencia después de liberar o alterar/eliminar una existente: debe fallar.
8. Asegurar que la tarifa siga siendo una sola para el embarque y que las entregas/pagos funcionen sin cambios.

## Actualización segura

1. Respaldar PostgreSQL, filestore y carpeta del addon V5.17.
2. En una **copia de tu VPS**, reemplazar únicamente `logistica_transcash` por el contenido del ZIP V5.18.
3. Reiniciar Odoo y **Actualizar** el módulo desde Aplicaciones (no desinstalar).
4. Recargar la PWA conectada a Internet; si el navegador conserva la versión anterior usar recarga forzada sin borrar datos offline pendientes.
5. Ejecutar los 8 escenarios y revisar el registro del servicio Odoo si aparece un error.

**Alcance de la validación entregada:** sintaxis de todos los Python/JS, XML, manifest, ACL y pruebas nuevas. No se ha ejecutado el módulo sobre una instancia real de Odoo 18 con tu base; ese paso es indispensable antes de producción.
