# TRANSCASH V5.8 — Contrato único ERP → Odoo 18 y dashboard operativo

## 1. Una sola API para guías y datos analíticos

**Endpoint vigente:** `POST https://TU-ODOO/api/transcash/v1/guias`

Cabeceras:

```http
Authorization: Bearer TOKEN_ENTRANTE_CONFIGURADO
Content-Type: application/json
```

**Cuerpo JSON:** un objeto con la propiedad `guias`, que contiene una o varias guías. Este endpoint ya existe en Transcash V5.7 y se conserva en V5.8. Los datos de analítica se envían en la **misma guía**, no en un servicio separado. Véase `TRANSCASH_V58_API_GUIAS_COMPLETA_EJEMPLO.json`.

El contrato propuesto se formaliza con `TRANSCASH_V58_API_GUIAS_JSON_SCHEMA.json`. **Nota:** el esquema es una validación estricta recomendada para el ERP emisor; el controlador actual de Transcash exige técnicamente menos campos, aunque la analítica necesita el conjunto completo para dar resultados confiables.

### 1.1 Cabecera de la guía

| Campo JSON | Tipo | Obligatoriedad de negocio | Uso |
|---|---|---|---|
| `id_externo` | string | Imprescindible | ID estable y único ERP de la guía. No cambiar en reenvíos. |
| `numero_guia` | string | Imprescindible | Número comercial visible. |
| `tipo_documento` | string | Sí | Factura, guía de remisión, transferencia, etc. |
| `numero_documento` | string | Sí | Número completo del documento transportado. |
| `estado_erp` | string | Opcional | Estado **informativo** en el ERP; no modifica estados operativos de Odoo. |
| `chofer_login` | string | Sí | Login exacto del usuario Portal Chofer existente en Odoo. |
| `ruc_chofer` | string | Sí | RUC/identificación, conservar como cadena. |
| `proveedor_codigo` | string | Sí | Código de la empresa de transporte, igual a **Referencia interna** del contacto Odoo. |
| `remitente_codigo` | string | Sí | Referencia interna de bodega/remitente en Odoo. |
| `destinatario_codigo` | string | Sí | Referencia interna del destinatario en Odoo; limita consulta del cliente. |
| `placa` | string | Sí | Placa del vehículo; usada en validaciones de embarque. |
| `direccion_origen` | string | Sí | Dirección completa de recogida. |
| `direccion_destino` | string | Sí | Dirección de entrega. |
| `destino_codigo` | string | Sí | Código estable del destino, p. ej. EC-UIO-CENTRO. |
| `destino_ciudad` | string | Sí | Ciudad destino normalizada. |
| `destino_provincia` | string | Sí | Provincia de destino normalizada. |
| `fecha_inicio_traslado` | ISO 8601 | Sí | Inicio previsto por el ERP, siempre con zona horaria. |
| `fecha_fin_traslado` | ISO 8601 | Sí | Fin previsto por el ERP, siempre con zona horaria. |
| `fecha_prevista` | ISO 8601 | Opcional | Fecha/hora estimada de llegada; con zona horaria. |
| `descripcion_carga` | string | Opcional | Comentario descriptivo general. |
| `bultos` | int >= 0 | Recomendado | Total informativo declarado en guía. |
| `peso_kg` | number >= 0 | Sí | Peso **total de la guía** en kg. |
| `productos` | array | Sí | Una o más líneas de mercancía. |

### 1.2 Producto / línea de guía

| Campo JSON | Tipo | Uso |
|---|---|---|
| `id_linea` | string | Identidad ERP **única dentro de la guía**. Reutilizar al actualizar. |
| `sku` | string | Código del producto. |
| `descripcion` | string | Descripción comercial. |
| `cantidad` | number > 0 | Cantidad transportada en la UDM indicada. |
| `unidad` | string | `m2`, `metro`, `unidad`, `kg`, `pallet`, `caja`. |
| `peso_kg` | number >= 0 | **Peso total de esa línea**, no peso por unidad. |
| `pallets` | number >= 0 | Conversión informativa del ERP, no reemplaza la UDM principal. |
| `cajas` | number >= 0 | Conversión informativa del ERP, no reemplaza la UDM principal. |
| `precio_unitario` | number >= 0 | Referencia económica para valoración del reclamo; opcional. No es el costo del flete. |
| `marca_codigo` | string | Código estable de marca para rankings. |
| `marca_nombre` | string | Nombre visible de la marca. |
| `proveedor_producto_codigo` | string | Código estable del fabricante/proveedor de ese SKU. |
| `proveedor_producto_nombre` | string | Nombre visible. **Distinto del proveedor de transporte**. |

El dashboard suma **pesos por línea** cuando están informados; si no, usa el peso total de cabecera. Para evitar cifras ambiguas, el ERP debe informar pesos completos y consistentes en todas las líneas de cada guía. Nunca se suman metros cuadrados con unidades, pallets o cajas. Las roturas se registran **en Transcash** por SKU, vinculadas a evidencias; no hace falta incluirlas como atributos iniciales del ERP.

