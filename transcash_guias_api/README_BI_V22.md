# Transcash BI v2.2 — Dashboard único (módulo `transcash_guias_api`)

## Qué cambia
- Se conserva **sin cambios** el código del módulo principal `logistica_transcash`, v5.32 o v5.33.
- El complemento reutiliza el XMLID `logistica_transcash.action_transcash_dashboard` y el único menú existente `logistica_transcash.menu_transcash_dashboard`.
- La acción pasa a la nueva etiqueta de cliente `tc_logistica_bi_v22` y consulta el servicio **`tc.logistica.bi.service`**.
- El código del dashboard anterior puede permanecer instalado como legado, pero ya no es el tablero que abre el menú. No se crea otro dashboard en el menú ni otro icono de aplicación.

## Datos / definiciones
- Fuentes reales: `transcash.guia`, `transcash.guia.linea` (líneas vigentes), `transcash.hoja.ruta`, `transcash.embarque`, `transcash.rotura` y `transcash.pago.liquidacion` (solo autorizados).
- Novedad = guía con `incidencia_estado != 'ninguna'` o recepción `con_novedades` o reporte no rechazado.
- Roturas = **cantidad de reportes** `transcash.rotura` cuyo estado no sea `rechazada`, no guías afectadas.
- Guías con roturas = guías únicas que tienen al menos un reporte no rechazado.
- Cantidad dañada se separa por `m2` y `unidad` de la línea reportada, sin sumar magnitudes incompatibles.
- Proveedor en rankings = **empresa transportista** `guia.proveedor_id`, no proveedor de producto.
- Traslado planificado ≠ salida real: KPI separados.
- Fuente multiempresa: `env.companies` del usuario autenticado, filtro aplicado antes de `sudo`.
- Datos de marca y proveedor de producto: exclusivamente `base.group_system` o `group_tc_sync_admin`.
- Datos financieros: exclusivamente contabilidad, jefe logística o sistemas.
- Excluye reportes de daños rechazados en KPI y comparaciones.
- Los detalles en pantalla se limitan a 300 fichas por sección; los totales suman todo el universo filtrado (hasta topes de 15.000 guías y 60.000 líneas).

## Instalación/actualización
1. Respalda la base de datos y la carpeta del módulo.
2. Mantén instalado **logistica_transcash** tal como está, no reemplaces ese módulo.
3. Reemplaza exclusivamente `transcash_guias_api` con esta versión, reinicia Odoo y actualiza la app.
4. Recarga el navegador con Ctrl+F5, después abre **Logística Transcash → Inteligencia logística**.
5. Selecciona fechas incluyendo los datos importados y el tipo de fecha **Registro en Odoo**.
6. Verifica la pestaña **Choferes**, **Transportistas**, **Destinos**, **Incidencias**, y la exportación a Excel.
7. Si actualizas `logistica_transcash` en el futuro, actualiza luego `transcash_guias_api` para reestablecer la redirección de la acción.

## Si el dashboard muestra cero
- Comprueba que existan guías en `transcash.guia` (no solo en `tc.guide`).
- Revisa el rango de fechas y el tipo seleccionado (registro vs salida real).
- Comprueba que las guías tengan chofer, transportista, destino y que los reportes de rotura estén registrados en `transcash.rotura`.
- Si faltan enlaces, primero ejecuta **Conciliar terceros y portales**; no hagas correcciones directas a movimientos históricos.
- El tablero cuenta sólo roturas reportadas; un producto faltante no se contabiliza como rotura hasta documentarlo.

## Pruebas antes de producción
- Abrir el dashboard con rol Logística y verificar que no aparezcan proveedores de producto ni montos financieros no autorizados.
- Abrir con rol Contabilidad y comprobar la sección de liquidaciones.
- Abrir con usuario Portal y confirmar que no accede al dashboard.
- Crear un reporte de rotura de prueba en una guía de prueba, comparar suma de reportes por transportista/chofer/destino y comprobar valores de m².
- Desplazar hasta el final con rueda del mouse y móvil; comprobar encabezados en tablas largas.
- Exportar detalle y el informe completo, contrastar cifras con las vistas de Odoo.

**Validación externa pendiente:** las verificaciones del código no sustituyen una prueba real en la base Odoo/ PostgreSQL instalada.
