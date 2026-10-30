# Integración getdatosdespachos · Odoo 18 · versión 1.8

## Qué queda implementado

Consulta GET con el mismo esquema del módulo Inventario Inteligente adjunto. Las credenciales pertenecen a **API Administrator**; el módulo de despachos no las duplica ni las envía al navegador. Solo depende de `api_administrator`, `base`, `web` y la biblioteca Python `requests`; no depende de Inventario Inteligente ni de Comisiones.

La API y Excel convergen en el mismo procesamiento de cortes: ciudades, parámetros SLA, bodegas, agrupación de facturas, detalle y publicación. La llave comercial sigue siendo **compañía + TipoFactura + NumeroFactura**. No incluye establecimiento, bodega ni número externo de presentación.

## Configuración inicial

1. Actualizar `transcash_dispatch_analysis` a 18.0.1.8.5, con `api_administrator` disponible en addons. Reiniciar Odoo y actualizar el módulo; no desinstalar ni volver a importar el Excel. Esta actualización conserva el cursor de avance y agrega el control de agrupación y tamaño adaptativo; requiere actualizar la base, además de copiar los archivos.
2. Seleccionar la empresa correspondiente. En API Administrator, configurar **exactamente un registro GET activo**:

   | Campo | Valor |
   | --- | --- |
   | `name` | `getdatosdespachos` |
   | `type` | `get` |
   | `status` | `A` |
   | `company_id` | Empresa de los despachos |
   | `url` | URL base del ERP |
   | `end_point` | Ruta final que expone el método getdatosdespachos |
   | `user_id`, `password` | Credenciales del ERP |

3. En **Análisis de despachos → Configuración → Fuentes y API**, abrir la misma fuente con la que se importó el Excel (normalmente `TRANSCASH`). Activar **Sincronizar API cada 2 horas**. Se permite una sola fuente automática por empresa. En otra empresa, usar su propia fuente y registro API.
4. Ejecutar **Análisis de despachos → Sincronizar → Sincronizar** y seguir el progreso desde la recepción. La pantalla de operación no solicita parámetros técnicos y usa la fuente automática configurada para la empresa (o la primera fuente activa si aún no se habilitó la automática). Esta ejecución está disponible para Operador y Responsable y también funciona sin activar la consulta automática. Los detalles se administran en Fuentes y API.
5. Verificar el estado final de importación y los totales. La ficha de fuente muestra el último intento, respuesta válida, resultado y enlace a la importación. “Última respuesta válida” indica que la descarga y validación del JSON terminaron; el estado de importación informa si el procesamiento acabó o encontró un error.

Al actualizar se crea un cron activo llamado **Despachos: consultar getdatosdespachos cada 2 horas**. Solo consulta fuentes con la casilla anterior activada. No se hace ninguna petición HTTP durante la actualización del módulo. La programación se puede revisar en Acciones planificadas; se conserva si el administrador la modifica.

## Petición que enviará Odoo

- Método **GET**, sin filtros ni cuerpo. Las fechas del tablero no recortan el universo del origen.
- URL: `url.rstrip('/') + '/' + end_point.lstrip('/')`; si no hay ruta, se usa `url` como URL completa.
- Cabeceras: `Accept: application/json`, `version: 1`, `framework: PRUEBAS`, `userid`, `password`, `deviceid: 000000000000000`, `sessionid: 0`.
- Tiempo de conexión 10 s y lectura 120 s; máximo 128 MiB de respuesta y 500.000 filas. Las redirecciones están bloqueadas; configurar la URL final.
- Se buscan únicamente registros API de la empresa de la fuente, con el nombre, método y estado indicados. Faltantes o duplicados generan un resultado visible y no se sustituyen datos vigentes.

## Respuesta del método en el ERP

Ejemplo completo en `examples/getdatosdespachos_response.json`:

```json
{
  "success": true,
  "fecha_corte": "2026-10-29",
  "total_rows": 1,
  "data": [
    {
      "TipoFactura": "FA", "NumeroFactura": "000001",
      "FechaFactura": "2026-10-27", "Ciudad": "GUAYAQUIL",
      "Cond_Entrega": "Entrega Transcash", "CodBodega": "B01",
      "Facturado": 10, "DespachoFisico": 4,
      "AjusteDevolucion": 0, "Pendiente": 6,
      "UltimoDespacho": "2026-10-28",
      "PesoFacturado": 1000, "PesoDespacho": 400, "PesoPendiente": 600,
      "PalletsFacturados": 2, "PalletsPendientes": 1.2
    }
  ]
}
```

Todos los pesos se reciben **en kilos** y Odoo los convierte a toneladas. Cantidades y pesos son acumulados a la fecha de corte; no son movimientos que se deban sumar al saldo previo. PalletsFacturados es opcional: si no existe, dejarlo ausente o null y se mostrará Sin dato/parcial. No convertir nulos desconocidos en ceros. No se calculan pallets facturados ni kg facturados a partir de una proporción de productos mezclados.

Una fila por factura y bodega cuando el origen está consolidado. Si se entrega detalle por producto, incluir `CodProducto` y una fila única por producto/bodega. Mantener el mismo nivel dentro de cada factura. Las distintas bodegas/productos sobreviven; las repeticiones de la misma clave de detalle se reemplazan por su última aparición sin sumarse. La tabla completa de columnas comunes está en `CONTRATO_API.md`.

