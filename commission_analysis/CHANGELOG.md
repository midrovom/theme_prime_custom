# Changelog

## 18.0.6.0.0
- Corrige el `DatatypeMismatch` de PostgreSQL al recalcular liquidaciones sin regla aplicable: `scheme_line_id` se tipa explícitamente como `integer` en `execute_values`.
- El botón **Recalcular** vuelve a vincular ICC/SIM por operador + `icc_key` antes de calcular, por lo que el orden Compras/Liquidaciones ya no deja registros permanentemente como “ICC sin compra”.
- Al importar compras se vinculan y recalculan automáticamente liquidaciones previamente cargadas para las SIM afectadas.
- Sincronización de Región/Zona de las liquidaciones con el maestro SIM después de aplicar mapeos.
- Versiones de esquemas cerradas siguen participando en recalculaciones históricas dentro de su vigencia; cerrar una versión exige `Fecha hasta`.
- Reglas y campos críticos de una versión activa/cerrada quedan bloqueados; los cambios se realizan mediante **Duplicar esquema**.
- Validación de rangos superpuestos/vacíos antes de activar un esquema.
- Estadísticas de liquidación: ICC vinculados, ICC sin compra, con regla, sin regla, datos incompletos, OK, diferencias y cobertura de reglas.
- Protección para no cambiar la longitud de normalización ICC cuando el operador ya tiene datos históricos.
- Identificador de fila fuente reforzado con hash corto para admitir archivos distintos con el mismo nombre.
- Parser DBF conserva enteros en campos numéricos sin decimales y sincroniza los datos maestros de la SIM desde la compra más antigua.
- XLSX se cierra explícitamente después de procesar para reducir recursos en cargas múltiples.
- Índice compuesto `(operator_id, icc_key)` en detalle de liquidación para acelerar re-vinculación masiva.
- Pruebas Odoo de regresión para recalcular sin reglas, mezclar líneas con/sin regla, detectar fechas faltantes, vincular compras cargadas después y conservar esquemas históricos cerrados.
- `flush_model/flush_recordset` antes de SQL directo para evitar lecturas obsoletas de campos ORM pendientes.
- El adjunto original de importación se reasigna al lote y queda visible desde la pestaña Archivos para preservar auditoría tras la limpieza del wizard transitorio.

## 18.0.5.0.0
- Importador reforzado para archivos grandes.
- Compras y liquidaciones pueden cargarse dentro de archivos ZIP; un ZIP puede contener múltiples fuentes.
- Trazabilidad de archivo contenedor, miembro ZIP, tamaño y SHA-256 del archivo lógico.
- Mensajes de error de importación legibles con nombre del archivo y detalle técnico en log.
- Protección frente a ZIP cifrado y límites de descompresión para evitar cargas accidentales excesivas.
- Recomendación integrada en el wizard para comprimir el DBF/XLS de compras antes de subirlo.

## 18.0.4.0.0
- Dashboard ejecutivo ampliado con margen por SIM, comisión por SIM, recuperación, maduración y capital sin recuperar.
- KPI “Pendiente potencial de Claro” sin compensar faltantes con sobrepagos de otras líneas.
- KPI territorial: zona que más genera, zona que menos genera y zona con mayor ROI.
- Participación de la zona líder y concentración Top 3 de zonas.
- Cobertura de mapeo territorial: SIM sin zona y porcentaje con zona asignada.
- Parámetro configurable por operador para días de madurez de SIM.
- Base de costo de ROI configurable y recalculable sin reimportar.
- Región fuente de Claro como respaldo cuando el ICC aún no tiene región mapeada.
- Reporte Región/Zona enriquecido con participación, comisión/margen por SIM, improductividad y capital maduro sin recuperar.
- Cobertura de reglas y cantidad de líneas con diferencia.

## 18.0.3.0.0
- Corrige instalación Odoo 18: botón del dashboard ya no llama `_compute` (método privado).
- Dashboard con método RPC público `action_refresh` y filtro por operador.
- ICC normalizable por longitud configurable de operador (Claro = 18).
- Operador agregado a lotes de compra y maestro de SIM.
- Mapeo Bodega -> Región/Zona reaplicable después de la carga.
- Porcentaje fuente y porcentaje normalizado separados.
- Recalculo masivo de liquidaciones mediante SQL por bloque.
- KPIs de SIM almacenados y refrescados masivamente.
- Patrón de producto y límites inclusivos/exclusivos parametrizables.
- Prevención de esquemas activos con vigencias superpuestas.
