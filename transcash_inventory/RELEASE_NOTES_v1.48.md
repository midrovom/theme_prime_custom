# v1.48 — Recuperación automática de miniaturas, multiempresa

### Problema confirmado
La reparación individual en v1.47 sí funciona; el cron combinado anterior
solo inspeccionaba 35 registros y reparaba un máximo de 3 por empresa cada
15 minutos, por lo que la recuperación masiva parecía no ejecutarse.

### Solución
- Acción programada independiente: **TRANSCASH: Recuperar miniaturas faltantes automáticamente**.
  Frecuencia: cada 2 minutos (el servidor debe tener `ir.cron` activo).
- Inspecciona hasta **180 fotos verificadas** por empresa activa en cada turno,
  usando un cursor persistente y rotación de hasta cuatro empresas.
- Detecta binarios JPEG ausentes/dañados y conserva SKU, URL y ficha originales.
- Prioriza recuperar desde la URL ya vinculada, y procesa lotes acotados por
  tiempo (máximo 45 segundos aprox.) y cantidad (hasta 16 por ejecución).
- Evita descargas de miniaturas válidas, aplica reintentos graduados y conserva
  el aislamiento de datos por empresa.
- Reutiliza una sola lectura del inventario por lote/empresa para reducir carga.
- El cron anterior de indexación de páginas sigue activo cada 15 minutos,
  separado del cron de reparación para no duplicar los intentos.
- El botón manual v1.47 continúa funcionando de forma idéntica.
- No se alteran snapshots, integración API, ABC/XYZ, IA, roles, filtros, diseño
  móvil, visualización HTML, ni endpoints de fotografías.

### Instalación
1. Respaldar PostgreSQL y filestore antes del despliegue.
2. Actualizar **transcash_inventory** sobre v1.47 (no desinstalar).
3. En modo desarrollador comprobar en Ajustes > Técnico > Automatización >
   Acciones planificadas que está **activa** la nueva tarea y que el servicio
   de cron de Odoo funciona. Para acelerar la prueba inicial, un administrador
   puede usar **Ejecutar manualmente** una única vez; no requiere actuar por SKU.
4. El avance es gradual. Refrescar la página para ver miniaturas recuperadas.

**No es posible ejecutar un cron en Odoo si la instalación está configurada con
max_cron_threads=0 o el servicio encargado de tareas programadas no funciona.**
