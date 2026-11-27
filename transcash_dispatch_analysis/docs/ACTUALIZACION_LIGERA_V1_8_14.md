# Actualización ligera 18.0.1.8.14

Aplicable a instalaciones estables 18.0.1.8.10 o 18.0.1.8.13 con identidad interna intacta. Si la versión instalada es 18.0.1.8.11 o 18.0.1.8.12, la actualización se detiene antes de operar sobre las facturas: estas versiones podían fusionar documentos diferentes y hace falta recuperar o validar esos datos por separado. No desinstalar el módulo.

- No se ejecuta el UPDATE histórico de `name` de 1.8.13 ni su comprobación histórica de claves en SQL. No se crea ninguna columna nueva: se utiliza `display_name`, campo no almacenado nativo de Odoo 18. Lista, formulario, relaciones y búsquedas muestran `FAC/` seguido de la referencia externa. El tablero forma la etiqueta en memoria al consultar datos.
- Se mantienen `invoice_key`, `name` almacenado, ID, detalles, cortes, favoritos, reglas y cron. El número interno sigue siendo la identidad técnica, pues el externo puede repetirse. Los registros sin externo conservan el aviso de respaldo. La exportación explícita del campo técnico `name` puede seguir devolviendo el valor histórico; el campo `display_name` contiene la etiqueta visible.
- Los scripts de 1.8.11, 1.8.12 y 1.8.13 no están en este paquete. Es imprescindible reemplazar la carpeta completa y comprobar que no haya otra copia del módulo en `addons_path`. La antigua migración 1.7.1 solo aplica a instalaciones antiguas y está fuera de este recorrido.
- Odoo aún realiza la actualización normal de esquema, vistas y metadatos. Si falta el índice de unicidad existente, el `init()` de Odoo intentará crearlo; no se desactiva esa garantía de integridad. Las operaciones normales del cron siguen disponibles después de arrancar el servicio.

## Procedimiento
1. No repetir la actualización desde Aplicaciones mientras exista un proceso en curso. Detener Odoo de forma controlada y comprobar que no queden procesos contra la base.
2. Respaldar base y filestore; comprobar `latest_version` con `DIAGNOSTICO_ACTUALIZACION.sql`.
3. Retirar la carpeta anterior de todas las rutas de addons y colocar este paquete (no mezclar carpetas). Si 1.8.11/12 llegó a quedar instalada, recuperar la copia previa o realizar una recuperación validada antes de continuar.
4. Ejecutar desde el usuario y entorno Python del servicio, con el servicio normal detenido, adaptando rutas y base:

```
./odoo-bin -c /ruta/odoo.conf -d themeConedera -u transcash_dispatch_analysis --stop-after-init --no-http --workers=0 --max-cron-threads=0 --log-level=info
```

5. Si falla, revisar las líneas anteriores al primer ERROR, el log del servicio (reinicios, timeouts) y los logs del kernel (OOM). Consultar bloqueos desde una segunda conexión PostgreSQL con el archivo SQL indicado. No matar procesos ni borrar tablas de forma automática. Si termina con código 0, iniciar Odoo y validar los indicadores y la búsqueda por `FAC/`.

## Validación
287 pruebas independientes superadas; las nuevas pruebas incluyen la ausencia de consultas del nuevo script en actualizaciones modernas, etiquetas de registros históricos sin alterar `name`, y dos documentos con el mismo externo. Se agregó una prueba de integración nativa de Odoo no ejecutada en este entorno. No se ha medido el tiempo real de actualización en la base de producción.
