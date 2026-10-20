## v1.6 — Stock físico en Explorador y fotos en Reposición
- Explorador de productos: se incorpora columna **Stock · cant.** entre comprado y ABC, ordenable, usando cantidades positivas del stock de corte y el filtro activo de bodega. La columna **Stock $** se conserva.
- Simulador de reposición: se muestran miniaturas verificadas por SKU en la columna Producto, utilizando la misma API/cache de fotos del Explorador. No se alteran la fórmula, el orden, los filtros ni el número de candidatos.
- Stock, demanda y propuesta del simulador muestran su referencia de unidad disponible o inferida, sin convertir m² a cajas o unidades.
- Se corrige el repintado de miniaturas: al volver a una vista, los enlaces ya consultados se aplican de inmediato, sin esperar a la expiración de la caché.
- No requiere volver a importar Excel ni reindexar imágenes que ya están asociadas.

# TRANSCASH — Inventario Inteligente (Odoo 18 Community)

Versión actual: 18.0.1.10.0.

Módulo independiente para Odoo 18 Community que mantiene el mismo diseño del dashboard HTML de Transcash. La visualización web se carga dentro del cliente backend de Odoo mediante una acción OWL y un iframe del mismo origen. No requiere Enterprise ni Inventory de Odoo; la lectura del Excel funciona sin bibliotecas externas. Las consultas de ChatGPT requieren internet saliente y API Key propia de OpenAI.

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


## v1.7 — Filtros de Explorador con búsqueda por texto

El Explorador de productos incorpora tres selectores buscables (proveedor del catálogo, formato y marca).
Permiten escritura, selección con Enter o clic, navegación con flechas, limpiar filtros y combinarlos con los filtros actuales.

- **Proveedor**: usa el campo Proveedor de la hoja Productos; no se confunde con el proveedor de cada compra.
- **Marca**: reutiliza el filtro global de marca, por lo que se sincroniza con el selector superior.
- **Formato**: se conserva exactamente desde la columna Formato del Excel para **nuevas importaciones**.
  Las importaciones anteriores a v1.7 no almacenaron ese campo; en ellas se extraen medidas de la descripción
  cuando están presentes y se agrupan los demás como 'SIN FORMATO IDENTIFICABLE'. Para tener el formato
  comercial exacto de todos los artículos, vuelva a cargar el mismo Excel: el historial previo se conserva.
- Los filtros de proveedor y formato aplican al **Explorador**. La exportación CSV desde esa vista los respeta.
- Se conserva el índice histórico del dataset: la unidad de medida sigue reservada en `p[20]` y el formato se agrega en `p[21]`.


## v1.8 — ABC × XYZ interactivo

- Nueva sección **Análisis ABC × XYZ** en el menú lateral del dashboard. Se conservan las páginas, importaciones, fotos y filtros previos.
- Matriz 3×3 con navegación AX, AY, AZ, BX, BY, BZ, CX, CY y CZ. Tabla por SKU con imagen vinculada, descripción, coeficiente de variación (CV), meses de venta, cantidades y cobertura, ordenamiento, paginación, ficha y exportación CSV.
- Los filtros buscables de proveedor, formato y marca se reutilizan entre Explorador y ABC × XYZ; no hay dos controles que puedan quedar desincronizados. Otros filtros globales también aplican.
- **ABC**: por ventas netas positivas durante el período seleccionado; orden acumulado 80/15/5 del universo filtrado (marca, proveedor, formato, categoría, búsqueda y bodega seleccionada). **XYZ**: CV poblacional de ventas mensuales en unidades durante los **12 meses completos que finalizan en el mes de fin seleccionado**, incluyendo meses sin ventas como cero. Para cada mes: `max(0, cantidad neta del mes)`. X ≤ 0,50; Y > 0,50 hasta 1,00; Z > 1,00.
- Si no hay 12 meses previos, media de demanda cero o ventas acumuladas no positivas, queda «Sin clasificar» en la matriz. La clasificación depende del período y filtros y puede cambiar; el cálculo XYZ no es rotación ni pronóstico de demanda.
- Al filtrar por bodega las ventas siguen siendo corporativas para SKU presentes en esa bodega, pues el archivo no desglosa ventas por bodega. No se mezclan ni suman cantidades entre unidades heterogéneas.
- Indicadores ABC-XYZ dinámicos se obtienen de los datos mensuales ya guardados, por lo que **no requiere nueva importación**. Fotos enlazadas se reutilizan.
- Actualización: reemplazar carpeta `transcash_inventory`, reiniciar Odoo, actualizar módulo desde Aplicaciones (sin desinstalar), refrescar navegador. Validar en entorno de prueba.

