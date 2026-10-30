# Validación de la entrega 18.0.1.6.0

## Ejecutado en 1.6

- 125 pruebas Python independientes: se añaden el caso ilustrativo de 27,95 t, agrupación por destino, restricciones por bodega, días con flota necesaria, pallets ausentes/cero/negativos, fechas de 30 días inclusivos y acciones de todos los indicadores con su lista de vistas.
- Montaje y renderizado real del componente y su XML con OWL 2.8.1 y jsdom 26.1.0: 17 verificaciones de inicialización, fechas antes de la primera consulta, cinco cuadros de carga, pallets facturados sin dato, click real en un indicador, cambio real del selector de agrupación, favoritas, períodos, análisis dinámico, manejo de errores y compilación del XML de progreso. Los servicios RPC/acciones se simulan; no equivale a una sesión completa del cliente Odoo.
- Compilación real de ambos SCSS y del conjunto con LibSass 3.6.6. Se conserva la corrección 1.5.1.
- Lectura del XLSX completo con el motor actualizado: 54.392 registros, 44.989 facturas únicas, 1.030,61176 t pendientes en todo el archivo. Las 54.392 filas carecen de PalletsFacturados y contienen PalletsPendientes. El indicador facturado se distingue como ausente.
- Rango de comprobación 30/09/2026–29/10/2026: 5.222 facturas únicas. Entrega Transcash: 55 pendientes y 620,42012 t conocidas, idénticas con salidas por bodega o agrupadas por destino. Hay seis filas pendientes sin peso válido; ambos modos conservan la advertencia parcial. Son cifras del archivo recibido con reglas de referencia, no una consulta de la base del cliente.
- Validación estática de Python, XML, vistas, permisos y manifiesto. Se incluyen pruebas nativas de actualización de pallets y acciones filtradas para ejecutarlas en Odoo.

## Validación histórica 1.5

## Corrección 1.5.1

Se reprodujo el fallo de compilación del SCSS del paquete 1.5 con LibSass 3.6.6. La corrección se conserva y se incluyen el detalle y el comprobador en CORRECCION_ESTILOS_V1_5_1.md y tests/check_styles.py. No se han compilado los demás módulos del servidor del cliente.

## Ejecutado

- 108 pruebas Python sin servidor Odoo: reglas SLA, ciudades, importaciones por bloques, deduplicación de detalles, llave TipoFactura + NumeroFactura, selección de versiones publicadas, conservación de bodegas, pesos, ciclos y métodos reales del tablero con un ORM de lectura en memoria.
- En la entrega 1.5 se ejecutaron 10 verificaciones JavaScript de bodegas múltiples, favoritos, formatos, parcialidad y auditoría. La interfaz 1.6 tiene la validación de montaje y eventos descrita arriba.
- Lectura completa del XLSX vigente: 54.392 registros, 44.989 llaves comerciales, 7.149 facturas con varias filas de bodega, 34 bodegas, cero filas idénticas y cero repeticiones factura/bodega.
- Doble carga simulada del universo completo con el selector de publicación que usa el módulo: 89.978 versiones -> 44.989 vigentes; el pendiente se conserva en 1.030,61176 t y no se duplica.
- Recorrido completo de lectura, preparación y carga con los métodos reales del modelo y ORM en memoria: 44.989 facturas, 54.392 renglones, 383 pendientes y 100 pendientes Entrega Transcash, con 73 ciudades y progreso monótono.
- Selección real de dos bodegas (AGD/CDT): se conciliaron 746,47762 t pendientes de Entrega Transcash y sus destinos, excluyendo el peso de otras bodegas.
- Sintaxis Python/JavaScript/XML, referencias de campos, archivos del manifiesto, 15 modelos y 26 filas de permisos declarados.

## Por comprobar en la base Odoo del cliente

- No se ha consultado ni modificado la base remota del cliente. La sospecha de duplicación por sus dos cargas debe comprobarse con el botón Validar / consolidar duplicados después de actualizar.
- Instalación/actualización y ejecución de las pruebas de integración nativas incluidas con Odoo 18 y PostgreSQL. Incluyen dos cargas, fuentes superpuestas, favoritos, bodegas y conversión de datos anteriores.
- Ejecución real del índice parcial único, SQL de actualización de datos previos, transacciones, concurrencia y permisos ir.filters con usuarios reales.
- Sesión completa del cliente web Odoo y revisión visual en escritorio/móvil. El montaje en DOM de OWL 1.6 se ha probado; no hay servidor Odoo ni ejecutable Chromium local.
- Capacidades reales de carga, ciclos de ruta, volumen, acceso y disponibilidad de flota antes de contratar.

Los cortes históricos se conservan como versiones explícitas fuera de los totales operativos. La entrega no afirma una limpieza ya ejecutada en el servidor del cliente. Ver UNICOS_BODEGAS_V1_5.md para actualizar y verificar esa base sin subir el Excel otra vez.
