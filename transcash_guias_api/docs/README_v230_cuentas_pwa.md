# Transcash Guías API v2.30 — Preparación de cuentas Portal y Mi cuenta

## Alcance

- Solo se modifica el addon `transcash_guias_api`. Se conserva `logistica_transcash` v5.32.
- Durante la reconciliación de una guía, utiliza los contactos ya homologados por identificación.
- Para transportistas y destinatarios con identificación válida genera una cuenta Portal si no existe; **no** asigna grupos funcionales de proveedor o cliente ni restablece contraseñas de usuarios ya existentes.
- Los proveedores quedan en `transcash.acceso.proveedor` como `activo=False` (solo Contabilidad puede habilitar). Los destinatarios quedan en `transcash.acceso.cliente` como `activo=False` (solo el jefe de Logística puede habilitar).
- No habilita acceso de proveedor pagable a contactos genéricos **Transporte proporcionado por cliente**.
- No crea usuarios a partir de códigos internos de destinatario, por ejemplo `-NAJ`, si el contacto no tiene identificación fiscal/extranjera.
- No prepara una segunda cuenta cuando el documento pertenece a un usuario existente en otro contacto; deja una observación para revisión.
- No mezcla roles de cliente, proveedor y chofer; no convierte usuarios internos a Portal.

## Contraseñas

Se implementó el requisito inicial de **login = identificación**, **clave temporal = identificación**, solo para cuentas nuevas. Este esquema es predecible, por lo que se exige cambiar la contraseña temporal (mínimo 12 caracteres) antes de autorizar el perfil de proveedor o destinatario. La contraseña se establece mediante Odoo (hash nativo) y no se registra en el log. Se recomienda HTTPS, política de intentos y, a mediano plazo, sustituir esta credencial por invitación temporal aleatoria.

Las cuentas existentes (incluidos los choferes de versiones anteriores) nunca ven modificadas sus contraseñas o permisos. La PWA muestra **Mi cuenta → Cambiar contraseña** y **Cerrar sesión** para todos los perfiles. El cambio exige la contraseña vigente, usa `res.users.change_password` y formulario con CSRF. No se guardan claves en JavaScript o en cookies propias del addon.

## Cómo actualizar

1. Respaldar PostgreSQL y la carpeta `transcash_guias_api` actual.
2. Instalar la carpeta del ZIP **sin agregar un módulo nuevo**.
3. Reiniciar Odoo y actualizar `transcash_guias_api` desde Aplicaciones.
4. En **Guías importadas ERP**, ejecutar **Conciliar terceros y portales** para que los terceros que ya existen reciban cuentas pendientes. También se procesa automáticamente en próximas sincronizaciones de `getguiaslogistica`.
5. Entrar a Logística Transcash → **Proveedores y acceso a liquidaciones** con el usuario de Contabilidad, o **Clientes y acceso PWA** con jefe de Logística. Filtrar **Por habilitar**. Validar identidad; el usuario debe cambiar su contraseña temporal, y luego el autorizador pulsa **Habilitar acceso**.
6. Con una cuenta Portal nueva, entrar a `/transcash`, abrir **Mi cuenta**, cambiar contraseña y volver a iniciar sesión si el sistema lo solicita. Validar **Cerrar sesión** en móvil.
7. Verificar que una segunda sincronización conserve un solo usuario y una sola solicitud por contacto + compañía.

## Advertencias de operación

- La PWA de un proveedor transportista solo debe mostrar viajes de su empresa y liquidaciones correspondientes, conforme a los filtros de `logistica_transcash`.
- El acceso del destinatario se limita a sus guías y evidencias autorizadas.
- Los proveedores de productos y marcas comerciales no son transportistas; no reciben cuentas mediante esta funcionalidad.
- Para terceros con RUC/cédula repetida pero vinculada a diferentes `res.partner`, no se realiza fusión automática; debe depurarse la identidad manualmente.
- En empresas con un representante distinto de la persona jurídica (y correo para invitación), se recomienda utilizar un contacto hijo autorizado en lugar de compartir la cuenta de la empresa entre varios empleados.
- El cambio de contraseña inicial es requerido antes de habilitar **nuevos** proveedores/destinatarios; las cuentas históricas conservan sus estados.

## Pruebas

Se incluye `docs/test_portal_accounts_v230.py`, que realiza pruebas locales con dobles de base de datos: creación inicial, idempotencia, prevención de login duplicado, alta pendiente, y rechazo del destinatario sin identificación. Estas pruebas NO son una instalación real de Odoo ni sustituyen pruebas por rol en una base de ensayo.
