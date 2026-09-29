# Análisis de Comisiones — Odoo 18

Módulo independiente para Telecity orientado a controlar compras de SIM/ICC, liquidaciones de Claro, conciliación de comisiones, ROI y desempeño por región/zona.

## Corrección de compatibilidad Odoo 18
La versión 18.0.6.0.0 conserva la corrección de compatibilidad introducida en 18.0.3.0.0: el error de instalación reportado en `dashboard_views.xml`: Odoo 18 no permite llamar por RPC a un método privado (`_compute`) desde un botón `type="object"`. El botón ahora invoca el método público `action_refresh` y los cálculos internos permanecen privados.

## Flujo recomendado
1. Configurar **Operadores**. Claro viene creado con longitud de cruce ICC = 18.
2. Configurar **Regiones**, **Zonas** y **Mapeo Bodega / Zona**.
3. Crear un **Lote de Compras**, seleccionar operador y cargar `DETALLE DE COMPRAS CHIPS.XLS`.
4. Si el mapeo Bodega/Zona se modifica después, usar **Aplicar mapeo Región/Zona** en el lote de compras.
5. Crear una **Liquidación** y cargar uno o varios XLSX de Claro (P1/P2/P3, etc.) en una sola operación.
6. Configurar/activar la versión de parámetros de comisión que corresponda.
7. Cuando se cambien parámetros, usar **Recalcular** en la liquidación.
8. Revisar Dashboard, análisis de liquidaciones y **Rendimiento por Región / Zona**.

## ICC / SIMCARD
Los archivos reales entregados no usan la misma longitud:
- Compras: ICC de 18 dígitos.
- Liquidaciones analizadas: SIMCARD de 19 dígitos.

En los archivos suministrados, los primeros 18 dígitos producen 99.232 coincidencias únicas y no se detectan colisiones en la normalización. El módulo conserva siempre el ICC original y adicionalmente genera `icc_key` usando la longitud configurable del operador. No está codificado de forma rígida para futuros operadores.

## Región y zona
El archivo de compras suministrado no contiene una columna explícita de zona/región; contiene `BODEGA` y `NBODEGA`. Por eso la zona analítica se obtiene mediante la tabla editable **Mapeo Bodega / Zona**. La región enviada por Claro también se conserva como texto fuente (`Región operador`). Si el ICC comprado todavía no tiene región mapeada, esa región de Claro se usa como respaldo en el maestro de SIM; cuando se aplica después un mapeo Bodega → Región/Zona, el mapeo de Telecity tiene prioridad y puede reemplazarla.

## Parametrización de comisiones
Los parámetros se mantienen directamente en Odoo, no mediante archivos de configuración. Un esquema incluye:
- Operador y producto.
- Patrón de producto reportado por el operador.
- Vigencia desde/hasta.
- Estado Borrador / Activo / Cerrado.
- Concepto y patrón de coincidencia.
- Día de evaluación.
- Base de cálculo.
- Límite mínimo/máximo con inclusividad configurable.
- Rango sin límite superior.
- Porcentaje o valor fijo.
- Prioridad y estado de cada regla.

El botón **Duplicar esquema** crea una nueva versión con todas sus reglas para que el usuario cambie únicamente vigencia/rangos/porcentajes. El módulo impide activar dos versiones del mismo operador/producto con vigencias superpuestas.

Se incluye en borrador una plantilla Claro Prepago desde 01/09/2026 para Bono 60 y Bono 90. No se activa automáticamente. La comisión base del 20% no se precarga como regla ejecutable porque la comunicación disponible no identifica de manera suficiente el concepto exacto del archivo ni todos los criterios de elegibilidad.

## Base de costo para ROI
El archivo de compras separa `COSTO`, `DESCUENTO` e `IMPUESTO`. Para no imponer una interpretación contable única, el operador tiene el parámetro **Base de costo para ROI** con tres opciones:
- **Costo fuente**.
- **Costo - descuento**.
- **Costo - descuento + impuesto**.

Claro queda inicialmente en **Costo fuente**, preservando el criterio usado en las primeras versiones. Si Telecity decide medir el retorno sobre desembolso incluyendo impuesto, puede cambiar el parámetro y usar **Recalcular costo ROI** en el lote de compras; no hay que volver a importar archivos. Los valores fuente nunca se alteran.

En el archivo suministrado, `COSTO` suma aproximadamente USD 251.789,96, `IMPUESTO` aproximadamente USD 37.768,49 y `DESCUENTO` es 0; por tanto, costo más impuesto suma aproximadamente USD 289.558,44. La elección correcta para ROI depende del criterio financiero/tributario de Telecity.

## Porcentaje reportado por Claro
En febrero 2025 Claro exporta 20% como valor numérico `0.20`. El módulo guarda:
- `Porcentaje fuente`: 0.20, para trazabilidad.
- `Porcentaje reportado %`: 20.00, normalizado para lectura y comparación.

