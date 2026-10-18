# Transcash V5.20 — Galería unificada de evidencias

**Base:** módulo completo V5.19 para Odoo 18. **Versión de salida:** `18.0.5.20.0`.

## Qué cambia

La ficha del **embarque/viaje** incorpora al final una galería uniforme con tres secciones:

1. **Carga:** fotos/videos de la bitácora de las hojas de ruta, responsable y fecha. Se conservan también videos legados.
2. **Descarga y recepción:** evidencias de cada guía, indicadas con número de guía, autor y fecha, incluidas las evidencias de recepción registradas por cliente.
3. **Firmas:** imagen de la firma capturada durante la entrega, guía y nombre de quien recibió (declarado por el chofer).

Cada tarjeta tiene miniatura y apertura **con un toque** en un visor a pantalla completa. Las fotos se cargan de modo diferido y los videos se solicitan al servidor solo al reproducirlos. Si JavaScript no está disponible, se conserva la URL autenticada de apertura de archivo.

Dónde aparece:

- **Operador/Jefe de Logística, PWA:** al final de `/transcash/operacion/embarques/<ID>`, con acceso rápido a la galería al comienzo del detalle. Las funciones de captura y liberación anteriores permanecen intactas.
- **Chofer y transportista, PWA:** al final de `/transcash/embarques/<ID>` y con acceso rápido en el detalle. Sin importe de flete para el chofer.
- **Cliente/destinatario, PWA:** al final de `/transcash/guias/<ID>` y solo con los archivos de **esa guía**, nunca con el video común de una hoja de ruta que pueda contener mercancía de otros destinatarios. Sí puede ver fotos de carga legadas que correspondan exclusivamente a su guía.
- **Usuarios internos autorizados (Ventas, Crédito, Cobranzas, Bodega, Contabilidad, Logística):** galería al final de las fichas nativas de Odoo para **Embarque** y **Guía**, mediante un componente de visor embebido; no es necesario abrir otra ventana para consultar los archivos.
- **Transportista, inicio:** nuevo vínculo en el listado de viajes recientes que lleva al detalle y su galería.

## Reglas de acceso

| Actor | Expediente del viaje completo | Expediente de guía individual | Datos de precio |
|---|---|---|---|
| Jefe/operador de Logística | Compañía autorizada | Compañía autorizada | Solo sus permisos actuales |
| Bodega y otras áreas internas con grupo de consulta | Compañía autorizada, solo lectura | Compañía autorizada | Solo grupos financieros |
| Contabilidad | Compañía autorizada, solo lectura | Compañía autorizada, solo lectura | Según sus permisos actuales |
| Chofer Portal | Viaje asignado | Guías propias | **No** |
| Proveedor Portal | Viajes de su empresa | Guías del transporte | Mantiene acceso autorizado a su propia liquidación |
| Cliente Portal | **No** (privacidad entre clientes) | Exclusivamente guías del mismo destinatario | **No** |

Los controladores verifican autorización **antes** de construir la galería. Las fotografías, videos y firmas se sirven desde los endpoints privados existentes, con autorización individual por archivo, `Cache-Control: private, no-store` y MIME controlado. Un enlace copiado de otra compañía, guía o viaje no concede acceso.

La galería es de solo lectura. **No cambia** la API, el armado de rutas y embarques, el precio por viaje, las objeciones, el registro de entrega, las incidencias ni las liquidaciones.

## Cómo actualizar en el VPS

1. Respaldar PostgreSQL, filestore y carpeta del módulo actual.
2. Copiar la carpeta `logistica_transcash` del ZIP V5.20 encima del addon V5.19 (con el servicio detenido o durante la ventana de mantenimiento). Nunca desinstalar el módulo.
3. Reiniciar Odoo y **actualizar** el módulo desde Aplicaciones o con `odoo-bin -d <BASE> -u logistica_transcash --stop-after-init` según el despliegue habitual.
4. Volver a iniciar Odoo; actualizar los recursos del navegador con `Ctrl+Shift+R` y abrir la PWA con Internet para actualizar su caché de aplicación. No borrar datos offline hasta que se sincronicen evidencias pendientes.
5. Verificar con cuentas separadas de operador, jefe de Logística, chofer, cliente de dos destinatarios distintos, proveedor y Contabilidad.

## Pruebas funcionales recomendadas

1. Crear un viaje con dos hojas de ruta y foto o video de carga en cada una. Abrir desde operador y chofer: aparecen **Carga**, **Descarga** y **Firmas** al pie; foto abre en pantalla completa y video reproduce sin descargar.
2. Cerrar una guía con nombre, firma y evidencia. Verificar que aparecen en secciones **Descarga** y **Firmas**, con el número de guía.
3. Entrar como cliente A: solo pueden abrirse archivos de su guía A; no se ve la carga común del vehículo ni la guía del cliente B. Copiar la URL de un archivo de B y verificar HTTP 404.
4. Entrar como cliente B y repetir el aislamiento. Comprobar que no hay valores de transporte.
5. Entrar como transportista: ver únicamente viajes de su empresa y abrir desde su listado la galería; comprobar los permisos de precios habituales en la liquidación.
6. Entrar como Contabilidad: abrir en Odoo un embarque y una guía; bajar al visor integrado, reproducir un video y comprobar que no existen controles de edición de evidencias.
7. Probar múltiples fotos y videos, estado sin firma y viaje sin descarga: cada sección debe mostrar un estado vacío, sin errores ni contenido de otro viaje.
8. Ensayar desde otro usuario sin acceso copiando directamente una URL `/transcash/embarques/<ID>/galeria` y sus archivos: debe devolver no encontrado.

### Validación realizada fuera de Odoo

- Compilación estática de Python y comprobación de sintaxis JavaScript, XML y manifiesto.
- Prueba aislada del agrupamiento y aislamiento de guías usando registros simulados equivalentes al ORM.
- Incluida prueba Odoo `tests/test_evidence_hub_v520.py` para ejecutar con `--test-enable`.
- Integridad del ZIP.

**Limitación:** no se ha ejecutado esta versión con la base real del VPS ni en un runtime completo de Odoo 18. Hacer primero la prueba en una copia de la base. La reproducción de HEIC/MOV puede depender del navegador; MP4/H.264 es el formato de video más compatible.