---

## v1.9 — Permisos, proveedor + rentabilidad y ChatGPT integrado

### Nuevos apartados
- **Rentabilidad por proveedor**: dos perspectivas: por proveedor de ficha del producto (ventas netas, utilidad bruta, margen, compras de esos SKU, stock a costo de catálogo) y por proveedor **real** de cada movimiento de compras. Ambos respetan los filtros del período y los filtros buscables de formato/proveedor de catálogo/marca, además del filtro global de categoría, marca y bodega. La exportación CSV del dashboard ahora respeta estos filtros en esta pestaña.
- **Consultar con ChatGPT**: preguntas en español, plan estructurado con OpenAI, cálculo determinista desde el snapshot autorizado y explicación sobre el resultado. Permite fórmulas aritméticas controladas entre métricas precalculadas; no genera ni ejecuta SQL o código arbitrario.
- **Configuración de ChatGPT**: menú nativo de Odoo exclusivo de administradores (grupo `base.group_system`). Campos de activar/desactivar, modelo (`gpt-5-mini` predeterminado) y API Key. Incluye botón `Probar conexión` para verificar conectividad y acceso al modelo.

### Permisos
1. **Acceso al panel de inventarios (consulta)** (`transcash_inventory.group_transcash_user`): lectura de los snapshots autorizados y panel general. Los usuarios que ya tenían este grupo mantienen su acceso después de actualizar.
2. **Responsable de inventarios (importar)** (`transcash_inventory.group_transcash_manager`): hereda consulta y permite cargar archivos e indexar fotos.
3. **Consultas de ChatGPT (IA)** (`transcash_inventory.group_transcash_ai`): hereda consulta y permite el asistente, sujeto a que el administrador configure y active la API. Los administradores técnicos pueden usar las rutas IA.
4. **Administrador de Ajustes** (`base.group_system`): único autorizado a administrar API Key, modelo y activación. Las vistas, los modelos y los endpoints hacen comprobaciones de grupo. Los snapshots están restringidos a la empresa actual.

**Asignación**: Ajustes → Usuarios → seleccione usuario → Derechos de acceso → Transcash Inventario. La API Key se guarda en `ir.config_parameter` del servidor; la clave no aparece en el HTML ni en JSON del navegador. Como otros secretos en parámetros de Odoo, es accesible a administradores y personas con acceso a la base de datos o copias de seguridad; proteja ambos recursos y rote las credenciales si se filtran. También puede usarse una clave restringida a este proyecto y límites presupuestarios en la plataforma de OpenAI.

### Configuración y consultas
1. Actualice la aplicación a **18.0.1.9.0** (NO desinstalar).
2. Asigne grupos de consulta y, según sea necesario, grupo de consultas IA.
3. En **Inventario Inteligente → Configuración de ChatGPT**, habilite la IA, introduzca su API Key y modelo; pulse **Guardar configuración** y **Probar conexión**.
4. Abra Dashboard → **Consultar con ChatGPT**. Preguntas ejemplo:
   - `¿Cuáles son los 10 proveedores de ficha cuyos productos dejaron más utilidad en 2026?`
   - `Top 20 formatos 60x60 por ventas y margen` (para ranking de ventas; puede preguntar después por margen).
   - `¿Qué proveedor real suministró más mercadería por valor de compra?`
   - `Crea un indicador de utilidad bruta dividida entre valor del stock por marca.`
5. Si la API Key no es válida, si el modelo no está disponible o se supera la cuota, verá un error concreto. Máximo **25 consultas por usuario cada hora**, con bloqueo transaccional para limitar consumo simultáneo.

