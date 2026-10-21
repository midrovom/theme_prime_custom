# Logística Transcash Odoo 18 — v5.33.0

## Diagnóstico corregido

La v5.32 contaba únicamente `transcash.embarque` en estado `ruta` o `entregado` y con fecha real de salida. No incluía guías de ERP publicadas pero sin ruta, hojas de ruta en borrador o embarques en preparación. Por tanto, el BI aparecía vacío aunque existiera operación.

## Alcance de esta versión

- Sustituye el servicio del dashboard mediante `_inherit` (`models/dashboard_v533.py`), sin cambiar estados, embarques, guías ni operaciones de contabilidad.
- El dashboard es la pantalla inicial de **Logística Transcash** y también está en **Logística Transcash > Inteligencia logística**; no aparece como aplicación independiente.
- Muestra KPIs de guías, pendientes de ruta, rutas, embarques preparados, salidas reales, entregas, kg, m², metros lineales, unidades, pallets, cajas, novedades y roturas.
- Incluye tablas reales de guías, rutas, embarques, transportistas, choferes, destinos, incidencias y liquidaciones (estas últimas **solo** para Contabilidad/Jefe Logística/Administrador).
- Marcas y proveedores de productos solo se consultan con el nuevo grupo **Analítica reservada: marcas y proveedores de productos** o Administración técnica. Se consultan preferentemente desde `tc.guide.line.private` si `transcash_guias_api` está instalado. El módulo logístico no depende formalmente del importador.
- Las pestañas usan búsquedas, ordenación, apertura de fichas y exportación XLSX con validación de permisos en servidor.
- Administradores técnicos disponen de **Diagnóstico de menús** para inspeccionar la acción/modelo de los menús activos; diagnosticar no confirma que todas las operaciones funcionen, pero ayuda a identificar configuración faltante.
- Todos los indicadores se calculan a partir de registros reales, con límites de 15000 documentos por categoría y 60000 líneas por consulta.

## Definiciones y fechas

- **Registro en Odoo** (por defecto): `create_date` de guía, ruta, embarque y liquidación; sirve para ver guías recién importadas sin esperar la salida del viaje.
- **Fecha prevista ERP**: `fecha_prevista` de la guía. Embarques y rutas se consultan por creación, ya que la fecha prevista de embarque es un compute no searchable.
- **Salida real**: `fecha_salida` de embarque para las guías asignadas, rutas y viajes; excluye por definición las guías que aún no salieron.
- **Viajes programados**: todos los embarques del periodo excepto que el usuario filtre por salida real. **Salidas reales**: embarques con fecha real de salida. No se consideran equivalentes.
- **Kg**: sumatoria de pesos de las líneas vigentes cuando tienen peso; en otro caso, peso de la guía. **m²**, **metros lineales** y **unidades** siempre se muestran separadamente.
- **Rutas en borrador**: métricas calculadas con las guías seleccionadas, aunque aún no se hayan confirmado.
- Rankings por transportista/chofer/destino: agrupan guías de la cohorte; viajes únicos pueden haber sido creados en el periodo y contener guías previas.
- Cifras por varias compañías corresponden a compañías activas autorizadas; si hay varias divisas los saldos se mantienen separados por moneda (el Excel registra moneda por liquidación).
- Tablas de documentos: hasta 300 filas; KPI calculados sobre todo el periodo dentro del límite de consulta.

## Actualización recomendada

1. Hacer respaldo de la base y del addon instalado.
2. Reemplazar solo `logistica_transcash` v5.32 por v5.33. Mantener `transcash_guias_api` v2.1 instalado y sin reemplazos; no instalar ningún módulo adicional.
3. Reiniciar Odoo y **Actualizar** la aplicación Logística Transcash, no solamente reiniciar. Confirmar en Apps la versión 18.0.5.33.0.
4. Recargar activos del navegador (Ctrl+F5 o `?debug=assets`).
5. El rol Analítica se implica a los perfiles internos de consulta/bodega/operador/jefe para que la aplicación abra correctamente. Los usuarios exclusivamente analíticos pueden acceder sin permisos de edición; datos de productos comerciales solo para grupo reservado.
6. Abrir **Inteligencia logística**, elegir fechas y 'Registro en Odoo'; probar todas las pestañas y exportar XLSX.
7. Administrador de Odoo: abrir **Diagnóstico de menús** y revisar los menús activos y accesos.

## Validación en servidor

El paquete ha pasado compilación de código Python, sintaxis JavaScript, parseo XML y validación estática de referencias de menús. **No se han ejecutado pruebas con el servidor ni los datos de producción del usuario**; para pruebas transaccionales con Odoo, ejecutar sus tests con `--test-enable -u logistica_transcash` en copia de la base.

## Nota sobre datos comerciales

La capa privada comercial permanece dentro de `transcash_guias_api`; desde el dashboard no se habilita acceso a marcas ni a proveedores de productos para choferes, proveedores de transporte, clientes, operadores o jefes logísticos.
