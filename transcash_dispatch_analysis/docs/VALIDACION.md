# Validación de la entrega 18.0.1.4.0

## Ejecutado en esta versión

- 90 pruebas Python sin Odoo: motor SLA, ciudades automáticas, control de importación, fórmulas de capacidad y métodos reales del servicio del tablero con un ORM de lectura en memoria.
- 12 verificaciones JavaScript de los métodos reales del componente: período aplicado, KPI de cumplimiento y toneladas, precisión decimal, subtotales parciales, destinos, envío de alcance y protección contra respuestas antiguas.
- 4 verificaciones JavaScript del recálculo interactivo, conservadas de la versión anterior.
- Lectura del XLSX vigente y cálculo completo con el lector, agregador, evaluador SLA y planificador del módulo: 54.392 registros, 44.989 facturas, 383 pendientes; Entrega Transcash: 1.727 facturas y 100 pendientes.
- Conciliación de toneladas: 1.030,61176 t en todas las modalidades y 767,22977 t en Entrega Transcash. Identificación de 14 líneas pendientes sin peso positivo en esa modalidad.
- Comprobación de capacidad suficiente para el peso conocido en cada alternativa de vehículo; ciclos enteros por horizonte, redondeos, rangos de fecha y separación de bodegas/fuentes/compañías.
- Sintaxis Python, JavaScript y XML, referencias de campos de vistas, archivos del manifiesto, 14 modelos y 24 filas de permisos declarados.

## Pendiente en el entorno Odoo

- Actualizar/instalar el módulo y ejecutar las pruebas de integración incluidas con Odoo 18 y PostgreSQL; no están ejecutadas en este entorno.
- Comprobar permisos reales, aislamiento de compañías y persistencia de valores personalizados, así como el recálculo del nuevo campo almacenado de toneladas.
- Montaje de las plantillas OWL y revisión visual en escritorio/móvil. No hay servidor Odoo ni ejecutable de Chromium local; las verificaciones de métodos JavaScript y XML no sustituyen esas pruebas.
- Validar capacidades reales, ciclos por destino y disponibilidad de flota antes de convertir un escenario en contratación.
- Conectar y verificar la API del sistema de origen cuando se reciba su contrato.

Para actualizar y usar los datos ya importados, ver PLANIFICACION_V1_4.md. El Excel se mantiene como corte completo y la pantalla conserva el procesamiento por bloques con progreso.
