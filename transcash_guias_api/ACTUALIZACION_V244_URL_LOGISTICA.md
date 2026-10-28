# v2.44 — Dirección pública de la PWA: /logistica

El nombre técnico de los addons sigue siendo `logistica_transcash` y
`transcash_guias_api`. No se cambia ningún modelo, relación, permiso, registro,
correo, valor ni regla de negocio.

## Dirección nueva

- `/logistica` (entrada por perfil)
- `/logistica/operacion` (centro de operaciones)
- `/logistica/operacion/rutas` (hojas de ruta)
- `/logistica/operacion/rutas/nueva` (crear hoja de ruta)
- `/logistica/operacion/embarques/nuevo` (armar embarque)
- `/logistica/operacion/embarques/<id>` (detalle del viaje)
- `/logistica/embarques` (viajes de chofer/proveedor)
- `/logistica/guias` (guías y destinatarios)
- `/logistica/proveedor` (portal transportista)
- `/logistica/mi-cuenta` (cambiar contraseña)
- `/logistica/offline` (cola de evidencias offline)

Los endpoints `/transcash/...` existentes **continúan activos**; el navegador
reescribe enlaces internos hacia `/logistica`. El router de Odoo resuelve la
nueva ruta con el controlador original y sus políticas (permisos, CSRF y método).
Las redirecciones de los formularios conservan `/logistica`.

Las rutas técnicas `/api/transcash/v1/...`, las rutas estáticas
`/logistica_transcash/static/...` y `/transcash_guias_api/static/...` no cambian.

La PWA nueva conserva el mismo `id` del manifiesto (compatibilidad con
instalaciones anteriores), pero cambia el `start_url`, el `scope`, el service
worker y las direcciones del modo sin conexión. La base de IndexedDB y la cola
pendiente tampoco cambian.

## Instalación

1. Respaldar base y complemento; reemplazar únicamente `transcash_guias_api`.
2. Reiniciar Odoo, actualizar el complemento desde Aplicaciones.
3. Cerrar y volver a abrir la PWA; entrar en `http(s)://SERVIDOR/logistica`.
4. Renovar accesos directos del navegador si todavía abren una dirección
   antigua. En PWA instaladas que conserven el inicio antiguo, abrir primero
   `/logistica` desde el navegador o actualizar/reinstalar el acceso directo
   **después de sincronizar las evidencias pendientes**.
5. Probar navegación por perfil, guardar guías, crear ruta, enviar evidencia,
   cambiar contraseña, cerrar sesión, y sincronizar offline.

**Nota:** los Service Workers y el almacenamiento offline fiable requieren
HTTPS o un origen seguro autorizado por el navegador; el cambio de URL no
suprime esa limitación del navegador.

## Verificación local

Pruebas unitarias aisladas sobre redirecciones, nombres de ruta, la
identidad y el alcance del manifiesto, contenidos del service worker y
shell offline. Sintaxis Python, JS, XML y paquete ZIP. Sin servidor Odoo
real no se puede afirmar que la integración de producción ya pasó.