Se admiten lista directa y envoltorios `data`, `result`, `results`, `items`, `rows`, `records`, `response` o `payload`, incluso anidados. Se reconocen variantes de mayúsculas/guiones bajos como `numero_factura`; también `tipo` y `numero`. Para evitar pérdida de ceros iniciales, enviar identificadores como texto. Las cantidades obligatorias son `Facturado`, `DespachoFisico` y `Pendiente`; campos ausentes o inválidos cancelan la carga antes de crear un corte.

`fecha_corte`/`cutoff_date` es opcional, pero recomendado. Sin él se toma el día de la operación (zona de la empresa, con America/Guayaquil como respaldo). No se admiten cortes futuros ni anteriores al vigente en esta consulta. Se recomienda `YYYY-MM-DD`; desde 1.8.2 se acepta **YYYY.MM.DD**, como `2026.01.05`. Se conservan `DD/MM/YYYY`, `DD-MM-YYYY`, con hora opcional, y objetos PHP con `date` y `timezone`, incorporados en 1.8.1. El formato con puntos es año/mes/día; el regional con barras o guiones es día/mes/año, sin inferir el formato de Estados Unidos. Se normalizan también FechaFactura y UltimoDespacho. Timestamps con zona se convierten a la zona de la operación antes de obtener su fecha, y timestamps sin zona se consideran locales. Detalles en `FECHAS_API_V1_8_1.md`.

La respuesta debe contener el **universo completo de la fuente**, incluidas facturas ya despachadas y todas sus bodegas/productos. No entregar solo pendientes, solo últimas modificaciones ni una página parcial: eso eliminaría del universo vigente las facturas omitidas y alteraría el cumplimiento. Incluir `total_rows` con el número total de filas de `data` y obtener una extracción coherente del ERP. `total_rows`, `total_records`, `total_lineas` y `total` en un envoltorio son controles de filas; deben coincidir. Si el ERP no declara controles ni paginación, Odoo no puede detectar una omisión que parezca una respuesta completa.

La paginación declarada (`has_more`, `next_page`, `next`, `links.next`, `total_pages`, `last_page` o estos indicadores bajo `pagination`) se rechaza. El servicio debe consolidar el corte completo en su respuesta. Una lista vacía se considera un resultado que requiere revisión y conserva el corte anterior. La recepción XML-RPC anterior mantiene su operación explícita para vaciar una fuente con controles cero.

## Actualización sin duplicación

1. Un bloqueo por fuente evita descargar y cargar al mismo tiempo desde cron, botón y Excel. Si ya hay una importación recibiendo/en cola/importando, se devuelve su progreso y no se hace otra descarga.
2. Se normalizan y validan los registros. Una huella de su contenido efectivo permite conservar el corte vigente si no hubo cambios en el mismo día/corte. El orden de las filas no genera versiones nuevas; repetir el feed completo tampoco.
3. Si cambian las facturas, se recibe un corte nuevo por bloques de hasta 5.000 filas/20 MiB. Desde 1.8.5, las nuevas consultas guardan las filas agrupadas de forma estable por factura y evitan el segundo ordenamiento en disco. El cron de importación carga inicialmente hasta 500 facturas/2.500 líneas por transacción y adapta su tamaño al tiempo observado; no divide una factura individual. La pantalla consulta su avance. Si ese cron está desactivado, conserva las operaciones interactivas de 100 facturas/500 líneas; el cursor permite continuar tras una respuesta perdida. Las cargas anteriores permanecen compatibles.
4. Las ciudades se crean antes de capturar los parámetros: **Guayaquil 3 días calendario, demás ciudades 9**. Las reglas existentes, editadas o archivadas se respetan; no se reinician cada dos horas.
5. El corte anterior permanece visible hasta completar todos los bloques. Al terminar se publica una sola versión vigente por compañía/tipo/número. Los históricos se conservan fuera de los indicadores. Las anulaciones/exclusiones del universo se reflejan al sustituir el corte completo.
6. Una factura totalmente despachada sigue en la respuesta con Pendiente=0 y sus acumulados reales. Así deja de sumar carga pendiente y permanece en el denominador de facturación/cumplimiento.

No se borran automáticamente los cortes históricos. Las respuestas sin cambios del mismo corte no crean otro; un cambio de fecha de corte permite actualizar antigüedades y plazos. La integración incremental y una política de retención serían ampliaciones separadas.

## Validación realizada y pendiente

Pruebas locales con el HTTP y ORM simulados: cabeceras iguales al módulo adjunto, filtros por empresa/nombre, errores/redirecciones, formatos y tamaños, fechas locales, respuestas repetidas, actualización de cantidades, reversiones, bloqueos, cron por empresa y conservación de ciudades. También se recorrió el Excel original completo convertido a registros API: mismos totales, facturas únicas, toneladas y pallets; repetirlo o reordenarlo conserva la huella efectiva.

Se incluyen pruebas nativas en `tests/test_api_sync_odoo.py` para ejecutar en una base de prueba Odoo 18 con API Administrator instalado. No se ha accedido al servidor del cliente ni al endpoint real; no se afirma una instalación, sincronización o validación remota.

Referencias: [acciones programadas Odoo 18](https://www.odoo.com/documentation/18.0/developer/reference/backend/actions.html) y [contrato HTTP de Requests](https://requests.readthedocs.io/en/latest/user/quickstart/). La configuración de cabeceras y los campos API Administrator se obtuvieron del código del módulo Inventario Inteligente proporcionado, no de una suposición sobre su API.
