# TRANSCASH — Inventario Inteligente (Odoo 18 Community)

Versión actual: 18.0.1.2.0.

Módulo independiente para Odoo 18 Community que mantiene el mismo diseño del dashboard HTML de Transcash. La visualización web se carga dentro del cliente backend de Odoo mediante una acción OWL y un iframe del mismo origen. No requiere Enterprise, Inventory de Odoo, internet ni bibliotecas externas para leer el Excel.

## Funcionalidad incluida

- Importación mediante el menú **Cargar archivos** (sin modal, carga por bloques) de un archivo `.xlsx` con las hojas **Productos**, **Stock**, **Ventas** y **Compras** (estructura del archivo `Analisis Transcash inventarios.xlsx`).
- Procesamiento en el servidor con lectores OOXML estándar, sin `pandas` ni `openpyxl`.
- Ocho apartados: Resumen ejecutivo, ABC/rentabilidad, cobertura/riesgo, simulación de reposición, bodegas, proveedores, explorador de productos y auditoría.
- Filtros interactivos por meses, categoría, marca, bodega y búsqueda de código/descripción/proveedor.
- Exportación CSV de resultados filtrados, detalle SKU y escenario de reposición 30/45/60/90 días.
- Historial de importaciones (cada archivo se guarda como nueva versión) y botón en el formulario histórico para visualizar sus indicadores.
- Separación por empresa de Odoo y grupos de seguridad de consulta e importación.
- Adaptador de análisis preparado para una futura API: `services.processor.build_dataset(productos, stock, ventas, compras, ...)` y `models.snapshot.create_from_dataset(dataset, ...)`.

## Instalación

1. Descomprime el ZIP y copia **solo la carpeta `transcash_inventory`** a un directorio incluido en `addons_path` de Odoo. Compruébalo en tu configuración: `grep '^addons_path' /etc/odoo18wv.conf`.
2. Asegura que el usuario del servicio Odoo pueda leer la carpeta y los archivos, reinicia el servicio Odoo correspondiente.
3. En Odoo: **Aplicaciones → Actualizar lista de aplicaciones**, busca `TRANSCASH | Inventario Inteligente` e instálalo.
4. Ve a **Ajustes → Usuarios** y asigna uno de los roles del módulo: **Consulta de inventarios** o **Responsable de inventarios (importar)**. Los administradores con el grupo Ajustes también pueden gestionar la carga.
5. Abre **Inventario Inteligente → Cargar archivos**, selecciona el Excel de cuatro hojas y pulsa **Cargar y procesar Excel**. La aplicación abrirá el **Dashboard** automáticamente. Si aún no hay datos, el dashboard muestra un aviso integrado en la página, nunca un modal.

### Instalación desde consola (opcional)

Si tu configuración ya incluye la carpeta de complementos y tu entorno virtual está activado, un ejemplo es:

```bash
cd /opt/odoo18wv/odoo18wv
./odoo-bin -c /etc/odoo18wv.conf -d odoo18wv -i transcash_inventory --stop-after-init
```

Usa el **usuario del servicio Odoo**, no root. Verifica antes el nombre de la base, el ejecutable, el entorno virtual, `addons_path` y el nombre del servicio. Haz una copia de seguridad de la base antes de instalar en producción.

## Formato de las hojas Excel

| Hoja | Columnas esperadas |
|---|---|
| Productos | `Codigo`, `descripcion`, `categoria`, `Formato` (opcional), `marca`, `proveedor`, `costo`, `precio` |
| Stock | `producto`, `nBodega`, `Stock`, `Valor` |
| Ventas | `producto`, `cantidad`, `Total_venta`, `Total_costo`, `Mes`, `Anio` |
| Compras | `producto`, `Cantidad`, `Costo`, `Mes`, `Anio`, `Proveedor`, `Valor` |

La carga agrupa movimientos por SKU, mes y, en compras, proveedor. Distingue stock positivo y negativo por bodega. Conserva el valor de origen de Stock únicamente para auditoría y valoriza provisionalmente por `cantidad positiva × costo del catálogo`.

**Límites**: hasta 45 MB `.xlsx`, 320 MB descomprimidos y 350.000 filas por hoja. No hay importación CSV o XLS antiguo en esta versión.

## Permisos y empresas

Los endpoints `/transcash_inventory/dashboard`, `/transcash_inventory/data` y `/transcash_inventory/upload` requieren sesión de Odoo. La carga usa POST con token CSRF, exige rol de responsable y se guarda para la empresa actualmente seleccionada. Los datos se guardan comprimidos en un adjunto de Odoo, no en archivos públicos. El historial y la consulta se limitan a las empresas autorizadas.

## Limitaciones del análisis

