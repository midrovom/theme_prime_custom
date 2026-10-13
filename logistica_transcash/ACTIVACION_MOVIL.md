# Transcash V4.1 — Activar WebApp móvil y usuarios chofer en Odoo 18

**Versión:** 18.0.4.1.0. **Alcance:** corrige la facilidad de acceso/configuración de la V4. **Estado:** revisión sintáctica, sin prueba en una instancia Odoo 18; instalar primero en staging.

## 1. ¿Dónde está la WebApp?

Con el addon `logistica_transcash` correctamente instalado, la dirección es:

`https://DOMINIO-DE-TU-ODOO/transcash/guias`

Es una **PWA de portal**, no una pantalla del cliente web estándar. El chofer (usuario Portal) debe entrar **directamente por el navegador del celular**, no por el backend de Odoo. La nueva V4.1 agrega **Logística Transcash → Abrir WebApp móvil** para usuarios internos autorizados. Ese acceso abre la misma URL en otra pestaña para que el personal pueda visualizarla. No crea un menú del backend para usuarios Portal.

- Android Chrome: menú ⋮ → «Instalar aplicación» / «Añadir a pantalla de inicio» según navegador.
- iPhone Safari: compartir → «Añadir a pantalla de inicio».
- Servidor con HTTPS válido. No usar la app de Odoo de App Store o Play Store para probar esta PWA; entrar desde navegador.

La primera apertura y la visita inicial a **cada guía** requieren Internet para guardar los datos offline. Una guía no preparada previamente no será consultable sin señal.

## 2. Crear el chofer: dos operaciones distintas

1. En Odoo, **Contactos → Nuevo**, crear un contacto con su nombre y correo individual. Guardar.
2. Contacto → **Acción → Otorgar acceso al portal** → activar «En Portal» → Aplicar. Enviar invitación al usuario para definir contraseña. Verificar que aparece como *Usuario Portal*, **no usuario interno**.
3. **Opcional pero recomendado en V4.1:** activar modo desarrollador en Odoo, ir a **Ajustes → Usuarios y empresas → Grupos**, localizar **«Chofer - WebApp móvil»** dentro de los grupos de portal/compartidos y añadir ese usuario como miembro. **Este grupo identifica el perfil** para administración; **no da permisos sobre documentos del backend** y no reemplaza la asignación de la guía.
4. Ir a **Logística Transcash → Todas las guías**, abrir una guía, en «Intervinientes» seleccionar **Usuario chofer = usuario Portal creado**. Guardar. El dato es `transcash.guia.chofer_usuario_id`.
5. Un usuario de Bodega debe pulsar **Iniciar embarque** cuando esté registrada, dejándola en estado «En embarque».
6. Desde el teléfono, el chofer inicia sesión en `https://DOMINIO-DE-TU-ODOO/transcash/guias`. Solo verá sus guías asignadas. Abre la guía para evidenciar carga. Bodega revisa la evidencia y autoriza la salida; luego el chofer documenta ruta y llegada.

**Importante:** el grupo «Chofer - WebApp móvil» **no es requisito técnico** para la versión V4/V4.1: la autenticación y el permiso operativo se controlan por ser usuario Portal y estar asignado como «Usuario chofer» en la guía. Se añade para que el perfil sea identificable en la administración. Los permisos se siguen comprobando en el servidor.

## 3. Ejemplo de prueba de principio a fin

1. Crear chofer piloto `chofer.piloto@ejemplo.com`, activar Portal e iniciar sesión una vez.
2. Asignar a una guía de prueba con productos y bodega.
3. Responsable de bodega: **Iniciar embarque**.
4. Chofer: ingresar a `/transcash/guias` y abrir la guía. Verá **Productos**, **Evidencias**, **Roturas**, **Historial**; subir 1 foto desde **Evidencias → Carga**.
5. Bodega: abrir **Aprobar evidencias de carga**, aprobar evidencia y luego **Autorizar salida**.
6. Chofer: confirmar llegada desde la guía, dejar fotos/video de descarga.
7. Destinatario portal: entrar a la misma webapp, visualizar el ciclo y registrar aceptación o roturas en recepción.
8. Sin conexión: preparar previamente la guía en el celular, activar modo avión, registrar una foto y verificarla en **Pendientes**; recuperar señal, usar **Sincronizar** y comprobar que cambia a recibido por servidor.

