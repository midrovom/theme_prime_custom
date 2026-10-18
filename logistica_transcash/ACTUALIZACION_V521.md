# Transcash V5.21 — Navegación única: embarque → hojas de ruta → guías

Actualización incremental para Odoo 18, basada en la V5.20.

## Criterio de operación

* **Chofer Portal**: al ingresar a `/transcash` ve **Mis viajes**, nunca una bandeja paralela de guías. Abre su viaje y despliega sus **hojas de ruta**; dentro de cada una aparecen las **guías** con cliente, destino, estado y acceso a la entrega individual. El conductor sigue aceptando/objetando **el embarque**, nunca cada ruta por separado. Continúa con el mismo cierre de recepción con nombre, foto/video y firma. No se muestran montos del flete.
* **Operador / jefe de Logística**: antes de armar el embarque conserva `Guías por planificar`, pues necesita buscar y seleccionar documentos al **crear cada hoja de ruta**. Una vez armado, la ficha del embarque presenta **hojas de ruta con sus guías**, sin duplicarlas como documentos independientes. En el centro de operaciones hay un desplegable **Ver guías de esta ruta** junto a la bitácora y captura de carga.
* **Proveedor transportista**: abre su viaje y consulta las mismas rutas → guías, con los permisos económicos que ya tenía en el módulo separado de liquidaciones. No puede planificar rutas ni registrar operación.
* **Otras áreas internas**: ven la misma jerarquía en la WebApp; en el escritorio Odoo el formulario de Embarque prioriza **Hojas de ruta y guías**, y al abrir cada ruta se consultan las guías. Para viajes históricos sin hojas se preserva una pestaña de guías históricas.
* **Cliente/destinatario**: excepción intencionada. Mantiene su lista **Mis guías**, sin permiso de ver el embarque ni otras hojas de ruta; solo consulta sus entregas y evidencias autorizadas.

## Qué cambia y qué NO

Modifica solamente navegación y visualización, sin escribir en las tablas operativas ni modificar autorizaciones, montos, API, guías, hoja de ruta, evidencias, offline, pagos o cierre del chofer.

El detalle del embarque usa el modelo existente: `embarque.ruta_ids` → `ruta.guia_ids` → `transcash.guia`. El componente de tarjeta es único y se reutiliza en el detalle de viaje y en el Centro de operaciones. La galería **Carga / Descarga / Firma** sigue al final. Las rutas se despliegan al tocarlas; durante el trayecto se abren automáticamente aquellas con entregas pendientes.

**Compatibilidad histórica:** las guías de embarques creados antes de existir hojas de ruta no desaparecen. Se agrupan bajo «Guías históricas sin hoja de ruta», únicamente en el viaje correspondiente. Los enlaces directos a guías continúan activos porque se usan para cerrar entregas y procesar evidencias offline.

## Instalación

1. Respaldar PostgreSQL, filestore y carpeta `logistica_transcash` V5.20.
2. Sustituir **la misma carpeta** del addon por el contenido del ZIP V5.21.
3. Reiniciar Odoo 18 y actualizar el módulo Transcash desde Aplicaciones. **No desinstalar.**
4. Desde un teléfono abrir la PWA con Internet, recargar y acceder a `/transcash/embarques`; si quedó un recurso antiguo, cerrar y volver a abrir la PWA.

## Pruebas prácticas en el VPS

1. Chofer Portal: entrar a `/transcash` y comprobar que existe **Mis viajes**, no un menú independiente «Mis guías».
2. Abrir un embarque con dos hojas de ruta y varias guías: desplegar la primera ruta, entrar a una guía, usar **Volver** y regresar a esa ruta. Confirmar que no se muestra precio.
3. En ruta, confirmar que los destinos con guías pendientes están desplegados. Registrar la llegada, la descarga, el nombre y la firma del receptor como antes.
4. Operador de Logística: buscar guías por planificar al preparar la ruta; luego abrir el embarque en Centro de operaciones y desplegar cada lista de guías dentro de su ruta.
5. Proveedor y usuarios internos autorizados: verificar la navegación por hojas de ruta sin facultades nuevas de edición.
6. Cliente: confirmar que continúa viendo solamente sus propias guías, sin acceso al embarque completo ni a valores/objeciones internas.
7. Embarque antiguo sin rutas: confirmar que sus guías permanecen accesibles desde la sección histórica.
8. Galería: fotos, videos y firma al pie del embarque; verificar que los archivos privados conservan sus controles de acceso.

## Validación y límites

Se pueden verificar de forma estática Python, JavaScript y XML, referencias de QWeb, permisos intactos, integridad ZIP y comparación con V5.20. No contamos con un Odoo 18 ejecutándose con tus datos, por lo que las pruebas funcionales de escritorio y PWA se deben ejecutar en copia de tu VPS antes de producción.