**Arquitectura y controles de privacidad**: la pregunta, un diccionario de métricas y una selección de etiquetas comerciales se envían a OpenAI para construir el plan (con `store: false`), y luego la pregunta y hasta 50 filas de resultados agregados para redactar la explicación. Los cálculos económicos los hace Odoo con un conjunto de dimensiones, medidas y operaciones autorizadas; no se manda el Excel entero ni ninguna API Key al navegador. La API de OpenAI tiene su propia facturación y exige conexión HTTPS saliente desde el servidor.

**Limitaciones**: el motor cubre venta neta, costo de venta, utilidad, margen, compras, cantidades vendidas/compradas, stock y fórmulas aritméticas construidas con estas magnitudes. No crea indicadores que dependan de campos inexistentes (por ejemplo inventario medio, GMROI contable real o lead time). Las cantidades no se convierten entre cajas, unidades y m². No puede atribuir rentabilidad a cada proveedor real de una compra sin trazabilidad por lote; por ello se informan por separado compras reales y rentabilidad de cartera.

### Comprobaciones antes de producción
- Copia de seguridad de la base de Odoo y prueba inicial en una instancia clonada.
- Usuario sin grupo: no ve ni consulta el dashboard ni sus rutas JSON.
- Usuario con grupo Consulta: ve el dashboard y análisis por proveedor, pero no importa ni consulta ChatGPT si no se lo autoriza expresamente.
- Usuario con grupo IA: puede consultar ChatGPT pero no ver la clave ni modificarla.
- Administrador: guarda clave, prueba conexión y activa/desactiva integración.
- Comparar las ventas, utilidad, compras y stock de los 12 meses con los resultados existentes; probar filtro de formato `45×45` y ranking de proveedores; comprobar proveedor catálogo versus proveedor real.

**Validación local**: Python y XML compilan, cálculos contrastados con el Excel original. La comprobación visual automatizada y una prueba de API real requieren un entorno que permita Chromium y una API Key activa; no se realizaron contra su servidor Odoo de producción.


## v1.10 — Consultas de IA sin espera infinita

- **Dos etapas**: `/transcash_inventory/ai/ask` con `fast=1` devuelve los valores calculados; `/transcash_inventory/ai/explain` solicita la explicación. Se preserva el antiguo `/ai/ask` para clientes en caché.
- El navegador muestra estados de cada fase, incorpora **Cancelar** y termina cada petición después de 40 segundos si Odoo no responde. Cancelar cierra la espera del navegador; no asegura interrumpir un proceso que el servidor ya esté ejecutando.
- Se sustituye el bloqueo PostgreSQL indefinido por un `pg_try_advisory_xact_lock`: una consulta simultánea del mismo usuario responde HTTP 409 con explicación visible.
- OpenAI usa timeout de conexión de 26 s por etapa. Los modelos de razonamiento GPT-5/GPT-6 y o-series utilizan razonamiento `low` para reducir latencia; límites de salida ajustados.
- El resultado de la primera etapa se muestra aunque falle la redacción de la explicación. La respuesta de la segunda etapa se valida con firma HMAC de 10 minutos vinculada a usuario/empresa y resultados del cálculo; no se transmite API Key al cliente.
- **Diagnóstico:** si persiste el error, primero usar `Configuración de ChatGPT → Probar conexión`; verificar HTTP 401, 403, 409, 429, 502 o 503, y los logs del servicio Odoo sin publicar el token secreto. Para que aplique la corrección es necesario actualizar el módulo y forzar recarga de navegador (`Ctrl+F5`).
- No requiere migración ni reimportación de datos: los datos y permisos continúan almacenados en el mismo módulo. La conexión real requiere prueba dentro de Odoo con una API Key válida.


## v1.11 — Guardado de configuración IA y botón desbloqueado

- **Configuración de ChatGPT** ahora usa un asistente temporal EXCLUSIVO de Transcash
  (`transcash.inventory.ai.configuration`), sin ejecutar el guardado masivo de
  `res.config.settings`. Escribe explícitamente `transcash_inventory.ai_enabled`,
  `transcash_inventory.ai_model` y `transcash_inventory.ai_api_key` en `ir.config_parameter`.
- Tras guardar, comprueba lectura inmediata de los tres parámetros. Si no coincide,
  muestra un error sin indicar que guardó. Volver a abrir el formulario crea un
  asistente nuevo que lee la configuración persistida en la base de datos.
