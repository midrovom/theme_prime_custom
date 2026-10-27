# Versión 18.0.1.4.75 — sincronización histórica de consumos

El cron activo de cinco horas (y los botones «Sincronizar») consultan `getconsumosgastos/2` una sola vez por empresa/ejecución e importan todas las fechas contenidas en la respuesta, sin filtrar por el año en curso. Continúa sincronizando cuentas, centros y subcentros.

## Movimientos existentes y duplicados

- Se conserva el formato de `source_key` que utilizaba 18.0.1.4.74 y la restricción SQL `unique(company_id, source_key)`. Los registros ya importados no se vuelven a crear.
- Cuando el ERP trae `id`, `external_id` o `id_movimiento` estable, esa clave permite actualizar importe, fecha, cuenta, centro, subcentro y la vinculación presupuestaria; si no hay cambios, el registro no se reescribe.
- Si la respuesta incluye dos filas con **el mismo identificador externo**, prevalece la última fila. Se indica cuántas repeticiones llegaron en el log.
- Si el ERP **no trae identificador**, se utiliza la huella previa calculada por cuenta, centro, subcentro, fecha, importe y ordinal de repetición. Es idempotente con respuestas de contenido idéntico, pero **no puede distinguir con certeza una rectificación de una transacción nueva cuando varían fecha/importe**. Para soportar rectificaciones confiables hace falta un ID estable proporcionado por el ERP.
- No se eliminan movimientos que ya están guardados aunque no aparezcan en una ejecución posterior del endpoint.

## Asignación a presupuesto y rendimiento

- La búsqueda de proyecciones usa empresa, **año**, cuenta, centro y mes. El subcentro sigue siendo dato de trazabilidad, tal como en la versión anterior.
- Si no hay presupuesto, el gasto se guarda en Gastos reales sin línea y podrá reconciliarse cuando se cree su proyección.
- Para una empresa se hace una sola llamada al endpoint de consumos. Los registros se consultan en grupos y se crean por lotes. En la primera ejecución histórica el volumen importado puede ser mucho mayor que en la sincronización habitual del año actual.
- Los logs de sincronización histórica tienen el campo `year` vacío y un resumen `años=...` en el detalle. La comprobación de historial reciente al guardar líneas acepta esa marca global y evita recargar el mismo endpoint.

## Instalación

1. Hacer respaldo de la base y del módulo instalado.
2. Reemplazar `expense_budget_control` por el contenido del ZIP y actualizar la aplicación en Odoo 18 (`-u expense_budget_control` o desde Aplicaciones).
3. Ejecutar manualmente «Presupuestos: cuentas, centros y consumos ERP (5 horas)» una vez, o pulsar «Sincronizar», para cargar años antiguos.
4. Revisar en Gastos reales los movimientos por año y el Historial de sincronización (insertados, actualizados y sin cambios).

Pruebas realizadas antes de entrega: comprobación de sintaxis Python y estructura ZIP. Las pruebas de integración requieren una instalación de Odoo 18 y una base de datos de pruebas con la API configurada.
