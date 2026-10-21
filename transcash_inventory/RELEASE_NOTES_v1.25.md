# Transcash Inventory Inteligente v1.25 — reparación carga inicial / caché

## Defecto reproducido
Un iframe Odoo con HTML antiguo y JS nuevo puede provocar errores al escribir `innerHTML`/`hidden` en elementos inexistentes. Las versiones anteriores los etiquetaban incorrectamente como "No hay información disponible" incluso existiendo el snapshot.

## Correcciones
- Archivos de estilos/JavaScript con nombres únicos `dashboard_v125.*`: no se mezclan con el JS anterior por caché.
- Actualiza la URL del iframe en los assets OWL a v1.25.
- Valida versión de plantilla y elementos obligatorios antes del procesamiento; intenta recargar solo una vez si detecta mezcla de versiones.
- Mantiene pantalla de carga hasta que las tarjetas KPI del período por defecto se han calculado.
- Un error de un gráfico no oculta las tarjetas KPI.
- Distingue "sin importación" de un error de interfaz, API o esquema.
- Conserva barra única de filtros, todos los análisis, importación, APIs, fotos, seguridad y consultas IA.

## Verificación de la instalación
1. Respaldar PostgreSQL y filestore. Reemplazar COMPLETAMENTE carpeta `transcash_inventory`.
2. Reiniciar servicio Odoo, Actualizar módulo en Aplicaciones.
3. En navegador recargar Ctrl+Shift+R o abrir en pestaña privada.
4. Dentro del iframe, confirmar `dashboard_v125.js` y `<meta name="transcash-dashboard-version" content="18.0.1.25.0">`.
5. Confirmar que abre Resumen con 8 tarjetas y datos; cambiar período 12/6/3, categoría, marca, proveedor y formato.
6. Comprobar Datos importados antes de volver a cargar archivos; no importar por un error JavaScript.

Validado en entorno aislado de navegador y cálculos de prueba. No se ha conectado al servidor productivo.
