# Versión 18.0.1.4.93 — prorrateo exacto y limpieza de vistas

- Vista de lista: se oculta «Meses pendientes» únicamente en esa lista; el campo técnico y el seguimiento en formulario se mantienen.
- Formulario: se elimina la explicación bajo «Agregar / Eliminar».
- Distribución: se calcula en unidades de la precisión presupuestaria (2, 4, 6 u 8 decimales). Los residuos se reparten cronológicamente entre las mensualidades y el total coincide con el objetivo anual.
- Ejemplo: 1400 entre 12 meses, precisión 2 => 8 meses de 116,67 y 4 de 116,66 (total 1400,00). Para 1300: 4 meses de 108,34 y 8 de 108,33 (total 1300,00).
- Migración 1.4.93: se revisan SOLO objetivos completos de presupuestos en borrador, sin meses aprobados o pendientes. Los presupuestos aprobados o enviados no se modifican, por seguridad contable.
- Se conserva la sincronización de gastos, los importes aprobados, los reportes existentes y la estructura del presupuesto.