## 4. Diagnóstico rápido

- **404 en `/transcash/guias`:** módulo no instalado/actualizado correctamente, controladores no cargados, módulo no está en `addons_path`, o servidor sin reiniciar. Revisar el log de Odoo y actualizar lista de aplicaciones. Instalar solamente la carpeta `logistica_transcash`, no el ZIP entero como un único archivo dentro de `addons_path`.
- **Redirección a `/web/login`:** falta iniciar sesión con la cuenta de chofer; verificar credenciales/portal.
- **Acceso denegado:** verificar usuario Portal válido y empresa/guía vinculada; revisar logs para encontrar si se trata de permisos. No dar permisos de Administrador para «solucionarlo».
- **«Sin guías por ahora»:** campo «Usuario chofer» sin asignar o vinculado a otra cuenta; verificar login exacto. Las guías del ERP también pueden asignarse por el campo API `chofer_login` (debe existir el usuario antes).
- **Guía visible sin botón de fotos:** verificar estado «En embarque», «En ruta» o «En destino» según tipo; la guía debe admitir carga de evidencia en esa etapa y sesión debe pertenecer al chofer asignado.
- **Página sin diseño:** comprobar que `/logistica_transcash/static/src/css/mobile.css` responde y que no hay bloqueadores de scripts/CSP/proxy.
- **No sale «Instalar aplicación»:** usar HTTPS, Chrome/Safari actualizados y abrir `/transcash/guias` (no `/web`); verificar que `/transcash/manifest.webmanifest` y `/transcash/sw.js` devuelven 200, y revisar consola de navegador.
- **No sincroniza offline:** primero abrir una guía con señal para guardar su ficha local; confirmar espacio libre del teléfono, permisos de almacenamiento, sesión activa y la bandeja «Pendientes»; en iPhone con PWA cerrada no se garantiza transferencia en segundo plano.
- **No aparece menú nuevo:** debe instalarse/actualizarse **V4.1**, reiniciarse Odoo y actualizar el módulo; el menú solo será visible a usuarios internos autorizados, **nunca** como menú de backend de un usuario Portal.

## 5. Actualización técnica de V4 a V4.1

1. Respaldar base de datos, filestore y addon actual; probar primero en una copia staging.
2. Descomprimir `logistica_transcash_odoo18_v4_1_acceso_movil.zip`. Copiar la carpeta **`logistica_transcash`** a un directorio de `addons_path`, reemplazando los archivos V4.
3. Reiniciar Odoo y activar modo desarrollador.
4. **Aplicaciones → Actualizar lista de aplicaciones** (si hiciera falta); buscar «Transcash - Seguimiento de Guias» y pulsar **Actualizar** (no instalar otro módulo con nombre distinto).
5. Verificar la nueva opción **Logística Transcash → Abrir WebApp móvil** y que exista el grupo **Chofer - WebApp móvil** en Ajustes → Usuarios y empresas → Grupos.
6. Validar recorrido end-to-end con un usuario **Portal** de prueba antes de habilitarlo a producción.

**Alcance de los cambios de V4.1:** se incorporan un grupo de perfil Chofer para administración (compartido/portal), un enlace `ir.actions.act_url` y un menú del backend hacia `/transcash/guias`. No se han cambiado las reglas de negocio, autenticación, permisos de guía ni subida reanudable de V4. No se ha probado la ejecución en Odoo real; la creación de perfiles, permisos, vistas y redireccionamientos debe validarse en staging.
