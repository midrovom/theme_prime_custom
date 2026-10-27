# 18.0.1.4.80 — Rubro único por empresa, año y código

- Un presupuesto por empresa/año/código de rubro sin distinguir estado.
- Ejemplo 2026/Servicio básico/RUB-101: segundo presupuesto bloqueado; 2026/Transporte/RUB-102: permitido.
- Rubro en cabecera inmediatamente debajo de Año. Ya no se muestra en las líneas de Proyecciones mensuales.
- Cuentas controladas continúan filtrándose con `parent.category_id` (solo las del rubro de cabecera).
- `expense.budget.line.category_id` se conserva como campo técnico almacenado para informes y compatibilidad. Se calcula con el rubro de cabecera (y con el de la cuenta para presupuestos históricos sin rubro definido).
- No se ejecuta ninguna consulta de API en las validaciones de rubro ni en el botón Imprimir PDF.
- Conservados presupuestos y movimientos existentes. La migración quita solo restricción antigua empresa/año si siguiese presente.
- El texto «Apruébelo antes de registrar otro rubro» NO aparece en el código de esta versión. Si se sigue mostrando después de actualizar, Odoo está cargando código antiguo: comprobar `addons_path`, actualización efectiva y reinicio de todos los workers.
