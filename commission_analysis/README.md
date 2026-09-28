# Análisis de Comisiones — Odoo 18

Módulo independiente para Telecity orientado a controlar compras de SIM/ICC, liquidaciones de Claro, conciliación de comisiones, ROI y desempeño por región/zona.

## Flujo
1. Configurar Regiones, Zonas y **Mapeo Bodega / Zona**.
2. Crear un lote de compras y cargar el archivo `DETALLE DE COMPRAS CHIPS.XLS` (el export recibido tiene estructura DBF/FoxBase aunque su extensión sea XLS).
3. Crear una liquidación Claro y cargar uno o varios XLSX (P1/P2/P3, etc.) en una sola operación.
4. Revisar conciliación y, cuando se cambien parámetros, usar **Recalcular** en la liquidación.
5. Revisar Dashboard, análisis de liquidaciones y **ROI por Región / Zona**.

## ICC / SIMCARD
Los archivos reales entregados no usan la misma longitud de ICC: Compras contiene ICC de 18 dígitos y las liquidaciones analizadas contienen SIMCARD de 19 dígitos. En la muestra real, los primeros 18 dígitos permiten 99.232 coincidencias y no se detectaron colisiones entre SIMCARD de 19 dígitos al normalizar a 18. Por ello el módulo conserva el ICC original y usa adicionalmente `icc_key` (18 primeros dígitos numéricos) para conciliación.

## Parametrización
Las reglas se mantienen en Odoo, no por archivos. Un esquema tiene vigencia y líneas con concepto/patrón, día de evaluación, base, rango, porcentaje/valor fijo, prioridad y estado. El botón **Duplicar esquema** permite crear una nueva versión rápidamente.

Se incluye en borrador una plantilla Claro Prepago desde 01/09/2026 para Bono 60 y Bono 90. No se activa automáticamente. La comisión base del 20% no se precarga como regla ejecutable porque la comunicación disponible no identifica de forma suficiente el concepto exacto en el archivo ni todos los criterios de elegibilidad. Tampoco se inventa una regla de Bono 90 para consumos inferiores a USD 4,00, ya que el documento no la especifica.

## Carga masiva y trazabilidad
- Creación ORM por lotes de 1.000 registros.
- Búsqueda de ICC por lote, no fila por fila.
- Lectura XLSX en `read_only`.
- Hash SHA-256 para impedir importar dos veces el mismo archivo.
- Archivo, fila de origen, usuario y fecha de importación.
- Restricción de fila fuente duplicada dentro del lote/liquidación.
- Validación de columnas mínimas de archivos Claro.

## ROI
`ROI realizado = (comisión reportada - costo compra) / costo compra × 100`

`ROI esperado = (comisión esperada - costo compra) / costo compra × 100`

El reporte **ROI por Región / Zona** consolida por cohorte mensual de compra y evita duplicar el costo cuando una SIM tiene varias comisiones.

## Validación realizada con los archivos suministrados
- Compras: 141.248 ICC únicos; costo acumulado aproximado USD 251.789,96.
- Liquidaciones febrero 2025 P1+P2+P3: 240.537 filas con SIMCARD y 240.537 SIMCARD distintos; valor reportado acumulado aproximado USD 101.235,68.
- Región informada por Claro en esos archivos: COSTA.
- Conceptos históricos presentes: 30, 60, 90, 120, 150 y 180 días.
- Porcentaje histórico observado: 0 o 0,20 en los archivos de febrero 2025. El módulo conserva el valor tal como viene de Claro.
- Cruce literal 18 vs 19 dígitos: 0 coincidencias; cruce por clave normalizada de 18 dígitos: 99.232 coincidencias. Esta diferencia fue incorporada al diseño.

## Dependencia
Python `openpyxl` para XLSX. El archivo de compras DBF se lee con el parser incluido y no requiere xlrd.

## Verificación técnica
Se verificó compilación Python de todos los archivos y sintaxis XML. El entorno de construcción no contiene un servidor Odoo 18 ejecutable, por lo que la instalación/upgrade final debe validarse en una base de pruebas Odoo 18 antes de producción.
