# Logística Transcash V4.2.0 — Activación, roles y vista de escritorio

## Qué corrige

Esta versión sustituye la V4.1.1 sin cambiar el nombre técnico `logistica_transcash` y conserva seguimiento, evidencias, roturas por producto, notas de crédito, PWA y cola offline. Se incorporan:

1. **Directorio de choferes en Odoo** en **Logística Transcash → Choferes y acceso móvil**.
2. Un botón **Habilitar acceso de chofer** para agregar el grupo de Portal Transcash a una cuenta Portal existente.
3. Un botón **Deshabilitar acceso** que revoca ese grupo sin borrar la cuenta ni sus evidencias anteriores.
4. **Vista adaptativa de escritorio** en la misma ruta `/transcash/guias`: menú lateral, fichas en múltiples columnas, buscador local por guía/origen/destino, formularios modales centrados. En móvil mantiene los controles, navegación inferior y el comportamiento PWA.
5. **Migración de choferes ya asignados** al actualizar desde V4.1.x (solo usuarios de tipo Portal).
6. Validación del grupo de chofer en el servidor para los accesos y operaciones de transporte.

## Instalación segura en servidor propio

**No desinstalar** el complemento existente, porque podría borrar datos. Realizar un respaldo de base de datos y filestore **antes** de actualizar.

1. Extraiga el ZIP: contiene una única carpeta `logistica_transcash`.
2. Reemplace la carpeta anterior de su `addons_path` por la V4.2.0. El directorio de addons debe contener `logistica_transcash/__manifest__.py`.
3. Reinicie el servicio que realmente usa en su VPS (`odoo18`, `odoo`, Docker, etc.).
4. Acceda con el administrador a **Aplicaciones → Actualizar lista de aplicaciones** y, después, abra el módulo **Transcash - Seguimiento de Guias → Actualizar**. La versión debe ser `18.0.4.2.0`.
5. Si administra Odoo por consola, la operación equivalente es ejecutar la actualización del módulo en la base correcta, p. ej. `odoo-bin -c /etc/odoo18.conf -d NOMBRE_BD -u logistica_transcash --stop-after-init` con el usuario de servicio y rutas apropiadas. Haga esto en una ventana de mantenimiento y solo si conoce la instalación.
6. Desde el navegador, abra `https://SU_DOMINIO/transcash/guias`. En escritorio (>=1024 px) verá el nuevo espacio de trabajo; en teléfono verá la PWA tradicional.
7. En teléfonos con la V4.1.1 instalada, cierre/reabra la PWA con Internet para que el service worker descargue `v4.2`. Si persiste el diseño anterior, recargue con conexión. **No borre datos de sitio ni reinstale la PWA si tiene evidencias pendientes sin sincronizar**.

## Cómo dar acceso a un chofer

**Paso A — Crear la cuenta de acceso Portal**

En **Contactos**, cree o abra al chofer con correo válido, guarde y use **Acción → Otorgar acceso al portal**. Es importante que sea un usuario externo **Portal**, no un usuario interno Odoo. La contraseña se establece con la invitación normal del portal.

**Paso B — Activar el perfil en Transcash**

Inicie sesión con un usuario interno que tenga el grupo **Administrador de logística**. Abra **Logística Transcash → Choferes y acceso móvil → Nuevo**. Seleccione el **Usuario de portal**, opcionalmente la empresa de transporte, guarde y pulse **Habilitar acceso de chofer**. En la ficha debe verse `Acceso chofer habilitado = Sí`.

Si la lista de choferes no aparece, compruebe que el administrador tiene el rol de Administrador de logística, no solo acceso de consulta. El grupo técnico `Chofer - WebApp móvil` puede no verse en la vista predeterminada de grupos porque Odoo filtra grupos de tipo compartido/portal; use **Choferes y acceso móvil**.

**Paso C — Asignación por guía**

Abra **Logística Transcash → Todas las guías → Intervinientes**. En **Usuario chofer**, seleccione **exactamente la misma cuenta Portal** y guarde. El chofer entra con esa cuenta en `/transcash/guias` y solo ve las guías asignadas.

**Paso D — Probar carga, ruta y roturas**

1. Bodega cambia la guía de Registrada a **En embarque**.
2. Chofer abre la guía y pulsa **Registrar evidencia / rotura**. Carga fotografías o videos de carga, o registra una rotura por producto y cantidad, adjuntando evidencia.
3. Bodega revisa y aprueba la evidencia de embarque. Al autorizar salida, pasa a **En ruta**.
4. El chofer documenta novedades, confirma llegada y registra descarga según el estado.
5. El destinatario acepta u objeta las evidencias de llegada.
6. Sin conexión, los archivos y observaciones pueden quedar en el teléfono y sincronizarse cuando regrese la red. Compruebe la bandeja **Pendientes** antes de borrar datos del dispositivo.

**Importante:** El perfil Administrador de logística no reemplaza al usuario Chofer en la interfaz móvil. Para capturar medios operativos, inicie sesión con la cuenta Portal del chofer asignado.

## Permisos importantes

- **Chofer:** grupo `group_transcash_chofer` **y** asignación de la guía. No tiene acceso al backend ni a Contabilidad.
- **Destinatario:** ve el flujo permitido para sus guías; puede actuar únicamente en recepción, objeciones y evidencias propias.
- **Vendedor:** registra roturas por producto en guías de su compañía.
- **Administrador de ventas / Aprobador de NC / Crédito y cobranzas / Contabilidad:** mantienen la separación de responsabilidades de V4.
- **Administrador de logística:** administra los choferes, coordina la operación. No recibe automáticamente los botones de captura del chofer.

## Aspectos técnicos

- Ruta principal (móvil y escritorio): `/transcash/guias`.
- Ruta offline: `/transcash/offline`.
- Manifest PWA: `/transcash/manifest.webmanifest`.
- Service worker: `/transcash/sw.js`.
- Módulo: `logistica_transcash`, versión `18.0.4.2.0`.
- Grupo técnico del chofer: `logistica_transcash.group_transcash_chofer` (grupo portal/compartido).
- Modelo administrativo del directorio: `transcash.chofer`.
- Migración automática para usuarios Portal anteriormente asignados: `migrations/18.0.4.2.0/post-driver-accounts.py`.

## Verificación y limitaciones

El paquete fue revisado de manera estática: sintaxis Python/JavaScript, XML, manifiesto e integridad ZIP; además se renderizó una vista previa HTML a resoluciones de escritorio y teléfono. **No se instaló ni ejecutó contra una instancia real de Odoo 18**. Primero pruébelo en una copia de la base antes de usarlo en producción.

Si Odoo arroja un error al actualizar, recupere la **primera excepción del log de Odoo** y no continúe borrando el módulo o sus tablas.