- No calcula rotación contable ni GMROI porque la fuente no incluye inventarios promedio históricos valorizados.
- Los datos de venta no están desglosados por bodega. Filtrar una bodega filtra SKU con stock allí, pero **no atribuye ventas a esa bodega**.
- Los planes de compra son escenarios, no pedidos aprobados: faltan plazos de entrega, mercancía en tránsito, pedidos abiertos, stock reservado, mínimos de compra y presupuesto.
- Los movimientos mensuales no permiten establecer última fecha exacta de venta; la identificación de demanda se basa en ventas netas agregadas por mes.
- Las etiquetas de recomendación y ABC global utilizan los últimos 12 meses de referencia completos disponibles. El ABC mostrado por pantalla se recalcula por filtros; las recomendaciones globales no se recalculan con cada periodo seleccionado.
- El estado de stock proviene de una fotografía sin fecha explícita; validar contra el inventario físico/contable.
- La API externa **no está conectada aún**: el procesador compartido permite incorporarla en una segunda etapa sin cambiar el diseño HTML.

## Probar una importación

El Excel `Analisis Transcash inventarios.xlsx` analizado debe producir aproximadamente estos resultados (últimos 12 meses completos, oct/2025-sep/2026):

- 16.150 SKU consolidados (16.127 registros de Productos).
- Ventas: USD 23.790.118,40.
- Utilidad bruta: USD 6.352.490,39.
- Compras: USD 19.399.782,21.
- Inventario valorizado provisionalmente: USD 7.218.983,45.
- Stock sin ventas netas en 6 meses: USD 1.939.796,91.

Cualquier variación sustancial en estos importes tras cargar el mismo Excel puede indicar que la exportación cambió, que alguna columna tiene otro significado o que cambió la fecha de referencia.

## Arquitectura

```
transcash_inventory/
├── __manifest__.py
├── models/snapshot.py          # Metadatos e histórico; almacena JSON comprimido
├── services/processor.py       # XLSX → registros normalizados → dashboard JSON
├── controllers/routes.py       # Sesión Odoo, importación CSRF y entrega de datos
├── static/src/dashboard.html   # Maquetación original Transcash
├── static/src/dashboard.css    # Estilo original + aviso no intrusivo sin datos
├── static/src/dashboard.js     # Gráficos, filtros y simulador; datos dinámicos
├── static/src/odoo_action.*    # Integración nativa en menú/cliente OWL Odoo
├── security/                    # ACL, grupos y regla multiempresa
└── views/                       # Menú, acción, historial
```

## Verificación efectuada

El importador fue probado en Python con el archivo original y coincidieron sus principales cifras. La visualización fue probada en Chromium con datos servidos de forma simulada: navegación, filtros, panel de reposición, productos y ventana de importación sin errores JavaScript. **No se ha realizado una instalación ni prueba E2E dentro de una instancia real de Odoo 18**; se recomienda instalar en staging antes de producción.

## Cambios versión 18.0.1.1.0

- Eliminado por completo el modal de carga y el bloqueo de pantalla cuando no hay importaciones.
- Nuevo menú **Inventario Inteligente → Cargar archivos**, visible para Responsable de Inventarios y administradores.
- Carga nativa Odoo con validación de Excel, barra de acción y redirección al dashboard cuando la versión se almacena correctamente.
- Cuando no existen datos, un aviso informativo se muestra dentro de la página sin bloquear la navegación.
- Para actualizar una instalación existente usa `-u transcash_inventory` (no `-i`), reinicia el servicio y actualiza los recursos web del navegador.

## Corrección v18.0.1.2.0 — carga que no responde al seleccionar archivo

- **Nuevo menú Cargar archivos** conectado a una acción OWL de Odoo con un formulario HTML dedicado. Ya no depende del campo Binary del asistente anterior (el asistente se conserva por compatibilidad, pero el menú apunta a la nueva pantalla).
- Al elegir el archivo se muestra su nombre y tamaño; **la selección no sube automáticamente**. Pulsa **Cargar y procesar Excel** para iniciar la importación.
- Transferencia fragmentada en bloques de 384 KiB (26 bloques para el Excel original de ~9,5 MB), con barra de progreso real de fragmentos enviados y una fase final de procesamiento.
- Las peticiones van autenticadas en la sesión activa de Odoo, incluyen CSRF y mantienen los permisos de responsable y separación por empresa.
- Los bloques se guardan temporalmente en adjuntos privados vinculados a una sesión de carga; al finalizar se genera una versión histórica y se eliminan los adjuntos temporales. Un cron elimina sesiones abandonadas después de 24 horas.
- Un fallo devuelve un mensaje visible con código o motivo y permite intentar otra vez; si la importación termina correctamente, retorna al dashboard.
- No cambia `static/src/dashboard.html`, sus indicadores ni la funcionalidad anterior.

