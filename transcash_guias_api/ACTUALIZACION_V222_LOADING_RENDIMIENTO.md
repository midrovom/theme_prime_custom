# Logística Transcash – API v2.22: PWA responsiva y guardado optimizado

Actualización incremental basada en `transcash_guias_api` v2.21. No modifica `logistica_transcash`.

## Cambios

- Loader compartido para las páginas PWA que incluyen `logistica_transcash.mobile_head`.
- Indicador circular y barra **indeterminada** (no muestra porcentajes inventados).
- Mensaje específico para selección de guías, confirmación de rutas, envío de archivos,
  embarques, aprobación y navegación. La confirmación de éxito/error la proporciona Odoo
  después de procesar la petición; el loader no afirma éxito anticipado.
- El primer formulario nativo se envía normalmente. Se bloquea un segundo `submit`
  hasta navegar y se restablece el estado al restaurar la página desde el historial.
- El atributo `name/value` del botón submit y el token CSRF se conservan: **no** se
  deshabilita el botón antes de la serialización de datos.
- Formularios de evidencia que implementan guardado offline mediante IndexedDB
  mantienen su mecanismo actual: la nueva rutina respeta `event.preventDefault()`.
- En `route_pwa_strict.py`:
  - Se reutilizan los resultados de las comprobaciones por destino/chofer/proveedor;
    ya no se vuelve a ejecutar `_match` para los mismos tres criterios en el barrido.
  - Caché por solicitud para búsquedas de coincidencia por nombre del transportista
    cuando no llega RUC y se requiere una comprobación inequívoca.
  - La tarjeta del chofer ya no construye tablas que la vista PWA eliminó en v2.17.
  - Se agrupan actualizaciones idénticas de relaciones operativas en `write` del ORM.
  - Si el usuario guarda una selección idéntica, no se reescribe el M2M.
  - Se mantiene mensaje de trazabilidad individual al homologar relaciones.

## Instalación

1. Hacer respaldo de PostgreSQL y de la carpeta `transcash_guias_api`.
2. Reemplazar exclusivamente `transcash_guias_api` por esta carpeta; mantener
   `logistica_transcash` y API Administrator como están.
3. Reiniciar el servicio Odoo, actualizar el addon `transcash_guias_api`.
4. Recargar la PWA (en PWA instalada, cerrar y reabrir; en navegador `Ctrl+F5`).
5. Probar con un operador de logística: abrir ruta borrador, marcar guías,
   guardar, observar el indicador y verificar que se guarde **una sola selección**.
6. Repetir con conexión lenta desde herramientas de desarrollo y con evidencias,
   chofer, proveedor, cliente y responsable de fletes.

## Verificación de velocidad

El código no establece tiempos de procesamiento garantizados. Si aún hay demora,
medir separadamente el POST `/transcash/operacion/rutas/<id>/guias` y el GET
`/transcash/operacion/rutas/<id>` de la redirección, consultando tiempos de
Odoo y PostgreSQL. No se ha probado contra la base de producción del usuario.

## Seguridad / funcionalidad

Se mantienen el máximo de 100 guías, la concurrencia con bloqueo SQL, la
verificación triple transportista-chofer-destino, el token CSRF, los estados de
ruta y las restricciones financieras por perfil.
