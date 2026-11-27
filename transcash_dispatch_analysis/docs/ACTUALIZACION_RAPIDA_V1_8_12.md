# 18.0.1.8.12 — Actualización de identidad externa sin reconstrucción masiva

La migración original 18.0.1.8.11 eliminaba las facturas de todos los cortes
ready/archived y recreaba sus cabeceras, líneas y relaciones por ORM, en una
transacción de actualización. Con muchos cortes puede superar los recursos o
límites del servidor. La versión 18.0.1.8.12 sustituye **los scripts originales
ubicados en migrations/18.0.1.8.11**, de modo que una actualización fallida
pueda volver a ejecutarlos desde la última versión instalada. Una instalación
que ya completó 18.0.1.8.11 no debe repetir la conversión.

La nueva migración cambia las claves y nombres mediante SQL por bloques,
conservando cabeceras, líneas y parámetros de cortes sin conflictos. Recalcula
solamente los grupos que se fusionan, se dividen o no coinciden con el original.
Detecta colisiones por corte y valores externos distintos en sus líneas. Si el
corte registraba duplicados y conserva el original, comprueba también si se
perdieron agrupaciones en la deduplicación anterior. Si no hay original, se
utiliza el detalle almacenado; no es posible recuperar filas descartadas que ya
no existen. No consulta la API durante la conversión. Los lotes parciales se
reinician en cola y el proceso de importación existente hace su limpieza.
La selección de la última versión vigente por empresa y clave se calcula en SQL.
Se conserva una única transacción, sin commits intermedios.

## Procedimiento recomendado

1. Confirmar que no quede una actualización anterior ejecutándose. No lanzar
   otra actualización simultánea. Detener todos los procesos Odoo conectados a
   esa base (incluidos los cron) mediante el procedimiento normal del servidor.
2. Realizar una copia de seguridad de PostgreSQL y del filestore. Reemplazar el
   directorio completo del módulo, no superponer archivos de versiones distintas.
3. Ejecutar desde consola con el mismo usuario, configuración, entorno Python y
   rutas de addons del servicio (adaptar las rutas y el nombre de base):

   ```bash
   ./odoo-bin -c /ruta/odoo.conf -d NOMBRE_BASE -u transcash_dispatch_analysis --stop-after-init --no-http --workers=0 --max-cron-threads=0
   ```

4. Comprobar el código de salida y el registro de Odoo. Para una conversión desde
   18.0.1.8.10 se registran mensajes por corte: `Despachos: corte ...: ... facturas,
   ... grupos recalculados`. Debe aparecer `Despachos: conversión externa finalizada`.
   Si ya se instaló 18.0.1.8.11, esos mensajes no son necesarios.
5. Si termina correctamente, iniciar el servicio normal y recargar el navegador.
   No desinstalar el módulo ni eliminar los cortes. Si vuelve a fallar, conservar
   el traceback y los mensajes anteriores al fallo para diagnóstico. No modificar
   manualmente la versión registrada ni las claves de facturas.

El tiempo depende de la cantidad de cortes, líneas, duplicados y capacidad de
PostgreSQL. Incluso el SQL puede tardar y bloquear escrituras durante la
transacción. Se recomienda probar primero con una copia de producción. No se
ha ejecutado la migración en un servidor Odoo/PostgreSQL real en este entorno.