## Carga masiva y trazabilidad
- Múltiples archivos por una misma liquidación.
- Procesamiento por bloques de 2.000 filas.
- Búsqueda de ICC por bloque, no por fila.
- XLSX en modo `read_only`.
- Recalculo masivo mediante SQL por bloque, evitando cientos de miles de `write()` individuales.
- KPIs de SIM almacenados y actualizados en bloque después de importaciones/recalculos.
- SHA-256 para impedir importar dos veces el mismo archivo.
- Archivo y fila de origen, usuario y fecha de importación.
- El adjunto original se conserva ligado al lote y puede abrirse desde la pestaña **Archivos**.
- Validación de columnas mínimas de Claro.
- El export de compras `.XLS` recibido es realmente DBF/FoxBase; se procesa con parser incluido, sin `xlrd`.

## Dashboard ejecutivo
La portada incorpora KPI pensados para lectura inmediata del dueño del distribuidor:
- Comisión recibida, comisión esperada y pendiente potencial de Claro.
- Margen realizado, ROI realizado y ROI esperado.
- Comisión por SIM y margen neto por SIM.
- SIM monetizadas y porcentaje de monetización.
- SIM maduras, SIM maduras improductivas y porcentaje de improductividad.
- Capital maduro sin recuperar.
- SIM que ya recuperaron su costo, porcentaje de recuperación y días promedio de recuperación.
- Zona con mayor generación de comisión.
- Zona con menor generación de comisión.
- Zona con mayor ROI.
- Participación de la zona líder y concentración de las tres zonas que más generan.
- Cobertura de zona y cantidad de SIM sin zona, para evitar conclusiones territoriales sobre datos incompletos.
- Cobertura de reglas, comisión recibida sin regla y cantidad de líneas con diferencia, para saber si el cálculo esperado está suficientemente parametrizado.

El parámetro **Días para SIM madura** se configura en el operador (Claro = 90 por defecto) y se mide desde la fecha de compra. Es una alerta gerencial de antigüedad/recuperación, no una afirmación de que contractualmente ya corresponda una comisión. No altera reglas contractuales.

**Pendiente potencial de Claro** suma únicamente diferencias positivas `esperado - recibido` a nivel de línea/concepto, por lo que un sobrepago en otra línea no oculta una diferencia pendiente. Solo puede considerarse deuda cuando las reglas activas, la elegibilidad y los datos fuente estén completos y validados.

## Rendimiento territorial
El reporte **Rendimiento por Región / Zona** agrega comisión recibida, margen, ROI, comisión por SIM, margen por SIM, monetización, participación sobre la comisión de la cohorte, SIM maduras improductivas y capital maduro sin recuperar. Incluye lista, pivot y gráfico de barras por zona.

## ROI
`ROI realizado = (comisión reportada - costo compra) / costo compra × 100`

`ROI esperado = (comisión esperada - costo compra) / costo compra × 100`

El reporte **Rendimiento por Región / Zona** consolida por operador, cohorte mensual de compra, región y zona, sin duplicar el costo cuando una SIM acumula varias comisiones en diferentes períodos.

## Validación contra los archivos suministrados
Regresión verificada sobre los archivos originales usados para diseñar el módulo:
- Compras: 141.248 filas / 141.248 ICC normalizados únicos.
- Fechas de compra: 04/10/2024 a 27/12/2024.
- Costo acumulado fuente: USD 251.789,95603123598 (visual aproximado USD 251.789,96).
- Impuesto acumulado fuente: USD 37.768,49 aprox.; costo + impuesto: USD 289.558,44 aprox.
- P1+P2+P3 febrero 2025: 240.537 filas con SIMCARD / 240.537 claves normalizadas únicas.
- Valor reportado acumulado (`Valor`): USD 101.235,68 aprox.
- Cruce compra-liquidación por 18 dígitos: 99.232 ICC coincidentes.
- Compras sin aparición en esos tres archivos: 42.016 ICC.
- SIMCARD de esos archivos no presentes en el archivo de compras suministrado: 141.305.
- Conceptos históricos detectados: 30, 60, 90, 120, 150 y 180 días.
- Porcentaje fuente observado: 0 o 0,20.

Estos números son pruebas de lectura/cruce de los archivos proporcionados; no significan por sí solos deuda o incumplimiento de Claro porque falta considerar temporalidad, elegibilidad y versiones de reglas.

## Dependencias
- Odoo 18.
- Módulos Odoo: `base`, `mail`, `web`.
- Python: `openpyxl`.
- `psycopg2` ya forma parte de la pila estándar de Odoo/PostgreSQL y se usa para actualizaciones masivas.