### 1.3 Reglas de actualización y seguridad

1. Reenviar una guía con el mismo `id_externo` actualiza su cabecera y sus líneas por `id_linea` (operación idempotente). Nunca reusar un identificador de otra guía.
2. El ERP debe registrar previamente los contactos (Referencia interna) y el usuario Portal del chofer en Odoo. El endpoint **no crea automáticamente** usuarios ni contactos a partir de nombres.
3. Una vez integrada en un embarque, cambiar chofer, empresa o placa por API se rechaza. Productos con roturas o guías ya aprobadas tienen restricciones de edición.
4. La empresa de transporte y el chofer pueden compartir varias guías; **no envíes el ID del embarque**: el chofer lo crea después en la PWA.
5. `fecha_inicio_traslado` y `fecha_fin_traslado` son fechas ERP de planificación. La salida real, llegada, cierre del chofer y confirmación del cliente son eventos propios de Transcash.
6. No envíes valor del flete o liquidación en este contrato: el **jefe de Logística** negocia/aprueba ese valor por embarque.
7. No envíes estados de entrega (`entregado`, `en_ruta`) para sustituir los estados Transcash; `estado_erp` es únicamente informativo.
8. Recomendación operativa: lotes de máximo **500 guías**, máximo **300 productos por guía**, cuerpo de petición máximo **5 MB** (límites existentes).
9. Cada guía procesa su propio resultado; la respuesta será HTTP 200 o 207 con `creadas`, `actualizadas` y lista `errores` por índice de la guía. Revisa los errores incluso si otras guías del lote se importaron correctamente.
10. Usar HTTPS y un Bearer token exclusivo de integración con rotación de credenciales. No incluir token en capturas, tickets ni repositorios.

Ejemplo de llamada:

```bash
curl -X POST 'https://TU-ODOO/api/transcash/v1/guias' \
  -H 'Authorization: Bearer TU_TOKEN' \
  -H 'Content-Type: application/json' \
  --data-binary @TRANSCASH_V58_API_GUIAS_COMPLETA_EJEMPLO.json
```

Respuesta de ejemplo:

```json
{"creadas": 2, "actualizadas": 0, "errores": []}
```

*Es un ejemplo de formato de respuesta, no una importación real ejecutada.*

## 2. Dashboard al estilo del HTML recibido

El archivo `Transcash_Dashboard_Interactivo.html` entregado como referencia tiene una navegación izquierda oscura, cabecera clara, tarjetas KPI, filtros globales, gráficos de barras y tablas ordenables. V5.8 adapta **ese lenguaje visual** a los indicadores reales de logística; no importa datos de inventario ni reproduce los cálculos de compras del archivo.

**Nuevo dashboard:** `Logística Transcash → Transcash · Indicadores`, con acceso reservado al grupo **Analítica: consultar dashboard logístico**. Secciones: Resumen, Transportistas, Choferes, Destinos, Marcas y Proveedores de productos. Fechas y frecuencia (día/semana/mes), búsqueda y ordenación de tablas. Cada tabla permite exportar a **Excel `.xlsx`**; hay además un botón para descargar varias hojas con todo el informe y sus KPI. El servidor vuelve a validar grupo de seguridad, rango de fechas y compañías del usuario para cada exportación. Las hojas reflejan la búsqueda/ordenación local en exportación de una tabla.

La exportación utiliza `xlsxwriter` en el entorno Python del servidor Odoo. Si la dependencia no está disponible, debe instalarse en el virtualenv de Odoo según la política de despliegue del VPS. El Excel exporta el **ranking disponible** del dashboard (actualmente limitado a 30 resultados por dimensión), no un volcado de todas las guías.

**Limitaciones metodológicas:** viajes únicos se cuentan por embarque; un embarque multidestino cuenta en cada destino al hacer rankings pero solo una vez en los KPI de viajes. Tasas de incidencia por guía para comparación entre empresas y choferes. Peso dañado en kg = estimación proporcional a la cantidad dañada de cada línea. El dashboard no presenta saldos financieros ni datos privados de clientes al nivel de detalle de guía.

## 3. Instalación sobre V5.7

1. Hacer respaldo de PostgreSQL, filestore y directorio del addon.
2. Descomprimir `logistica_transcash_odoo18_v5_8_dashboard_excel.zip` y sustituir la carpeta `logistica_transcash` anterior (sin desinstalar).
3. Reiniciar el servicio Odoo. Comprobar que `xlsxwriter` está instalado en el virtualenv si se usarán exportaciones Excel.
4. En Odoo: **Aplicaciones → Transcash - Seguimiento de Guías → Actualizar** en modo desarrollador.
5. Abrir el dashboard y probar permisos, filtros, exportación y varias guías con productos de marcas diferentes.
6. Probar el JSON de ejemplo en una base **de pruebas** tras crear previamente los contactos y usuarios con los códigos indicados; no ejecutar ese ejemplo directamente contra producción.

El código y el esquema se han revisado estáticamente. **La importación real de guías, el render OWL del dashboard y la exportación Excel deben probarse en un Odoo 18 de prueba antes de producción.**