### Para actualizar desde v1.1 (no reinstalar ni desinstalar)

1. Haz **respaldo de la base y addons**.
2. Copia la carpeta `transcash_inventory` de este ZIP **reemplazando** la carpeta v1.1 existente, sin duplicar addons en otro lugar.
3. Reinicia el servicio Odoo correspondiente.
4. **Actualiza el módulo**, desde Aplicaciones → TRANSCASH Inventario Inteligente → Actualizar. Alternativamente, en mantenimiento, usa `odoo-bin -c /etc/odoo18wv.conf -d odoo18wv -u transcash_inventory --stop-after-init` con el entorno/usuario adecuados; luego reinicia Odoo.
5. En el navegador haz `Ctrl+F5` para obtener los nuevos activos. Abre **Inventario Inteligente → Cargar archivos**, selecciona el **Excel original** y pulsa **Cargar y procesar Excel**.
6. Debes ver «Subiendo Excel...» y «Transferencia completa. Procesando datos...», y finalmente el número de SKU, período y versión importada.

### Si continúa el problema

- Si el menú nuevo no aparece, normalmente falta **actualizar el módulo** (no basta copiar el ZIP).
- Si aparece `HTTP 403`, verifica que el usuario tenga el grupo Responsable de inventarios, empresa activa y sesión válida.
- Si aparece `HTTP 413`, revisa `client_max_body_size` en Nginx y los límites HTTP de Odoo/servidor: la transferencia ahora usa bloques de menos de 400 KB, pero una configuración excepcionalmente restrictiva podría bloquearlos.
- Si muestra `HTTP 404` en `/upload/start`, la versión desplegada aún no tiene los controladores nuevos o el servicio no se reinició.
- Si el error ocurre al terminar, valida que el Excel tenga las hojas **Productos, Stock, Ventas, Compras** y revisa el log de Odoo para excepciones del procesador.
- Si el archivo supera 45 MB, reduce su tamaño o solicita subir el límite en una siguiente versión; no aumentes los límites globales sin evaluar seguridad.

### Verificaciones realizadas antes de distribuir

- `compileall` de módulos Python y parsing de archivos XML.
- Procesador probado con el Excel fuente de Transcash, obteniendo 16.150 SKU, ventas USD 23.790.118,40, utilidad USD 6.352.490,39 y stock catalogado USD 7.218.983,45.
- Interfaz de importación probada en Chromium con un servidor simulado: selección de archivo, botón habilitado, 26 solicitudes de transferencia, señal de procesamiento y confirmación de éxito, sin errores JavaScript.
- **Pendiente:** instalación y prueba de integración sobre tu servidor real de Odoo 18; no puede certificarse aquí el límite HTTP ni la configuración de tu instancia.

## Novedad versión 1.3: Fotografías vinculadas desde Transcash.ec

Esta versión mantiene la carga XLSX y el dashboard de la v1.2. No sustituye sus
snapshots ni modifica `product.template` de Odoo 18.

### Funcionamiento

1. Instale/actualice el módulo sobre la carpeta existente `transcash_inventory`.
2. Importe el Excel con las hojas Productos, Stock, Ventas, Compras.
3. Abra **Inventario Inteligente > Buscar imágenes** (permisos Responsable).
4. Pulse **Buscar fotografías** y mantenga abierta la pantalla; el navegador
   procesará 2 páginas públicas de Transcash.ec por solicitud con pausas.
   El proceso puede detenerse y retomarse, sin perder coincidencias guardadas.
5. Revise las coincidencias desde **Inventario Inteligente > Imágenes vinculadas**.
   Puede registrar una URL `https://transcash.ec/shop/...` y una imagen
   `https://transcash.ec/web/image/...` para asociar manualmente un código.
6. En **Dashboard > Explorador de productos**, la miniatura y la ficha individual
   consultan el mapeo de imágenes por SKU y no alteran los indicadores.

### Criterios de seguridad/precisión

- Solo se vincula automáticamente cuando el código SKU coincide exactamente
  con el prefijo de la URL de Odoo Website (antes de la descripción).
- No se transfiere la imagen desde el navegador a Odoo; se guarda su enlace
  público. El navegador carga la imagen desde `www.transcash.ec`.
- No se usa coincidencia aproximada por nombre para evitar foto equivocada.
- Las URL editables están limitadas a HTTPS y dominios transcash.ec.
- Si la página está bloqueada, la sincronización muestra el error y no inventa
  coincidencias ni repite indefinidamente la misma página.
- No todos los SKU de ERP se encuentran publicados en el ecommerce. La tienda
  puede ofrecer muchas menos fichas que los códigos del Excel.
