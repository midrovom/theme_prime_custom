# Validación de la entrega 18.0.1.1.0

## Ejecutado

- Lectura completa del XLSX actualizado: 54.392 registros, 44.989 facturas, 383 pendientes.
- Conciliación independiente de claves, fechas y cantidades del origen.
- 39 pruebas unitarias del motor: plazos, feriados, parciales, devoluciones, saldos negativos, fechas, denominadores, granularidad por bodega y producto.
- JavaScript de la vista previa ejecutado con el conjunto completo mediante Node y un DOM mínimo: filtros, indicadores, configuración, creación de visuales y persistencia local.
- Comparación factura a factura de fecha límite, estado y días de atraso entre Python y la vista previa para 1.727 facturas Transcash (2 días hábiles, feriado 09/10/2026).
- Sintaxis Python y XML, campos de vistas, entradas del manifiesto, ACL declaradas y sintaxis JavaScript.

## Pendiente en el entorno de destino

- Instalación del módulo y ejecución de las seis pruebas de integración incluidas en una base Odoo 18 con PostgreSQL.
- Pruebas de lectura/importación con usuarios reales y aislamiento entre compañías.
- Montaje de las plantillas OWL y revisión visual en escritorio/móvil. El entorno de generación no tiene servidor Odoo ni navegador Chromium local; las pruebas JavaScript no sustituyen esas verificaciones.
- Conexión con la API origen, semántica de fechas, paginación, frecuencia y retención de cortes.

Usar primero una base de prueba. Las instrucciones y comandos están en README.md. El Excel se carga como corte completo y las importaciones se procesan en segundo plano.
