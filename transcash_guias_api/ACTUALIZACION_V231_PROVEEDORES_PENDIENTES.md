# v2.31 — Proveedores Portal visibles para Contabilidad

## Problema corregido
La preparación automática de usuarios Portal de v2.30 podía crear `res.users` sin insertar la solicitud en `transcash.acceso.proveedor`, porque el `create()` del directorio exigía el grupo de Contabilidad incluso al importador técnico.

## Corrección
- Permitir **solo al importador en sudo y con contexto restringido** crear registros `activo=False` en los directorios oficiales de proveedores y clientes; **ningún grupo funcional** se asigna durante la sincronización.
- Reconstruir solicitudes que faltan para usuarios Portal existentes asociados a un contacto de transporte de guías importadas. Excluye choferes, destinatarios y transportes provistos por cliente.
- La migración de versión v2.31 intenta la reconstrucción automáticamente. Contabilidad también dispone de **Actualizar proveedores Portal pendientes**, que abre la bandeja de los que están **Por habilitar**.
- Los nuevos registros y los existentes se ordenan con pendientes primero. Se mantienen los estados y permisos anteriores.
- Se conserva la obligación de cambiar la contraseña inicial antes de autorizar: el usuario puede entrar a `/transcash/mi-cuenta` para efectuarlo, sin obtener el grupo de transportista de forma anticipada.

## Comprobación
Instalar solo `transcash_guias_api`; actualizar desde Aplicaciones. Iniciar sesión con Contabilidad, abrir **Proveedores y acceso PWA** y ver las tarjetas **Sin acceso**. Si ya se habían creado usuarios y no aparecen, ejecutar **Actualizar proveedores Portal pendientes**; la acción reconstruye registros administrativos sin volver a crear usuarios ni contraseñas. Revisar RUC/empresa y habilitar cuando la clave inicial se haya cambiado.