- El campo de API Key está **vacío al abrir por seguridad**, incluso cuando ya hay
  una guardada. El estado de clave guardada aparece en un aviso. Dejar el campo
  en blanco CONSERVA la clave existente; para reemplazarla, ingrese una nueva.
- **Guardar y probar conexión** persiste los cambios ANTES de llamar OpenAI. Un
  problema de conexión se notifica sin invalidar la configuración guardada.
- El botón **Calcular con ChatGPT** ya no queda deshabilitado si el endpoint
  de estado falla o devuelve `enabled = false`. Al pulsarlo, el servidor muestra
  el problema de configuración o permisos real.
- El ACL limita el nuevo asistente a administradores `base.group_system`. Los
  datos, fotografías, importaciones y otros análisis se conservan.
- Prueba recomendada: Active la IA, guarde, salga del menú, entre nuevamente:
  `Activar` debe seguir marcado, el modelo persistente visible y el aviso de
  `API Key guardada` presente. Luego ejecute Guardar y probar conexión y
  realice una consulta del dashboard. Si el aviso dice que no hay clave, revise
  permisos de administrador y el log de Odoo. Nunca comparta la clave en logs.


## v1.12 — Botón ChatGPT siempre accesible y estado verificable

- Corregidos los parámetros de versión de `dashboard.js`, `dashboard.css` y el `iframe` de Odoo: v1.11 mantenía versiones de caché de v1.10 y v1.9. Eso podía conservar el JavaScript anterior, que bloqueaba la consulta cuando la configuración estaba inactiva.
- `Consultar con ChatGPT` permanece habilitado si no hay una petición en curso. Los errores reales del servidor se muestran debajo del formulario (sin prometer que ChatGPT esté configurado).
- Nuevo botón `Verificar estado` en el asistente. El endpoint indica por separado si falta la API Key, si está desactivada la integración o si está lista; jamás muestra la clave.
- `Configuración de ChatGPT → Verificar configuración guardada` confirma el estado leído directamente de `ir.config_parameter` sin consumir API ni revelar credenciales.
- Para aplicar: sustituir carpeta, reiniciar Odoo, actualizar aplicación y hacer Ctrl+F5. La prueba real de OpenAI requiere conectividad y clave válida en el servidor.


## v1.13 — Guardado directo y verificable de ChatGPT

- La opción **Configuración de ChatGPT** abre una página administrativa propia,
  sin formularios transitorios que puedan perder valores al navegar.
- Al guardar, las tres opciones se escriben en `ir.config_parameter` bajo
  `transcash_inventory.ai_*`. Un segundo HTTP GET lee de la base de datos y
  confirma la persistencia **en una transacción posterior**, sin exponer la clave.
- Si el campo de clave llega vacío, mantiene la previamente guardada; se puede
  eliminar intencionalmente mediante la casilla correspondiente.
- Se añadió diagnóstico visible y prueba de conexión independiente.
- Solo `base.group_system` puede abrir la pantalla y consumir sus rutas.
- Los endpoints de consultas leen los mismos parámetros que el formulario y no
  dependen de cachés de asistente. Se conservaron los menús, datos y reportes.
- En la actualización debe reiniciar el servicio Odoo y ejecutar la actualización
  del módulo: de lo contrario puede continuar la pantalla vieja en caché.
- Validación completa en Odoo real pendiente; no introducir secretos en capturas.


## v1.14 — Consultas con varias métricas y contexto de datos

- El plan JSON ahora soporta `metrics` (1 a 8 métricas) y `metric` como columna principal de orden.
  Ejemplo: ventas, utilidad y margen **juntas** por formato 45x45, agrupado por marca.
- El servidor aporta un **diccionario semántico compacto** a la llamada planificadora:
  columnas disponibles, fórmulas reales, limitaciones, períodos y ejemplos de categorías,
  marcas, formatos y proveedores con mayor presencia. No transfiere todos los SKU ni facturas.
- El motor calcula todas las columnas en UNA agrupación determinista (sin SQL de IA),
  con márgenes como ratio de sumas. El frontend genera columnas de resultados y totales
  dinámicamente. Se mantienen las restricciones de empresa, permisos y firma HMAC.