- En imágenes ausentes o rotas, el frontend presenta un marcador neutro.
- No se han comprobado imágenes reales en Odoo de producción: probar primero
  con el código de ejemplo `EURATENMARF` (ficha pública 1412).

### Direcciones web de la función

- `/transcash_inventory/photos/scan` - herramienta en iframe integrada en Odoo.
- `/transcash_inventory/photos/status` - estado actual de búsqueda.
- `/transcash_inventory/photos` - consulta limitada por SKU para el frontend.
- `/transcash_inventory/photos/lookup?sku=EURATENMARF` - prueba de asociación.

La conectividad HTTP(S) entre el servidor Odoo y `www.transcash.ec` es
necesaria para la indexación. Si no hay conectividad se puede asociar URLs
manualmente. El indexador no requiere credenciales del sitio ni instala
paquetes adicionales.

### Asociación puntual por URL

En la misma pantalla **Buscar imágenes**:
- Introduzca el código `EURATENMARF`.
- Pegue `https://transcash.ec/shop/euratenmarf-ceramica-atenas-marfil-24-5-50-1-96-mt-51cjs-p-1412`.
- Pulse **Vincular ficha exacta**.
- En el dashboard, la ficha del SKU mostrará el enlace a la foto principal.

La asociación puntual valida que el SKU aparezca como prefijo del slug de
producto y exista en el snapshot importado. No inventa ni confunde el código.

## v1.4: Explorador con fotos y cantidades físicas

- En **Explorador de productos**, las miniaturas ya vinculadas a cada SKU se solicitan automáticamente al renderizar la página; si una imagen no está vinculada aparece el marcador «Sin foto» y puede sincronizarse en **Buscar imágenes**. No se asignan fotos por similitud de nombre.
- Añadidas columnas ordenables **Vendido · cant.** y **Comprado · cant.**, calculadas con `Ventas.Cantidad` y `Compras.Cantidad` del período seleccionado, por código. Compras y ventas pueden ser negativas por devoluciones y se presentan netas; no convertir a valor monetario.
- El campo **Unidad de medida** NO existe en el Excel original. «m²*» y «und.*» son inferencias solo cuando la descripción las menciona explícitamente y requieren validación con el ERP; «s/d» indica que no se conoce la U.M. real. No se realizan conversiones entre cajas, piezas y metros cuadrados.
- La ficha individual y el CSV filtrado también incluyen cantidades vendidas, compradas y U.M. referencial. La foto requiere que el SKU haya sido vinculado por sincronización o manualmente.

### Fotos: sincronización automática (v1.4)

- Al abrir el Explorador, las imágenes ya vinculadas se muestran sin acciones del usuario.
- Un usuario con permiso de importación inicia un barrido inicial ligero en segundo plano al abrir el Explorador (máximo 2 páginas por visita).
- Se instala la tarea programada `TRANSCASH: Indexar fotos públicas por SKU` que examina hasta dos páginas del catálogo cada 15 minutos (una empresa por ejecución, con pausa si falla la web). Los registros con SKU exacto quedan vinculados.
- La primera sincronización completa del catálogo no es instantánea: las fotos dependen de que Transcash.ec sea accesible y publique una ficha cuyo prefijo coincida exactamente con el SKU. Los SKU sin ficha mantienen marcador.
- Si el servidor restringe salida HTTPS, puede usar **Buscar imágenes** manualmente o conectar la API posteriormente.


## v1.5 — Fotografías verificadas y búsqueda puntual

- El SKU visible en el Explorador entra a la cola si carece de foto; el panel no espera llamadas a Transcash.ec.
- **Buscar imágenes → Buscar este SKU ahora** consulta la búsqueda pública y exige coincidencia exacta del SKU en la URL.
- **Comprobar y vincular URL** permite pegar la URL exacta del producto y lee `og:image` u otras imágenes de la propia ficha.
- Se valida que la respuesta sea una imagen real y se genera una miniatura JPEG local de 240 px, servida por una ruta autenticada desde Odoo para evitar fallos del navegador al acceder a otra web.
- Fotos anteriores se marcan *Sin verificar* y son comprobadas progresivamente por el cron.
- Estados: verificada, pendiente, no encontrada, imagen rota y error remoto, con un próximo reintento.
- El cron existente procesa lotes pequeños cada 15 minutos. No se descargan las 16.000 fotos de golpe.
- El ZIP actualiza el mismo módulo `transcash_inventory`; **no desinstalar** o se perderían los snapshots.
- Dependencia de imagen: Pillow, incluida habitualmente con Odoo 18.
- Las búsquedas y verificaciones dependen de que el servidor Odoo pueda acceder por HTTPS a `www.transcash.ec`.
- No se modifica `product.template` ni el Excel importado.
