# Contrato de recepción de datos

## Alcance y autenticación

La recepción utiliza la API externa de Odoo 18, XML-RPC sobre HTTPS, con un usuario técnico del perfil **Operador** y acceso a la compañía de destino. Usar una API key en lugar de contraseña. No se crean rutas públicas ni se evita la seguridad del ORM.

El conector de origen obtiene un exportador completo y estable, lo normaliza a las columnas siguientes y lo envía por bloques. Debe congelar el mismo universo/página de origen durante una extracción: paginar sobre datos que cambian sin un identificador de corte puede dejar faltantes o duplicados.

## Columnas

| Campo | Tipo | Uso |
| --- | --- | --- |
| `TipoFactura` | texto, obligatorio | Parte de la clave. |
| `NumeroFactura` | texto, obligatorio | Identificador de documento en el exportador, sin pérdida de ceros. |
| `Establecimiento` | texto | Descriptivo; no forma parte de la llave TipoFactura + NumeroFactura. |
| `Factura` | texto | Segundo identificador de la factura para visualizar. |
| `FechaFactura` | `YYYY-MM-DD` | Inicio del plazo. No inventar fecha si falta. |
| `HoraFactura` | texto | Trazabilidad; no se usa para precisión horaria sin hora de despacho. |
| `CodCliente`, `Cliente` | texto | Cliente. |
| `CodProducto`, `Producto` | texto, opcional | Producto. Si no hay `CodProducto`, cada fila debe ser un consolidado único por factura/bodega, como en el archivo actualizado. |
| `CodBodega`, `Bodega` | texto | Bodega; bodega única por factura cuando no hay SKU; producto/bodega único cuando sí lo hay. |
| `CodVendedor`, `Vendedor` | texto | Responsable comercial. |
| `Cond_Entrega` | texto | Modalidad; usar el mismo vocabulario del exportador o mapearlo antes de enviar. |
| `Ciudad` | texto | Ciudad de despacho. Se normalizan mayúsculas, acentos y espacios. No se deduce de la dirección. |
| `Facturado` | número, obligatorio | Cantidad facturada de la línea. |
| `DespachoFisico` | número, obligatorio | Cantidad físicamente despachada acumulada. |
| `AjusteDevolucion` | número | Ajuste acumulado separado del movimiento físico. |
| `Despachado` | número | Total reportado de origen; en este Excel = físico + ajuste. |
| `Pendiente` | número, obligatorio | Saldo reportado. Debe conciliar con facturado menos físico y ajustes. |
| `UltimoDespacho` | `YYYY-MM-DD` o `null` | Fecha real del último movimiento físico de esa línea. Validar su significado en origen. |
| `PesoPendiente`, `CajasPendientes`, `PalletsPendientes` | número | Carga pendiente en unidades homogéneas. |
| `PesoDespacho` | número, kg | Peso despachado acumulado; indicador de toneladas despachadas. |
| `PesoFacturado` | número, kg, recomendado | Peso facturado por renglón único. Necesario para completar el indicador cuando hay ajustes o pesos faltantes. |
| `PesoAjusteDevolucion` | número, kg, opcional | Peso separado del ajuste; permite conciliar facturado = físico + pendiente + ajuste cuando faltara PesoFacturado. |
| `PalletsFacturados` | número, opcional | Pallets equivalentes facturados del renglón. Sin este campo el indicador se muestra sin dato o parcial; no se deriva de toneladas ni cantidades de productos mezclados. El cero explícito es un dato válido. |
| `Direccion`, `Comentario`, `Bloques`, `Ubicaciones`, `EstadoDespacho`, `DiasSinMovimiento`, `TienePendiente`, `PesoDespacho` | datos de origen | Trazabilidad. El estado y la antigüedad del indicador se calculan a partir de cantidades y fechas. |

No enviar números con separadores de miles. Para la API se recomiendan valores numéricos JSON y fechas ISO. Convertir timestamps a fecha local de operación (America/Guayaquil, si aplica) antes de reducirlos a fecha. No cortar la parte de fecha de un timestamp UTC sin convertir su zona.

La llave comercial es TipoFactura + NumeroFactura por compañía. Las filas que repiten su clave de detalle dentro de una extracción se consolidan sin sumar: la última aparición actualiza la anterior, por bodega en el consolidado o producto/bodega en el detalle por SKU. Se registran repeticiones y cambios. No mezclar ambos niveles en una misma factura. Si tu API admite varias líneas legítimas con esa combinación, se debe incorporar un ID estable de línea y adaptar la clave antes de usarla. Las extracciones posteriores publican una versión vigente única y conservan las anteriores como histórico fuera de los totales.

## Secuencia

1. Buscar el ID de `dispatch.source` por código y compañía. La fuente debe contener un universo independiente y completo.
2. `dispatch.source.api_start_batch([source_id], batch_key, cutoff_date)` devuelve `{id, state}`. `batch_key` debe identificar de forma estable una extracción; reutilizarlo en reintentos.
3. `dispatch.snapshot.api_append_chunk([snapshot_id], index, rows)` recibe entre 1 y 5.000 líneas, máximo 20 MiB de JSON por bloque. Los índices comienzan en cero y son consecutivos. Máximo 500.000 líneas por corte.
4. `dispatch.snapshot.api_finalize([snapshot_id], expected_chunks, expected_rows)` verifica índices y conteos y encola el trabajo.
5. Consultar `dispatch.snapshot.read` para conocer `state`, `total_rows`, `total_invoices`, `loaded_invoices` y `error_message`.

El mismo bloque con el mismo índice y contenido es idempotente. Un contenido distinto en el mismo índice se rechaza. El identificador del lote es único por fuente. No se debe modificar el archivo de extracción entre reintentos. El conector debe enviar los bloques secuencialmente.

Un lote con cero bloques y cero líneas representa deliberadamente una fuente vacía. Un corte fallido no reemplaza al vigente. Un corte de fecha anterior al vigente se archiva y no lo sustituye. Para corregir un exportador que ya quedó cerrado, generar otro identificador de lote.

## Ejemplo de envío

Configurar en el proceso de integración `ODOO_URL`, `ODOO_DB`, `ODOO_LOGIN` y `ODOO_API_KEY`; no incluir secretos en el archivo ni en un repositorio. Luego:

```bash
python3 examples/push_api.py exportacion.jsonl --company-id 1 --source-code TRANSCASH --cutoff 2026-10-29 --batch-key export-2026-10-29-01
```

Es un ejemplo de recepción listo para adaptar, no un conector ya conectado a tu sistema de origen. Para completar esa parte se necesitan URL/documentación de origen, método de autenticación, ejemplo real de respuesta, identificadores de factura/línea, política de cancelaciones y devoluciones, semántica de fechas, paginación y frecuencia deseada.