- Permite también las agrupaciones combinadas `categoria_formato`, `categoria_marca`,
  `categoria_marca_formato`, además de las dimensiones anteriores.
- Si el esquema recibe un resultado antiguo con una métrica, conserva compatibilidad
  para que instalaciones que no hayan cargado el nuevo JavaScript sigan funcionando.
- NO habilita rotación contable, utilidad neta ni GMROI si faltan datos históricos.

**Prueba:** `¿Cuáles son las ventas, costo de ventas, utilidad, margen y cantidad vendida
para el formato 45x45, agrupado por marca en los últimos 12 meses?`

Los cálculos del nuevo motor pueden validarse localmente sin ninguna API Key; la
planificación en lenguaje natural necesita pruebas con API Key activa en Odoo.


## Arquitectura IA / SQL (v1.15)

La fuente de cálculo de IA son los **modelos relacionales de Odoo**:

| Modelo ORM | Tabla PostgreSQL | Semántica |
| --- | --- | --- |
| `transcash.inventory.fact.product` | `transcash_inventory_fact_product` | SKU, categoría, marca, formato, proveedor de catálogo, costo y stock actual |
| `transcash.inventory.fact.sale` | `transcash_inventory_fact_sale` | Ventas netas, cantidad y costo de ventas por mes/SKU |
| `transcash.inventory.fact.purchase` | `transcash_inventory_fact_purchase` | Compras y cantidades por mes/SKU |
| `transcash.inventory.fact.supplier.purchase` | `transcash_inventory_fact_supplier_purchase` | Valor de compra por proveedor real/mes/SKU |
| `transcash.inventory.fact.stock` | `transcash_inventory_fact_stock` | Stock al corte por SKU/bodega |

La importación Excel y cualquier integración API que invoque
`env['transcash.inventory.snapshot'].create_from_dataset(dataset, filename='API')`
crean **simultáneamente** la versión histórica para el dashboard y los hechos
normalizados. El adaptador de API debe llamar primero a
`services.processor.build_dataset(...)` o construir el mismo contrato de datos,
incluidos `products`, `sales`, `purchases`, `supplierPurchases`, `stockWarehouses`,
`categories`, `brands`, `providers`, `months`, `summary` y `source`.
No se confunden `proveedor_ficha` (cartera) y `proveedor_compra` (movimiento).

Al usar ChatGPT con una importación de v1.14 o anterior, el endpoint de
preparación crea las tablas normalizadas desde la versión ya conservada
**una sola vez**, sin volver a cargar el Excel. La operación puede tardar
segundos según tamaño/recursos de PostgreSQL; no cerrar la sesión.

ChatGPT obtiene un diccionario generado desde `env[modelo]._fields` de solo
cinco modelos aprobados. Devuelve un plan estructurado de dimensiones,
métricas y filtros, no código SQL. El servidor genera un `SELECT` con
**identificadores fijos** y parámetros enlazados, incluyendo `company_id`
y `snapshot_id`. Cada consulta deja visible el SQL ejecutado y sus parámetros
al usuario autorizado. No se ejecuta SQL libre ni sobre cualquier modelo de Odoo.
La API Key nunca se incluye en el esquema ni en el SQL.

### Pruebas de actualización

1. Respaldar base de datos y carpeta del módulo. Actualizar (no desinstalar).
2. Abrir consulta IA. El primer uso prepara las tablas para importaciones viejas.
3. Pulsar «Ver esquema de datos Odoo autorizado» y comprobar los cinco modelos.
4. Probar «Ventas, costo de ventas, utilidad, margen y compras del formato 45x45, agrupadas por marca».
5. Verificar columna «Fuente: tablas relacionales de Odoo» y desplegar «Ver sentencia SQL».
6. Probar con usuario que NO tenga permiso `Consultas de ChatGPT`, y con otra empresa.
7. Registrar un nuevo dataset vía `create_from_dataset` para validar futuras API.

**Limitaciones:** SQL probado por generación y comparación local; la instalación
Odoo18 + PostgreSQL y OpenAI requieren validación en el servidor real.
No existe histórico de stock al cierre ni ventas por bodega en el archivo fuente.