## Instalación/actualización
1. Sustituir la carpeta anterior `commission_analysis` por esta versión.
2. Reiniciar el servicio Odoo.
3. Actualizar la lista de aplicaciones.
4. Instalar **Análisis de Comisiones** o, si ya quedó instalado en otra prueba, actualizar el módulo.
5. Probar primero en una base de pruebas antes de cargar los archivos completos en producción.

## Verificación técnica ejecutada
- Compilación de todos los Python del módulo.
- Parseo XML de todas las vistas/datos.
- Validación de `__manifest__.py`.
- Revisión de botones `type="object"`: ninguno llama métodos privados.
- Prueba del parser DBF con las 141.248 filas reales.
- Prueba de encabezados de los tres XLSX reales.
- Prueba de normalización de porcentaje 0,20 -> 20,00%.
- Prueba de cruce ICC 18/19 dígitos con los archivos reales.
- Pruebas Odoo de regresión incluidas para recalculación masiva sin reglas, mezcla de líneas con/sin regla, fecha de compensación faltante, re-vinculación tardía de ICC y vigencias históricas cerradas.
- Revisión de SQL directo con `flush_model/flush_recordset` antes de agregados/actualizaciones masivas.

El entorno de construcción no incluye un servidor Odoo 18 ejecutable ni PostgreSQL configurado, por lo que no se puede afirmar que se ejecutó una instalación end-to-end local. La corrección se hizo contra el traceback real y la documentación de Odoo 18, además de validaciones estáticas y de datos fuente.

## Recalculación y orden de carga (v18.0.6.0.0)

El flujo fue reforzado para que **Compras y Liquidaciones puedan cargarse en cualquier orden**. Al recalcular una liquidación, el módulo primero vuelve a vincular cada línea por `Operador + icc_key`, sincroniza Región/Zona desde el maestro SIM, aplica la versión de reglas vigente para la fecha de compensación y finalmente actualiza los KPI de las SIM afectadas.

La versión corrige específicamente el error PostgreSQL `column "scheme_line_id" is of type integer but expression is of type text`. Ese error aparecía cuando un bloque completo no tenía una regla aplicable (caso normal para febrero 2025 mientras no exista un esquema histórico configurado): PostgreSQL infería el `NULL` de `scheme_line_id` como texto. La actualización masiva ahora tipa explícitamente ID, importes, porcentaje y estado.

Una liquidación muestra además controles de calidad de primera vista: registros totales, ICC vinculados, ICC sin compra, líneas con regla, sin regla, datos incompletos, OK, diferencias y porcentaje de cobertura de reglas. Que un registro quede **Sin regla** no es un error técnico: significa que falta una parametrización contractual aplicable a esa fecha/concepto.

## Integridad histórica de parámetros

Las versiones activas o cerradas quedan protegidas para evitar que un cambio posterior altere una auditoría histórica. Para modificar porcentajes/rangos se usa **Duplicar esquema**, se ajusta la nueva vigencia y luego se activa. Antes de cerrar una versión se exige `Fecha hasta`; una versión cerrada continúa siendo utilizada al recalcular fechas que caen dentro de su vigencia.

Antes de activar, el módulo valida rangos superpuestos o vacíos dentro del mismo patrón/base. La longitud de normalización ICC del operador tampoco puede cambiar una vez existen datos, porque modificarla rompería los cruces históricos.

## Importación de archivos grandes (v18.0.5.0.0)

El archivo `DETALLE DE COMPRAS CHIPS.XLS` utilizado para validar este módulo no es un libro Excel: es un DBF/FoxBase con extensión `.XLS`. El archivo analizado pesa aproximadamente 110 MB y contiene 141.248 registros.

Para evitar límites de carga del navegador, proxy o servidor, el importador acepta ahora `.ZIP`. Comprima el `.XLS`/DBF y cargue el ZIP directamente; el módulo lo descomprime y procesa conservando la trazabilidad. En la muestra real de Telecity, el archivo de aproximadamente 110 MB se reduce a cerca de 1,1 MB al comprimirlo como ZIP.

También se pueden incluir varios `.XLS`/`.DBF` de compras dentro de un mismo ZIP. Para liquidaciones se admiten `.XLSX` directos o varios `.XLSX` dentro de un ZIP.

Cada archivo lógico conserva SHA-256, archivo contenedor, miembro del ZIP, tamaño, filas importadas, fecha y usuario. Un error de procesamiento se registra en el log del servidor y se presenta al usuario con el archivo que lo produjo.

### Nota sobre `navigator.clipboard.writeText`

El error de JavaScript `Cannot read properties of undefined (reading 'writeText')` pertenece al botón de copiar del diálogo de errores del cliente web y no identifica la causa del fallo de importación. En navegadores modernos la API de portapapeles puede no estar disponible cuando Odoo se abre por HTTP en lugar de un contexto seguro. Para diagnosticar una importación, use el mensaje original del diálogo o el traceback del servidor, no el error generado al pulsar el botón de copiar.
