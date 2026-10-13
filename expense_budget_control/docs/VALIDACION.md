# Verificación técnica del módulo

Validación estática realizada para el entregable de Odoo 18:

- **Python:** los archivos `.py` compilan con `compileall`.
- **XML:** todos los documentos se analizan con `lxml.etree.parse`.
- **Manifest:** las rutas declaradas en `data` existen y están ordenadas para resolver seguridad, vistas, acciones y menús.
- **Referencias:** los IDs internos de menús, acciones, grupos y modelos son coherentes.
- **Seguridad:** 13 reglas de acceso a modelos; reglas de empresa para los modelos persistentes con datos empresariales.
- **Plantilla:** se confirma la apertura del libro XLSX con las hojas `Cuentas`, `Proyecciones` y `Gastos`.
- **Parseadores:** fechas, importes con separador decimal español/inglés, normalización de encabezados y rechazo de montos no finitos.
- **Vistas Odoo 18:** se utiliza `<list>` y `view_mode="list,form"`, no `<tree>`.
- **Reporte PDF:** se comprobaron sintácticamente la plantilla QWeb, acción `ir.actions.report`, formato A1 horizontal y su botón `action_print_annual_pdf`.
- **Agrupación:** prueba aislada de rubros, cuentas, los doce meses, subtotales de gasto/proyección, porcentajes de ejecución y meses sin proyección.
- **Pruebas Odoo:** se añadió un caso para comprobar la estructura del informe y que el botón devuelve una acción `qweb-pdf`.

## Prueba en una instalación real

La comprobación estática **no sustituye** la validación al instalar Odoo. No estaba disponible un servidor Odoo 18 en el entorno de construcción y no se adjuntó el módulo `api_administator` instalado. En un staging Odoo 18 instale primero la dependencia y valide:

1. Instalación sin errores de registro/ACL y correcta apertura de menús.
2. Importar `Cuentas`, crear el presupuesto 2026, importar `Proyecciones` e importar `Gastos`.
3. Corroborar montos y pivot por rubro/mes.
4. Reimportar los mismos gastos: no se crean duplicados.
5. Configurar una API de gastos GET con `status = A`, confirmar que `call_api` devuelve la estructura JSON esperada y ejecutar sincronización.
6. Validar permisos del grupo lector y del administrador con varias compañías.
7. Imprimir PDF desde un presupuesto anual con rubros **Servicios básicos / Luz / Agua**: comprobar agrupación, subtotales, títulos mensuales y doce meses en una sola tabla y porcentaje total anual, así como la columna de ejecución sin rótulo.
8. Activar el cron solo después de una sincronización manual satisfactoria.

## Particularidades de la dependencia externa

Se asumieron los nombres técnicos compartidos en el ejemplo: modelo `api.administrator`, campos `name`, `type`, `status`, `url`, `end_point`, `user_id`, `password`, `company_id`, método `call_api(...)` y botón `button_run_sync()`. Si el addon real difiere, solo deberá adaptarse la integración específica en `models/api_sync.py` y/o `views/expense_budget_api_views.xml`.
