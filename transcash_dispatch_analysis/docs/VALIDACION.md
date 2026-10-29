# Validación de la entrega 18.0.1.5.0

## Ejecutado

- 108 pruebas Python sin servidor Odoo: reglas SLA, ciudades, importaciones por bloques, deduplicación de detalles, llave TipoFactura + NumeroFactura, selección de versiones publicadas, conservación de bodegas, pesos, ciclos y métodos reales del tablero con un ORM de lectura en memoria.
- 10 verificaciones JavaScript nuevas de los métodos reales del componente: bodegas múltiples, favoritos mediante los servicios del módulo, formatos de toneladas, parcialidad del peso facturado y auditoría. También pasan las 12 verificaciones del tablero anterior.
- Lectura completa del XLSX vigente: 54.392 registros, 44.989 llaves comerciales, 7.149 facturas con varias filas de bodega, 34 bodegas, cero filas idénticas y cero repeticiones factura/bodega.
- Doble carga simulada del universo completo con el selector de publicación que usa el módulo: 89.978 versiones -> 44.989 vigentes; el pendiente se conserva en 1.030,61176 t y no se duplica.
- Recorrido completo de lectura, preparación y carga con los métodos reales del modelo y ORM en memoria: 44.989 facturas, 54.392 renglones, 383 pendientes y 100 pendientes Entrega Transcash, con 73 ciudades y progreso monótono.
- Selección real de dos bodegas (AGD/CDT): se conciliaron 746,47762 t pendientes de Entrega Transcash y sus destinos, excluyendo el peso de otras bodegas.
- Sintaxis Python/JavaScript/XML, referencias de campos, archivos del manifiesto, 15 modelos y 26 filas de permisos declarados.

## Por comprobar en la base Odoo del cliente

- No se ha consultado ni modificado la base remota del cliente. La sospecha de duplicación por sus dos cargas debe comprobarse con el botón Validar / consolidar duplicados después de actualizar.
- Instalación/actualización y ejecución de las pruebas de integración nativas incluidas con Odoo 18 y PostgreSQL. Incluyen dos cargas, fuentes superpuestas, favoritos, bodegas y conversión de datos anteriores.
- Ejecución real del índice parcial único, SQL de actualización de datos previos, transacciones, concurrencia y permisos ir.filters con usuarios reales.
- Montaje OWL y revisión visual en escritorio/móvil. No hay servidor Odoo ni ejecutable Chromium local. Las pruebas de métodos y XML no sustituyen esas verificaciones.
- Capacidades reales de carga, ciclos de ruta, volumen, acceso y disponibilidad de flota antes de contratar.

Los cortes históricos se conservan como versiones explícitas fuera de los totales operativos. La entrega no afirma una limpieza ya ejecutada en el servidor del cliente. Ver UNICOS_BODEGAS_V1_5.md para actualizar y verificar esa base sin subir el Excel otra vez.
