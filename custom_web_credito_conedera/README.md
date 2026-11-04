# Portal de Solicitudes de Crédito CONEDERA - Odoo 18

Módulo nuevo e independiente de los módulos de Recursos Humanos utilizados como referencia.

## Funcionalidades incluidas

- La entrada **Solicitar crédito** abre el login nativo de Odoo con retorno al formulario de crédito. Los usuarios de portal ya autenticados van directamente al formulario.
- El registro utiliza la pantalla nativa `/web/signup` de Odoo. Tras enviar el formulario, el usuario verifica el código OTP y solo entonces se activa la cuenta mediante `res.users.signup()` de `auth_signup` y un token firmado nativo generado por el contacto; no se usa `res.users.create()` ni un modelo paralelo de cuentas.
- El acceso público de **Solicitar crédito** conduce primero a `/web/login` nativo de Odoo. Desde el propio login, el visitante puede abrir el registro nativo `/web/signup`.
- Código de verificación OTP de seis dígitos enviado por correo; vence en 3 minutos y limita los intentos de validación.
- La cuenta nativa de Odoo se crea únicamente después de validar el código. Luego se solicita iniciar sesión en `/web/login` y el acceso por defecto redirige a `/my/credito/nueva`.
- Formulario web con los campos de la página 1 del PDF: propietario/representante, tipo de solicitante configurable, negocio, datos económicos, relación de dependencia y referencias comerciales, personales y bancarias ampliables desde tres líneas iniciales.
- En Datos del negocio o empresa, las dos cédulas de Personas autorizadas (comprar y retirar mercadería) se validan primero con el algoritmo ecuatoriano; si falla, se acepta un documento extranjero de exactamente 10 dígitos numéricos. Se comprueba en el portal, el controlador y el modelo Odoo.
- Historial personal de solicitudes y detalle con etapas visibles para el cliente.
- Kanban interno por etapas para arrastrar solicitudes y avanzar el proceso. Los cambios se registran en la línea de tiempo y generan intento de notificación por correo al solicitante.
- La etapa **Aprobada** habilita la carga documental. El tipo de solicitante configurado en Odoo determina los documentos y sus requisitos obligatorios.
- Gestión de la documentación recibida y controles para aceptar el expediente o pedir correcciones.
- El croquis y los datos de verificación de ubicación NO se piden al crear la solicitud ni al corregir el formulario de cinco pasos. Cuando una solicitud llega a En revisión y todavía no tiene el croquis con dirección, el historial muestra solamente **Subir croquis**. Se abre un formulario independiente con ubicación y archivo (imagen/PDF con vista previa). Al guardar los datos dentro del expediente existente, el botón regresa a **Ver detalle**. La inspección y sus resultados permanecen en Odoo para el personal CONEDERA.
- Se notifica a `cobranzas@viteltek.com` la latitud y longitud ingresadas del negocio, sin generar ni almacenar enlaces de Google Maps.

## Documentos posteriores a la aprobación

### Persona natural

1. Solicitud de crédito preparada y firmada.
2. RUC actualizado.
3. Cédula a color del cliente; cédula del cónyuge cuando se haya indicado cónyuge en la solicitud.
4. Certificado de votación vigente del cliente.
5. Planilla de servicio básico del local y del lugar de residencia.
6. Fotografías interna y externa del local.
7. Fotografía del solicitante firmando, con el rostro claramente visible.

### Persona jurídica

1. Solicitud de crédito preparada y firmada por el representante legal.
2. RUC actualizado.
3. Cédula a color del representante legal.
4. Certificado de votación vigente del representante legal.
5. Planilla de servicio básico del local y del lugar de residencia.
6. Nombramiento del representante legal.
7. Fotografías interna y externa del local.
8. Fotografía del solicitante firmando, con el rostro claramente visible.

Documentos administrativos aceptan PDF/JPG/PNG; los tres campos de fotografía aceptan JPG/PNG. El límite aplicado por archivo en el portal es 12 MB.

## Etapas iniciales

1. Recibida
2. En revisión
3. Aprobada
4. Documentación recibida
5. Verificación
6. Finalizada
7. Denegada

Las etapas se pueden administrar desde **Crédito CONEDERA → Etapas del flujo**. La etapa aprobada activa la carga documental y la etapa denegada la oculta/bloquea.

## Instalación

1. Copiar `custom_web_credito_conedera` en el directorio de addons personalizados de Odoo 18.
2. Reiniciar el servicio de Odoo.
3. Actualizar la lista de aplicaciones.
4. Si el módulo ya estaba instalado, usar **Actualizar / Upgrade** para aplicar los campos y las vistas nuevas; si es una instalación nueva, instalar **Portal de Solicitudes de Crédito CONEDERA**.
5. Asignar a los usuarios internos que administrarán el flujo el grupo **Gestión de solicitudes de crédito CONEDERA**.
6. Configurar un servidor SMTP saliente en Odoo y un correo de compañía o remitente predeterminado; es necesario para enviar códigos OTP y avisos de etapa.

## Seguridad y notas

- El usuario del portal solo puede consultar los registros enlazados a su propio usuario; las rutas verifican propiedad antes de leer una solicitud o cargar archivos.
- Los accesos de backend y las etapas están restringidos al grupo interno del módulo.
- La ubicación y el croquis son completados por el cliente. Los usuarios de crédito los consultan sin poder modificarlos; las evaluaciones y resultados de la inspección se registran solo en Odoo. El portal conserva latitud y longitud y el botón de geolocalización sujeto a permisos/HTTPS.
- La declaración/autorización del formulario web sigue el texto de la solicitud PDF entregada. Por tratarse de una autorización legal de crédito, el área legal de CONEDERA debe validar la versión web antes de producción.
- Este paquete se validó estáticamente (estructura, XML y sintaxis Python). No se ejecutó contra una instancia real de Odoo ni se verificó el SMTP, por lo que se recomienda instalar primero en una base de pruebas.


### Ajustes de registro y aceptación documental
- El registro reutiliza el formulario nativo de Odoo y la casilla única **Acepto términos y condiciones** que aporta `custom_web_hr_datos_candidatos`; no agrega una segunda aceptación de tratamiento de datos.
- Al pulsar **Registrarse**, se envía automáticamente el primer código y se abre un modal para ingresarlo. El contador tiene una vigencia de 3 minutos; al llegar a cero aparece **Reenviar código** y solo ese clic envía un código nuevo e invalida el anterior.
- La cuenta de `res.users` se crea después de validar un código vigente. El servidor también valida que se haya aceptado la casilla de términos y condiciones.
- Antes de enviar la solicitud, el cliente debe aceptar por separado las cláusulas sugeridas sobre relación comercial previa, citación telemática, consulta de score crediticio por cualquier plataforma o buró de crédito autorizado, firma/sello de CONEDERA y documentos financieros adicionales.
- La aceptación de documentos financieros adicionales sigue siendo una casilla de la solicitud; los comprobantes de IVA, renta y certificado bancario ahora solo se solicitan si el administrador los agrega como requisitos en el catálogo de documentos del tipo de solicitante. Los archivos de versiones antiguas no se eliminan.
- La autorización para consulta de score/historial se muestra como bloque independiente y no identifica a un proveedor específico.


### Integración con el usuario nativo de Odoo
- La cuenta se crea con el mecanismo `res.users.signup()` de `auth_signup`, usando un token firmado nativo generado para el contacto que se vinculará a la cuenta. La creación del contacto y del usuario ocurre en un `savepoint`; si falla el registro nativo, se revierte la operación para no dejar contactos huérfanos.
- No se crea un modelo personalizado de usuarios ni un segundo usuario de portal. La solicitud de crédito se vincula al `res.users` autenticado. Como en Odoo estándar, cada usuario tiene su contacto `res.partner` asociado.
- El menú público **Solicitar crédito** abre `/web/login?redirect=/my/credito/nueva`. Las rutas antiguas de registro y las pantallas de verificación sin una sesión pendiente también devuelven al login, no al registro.


## Corrección 18.0.1.0.3

La versión 18.0.1.0.6 envía al usuario al login de forma predeterminada, valida la casilla de términos antes de comprobar si el correo ya existe y verifica en el servidor que la aceptación esté registrada en la sesión antes de completar el alta.



## Configuración del correo SMTP de crédito

En Ajustes > Técnico > Correo > Servidores de correo saliente, marque el servidor SMTP correspondiente con la casilla **Correo de crédito**. Configure su usuario SMTP (`smtp_user`) y deje marcada esa opción en un único servidor. Los códigos OTP de registro, las notificaciones de etapas y el aviso de ubicación de negocio enviados por este módulo usan ese servidor explícitamente y establecen `email_from` con su `smtp_user`. El servidor marcado **Correo de Reclutamiento** por el módulo `custom_web_hr_datos_candidatos` permanece separado y sin cambios.


### Corrección del modal de verificación (18.0.1.0.8)

- El modal incluye una X que cancela el registro pendiente y vuelve al registro nativo de Odoo.
- El temporizador se calcula cada 250 ms desde la hora de vencimiento del servidor para actualizar el contador cada segundo y habilitar el reenvío al vencer.
- La inicialización JavaScript funciona incluso cuando los assets se cargan después de `DOMContentLoaded`.


### Corrección 18.0.1.0.9: creación de cuentas luego del OTP (Odoo 18)

- Se corrigió la incompatibilidad que impedía crear la cuenta tras verificar el código: en Odoo 18, `res.partner.signup_prepare()` no rellena `signup_token` como en versiones antiguas. Ahora se invoca `partner._generate_signup_token()` y se pasa ese valor a `res.users.signup()` para enlazar el usuario con el contacto recién creado.
- Se conserva la transacción con `savepoint`, la validación del código, el inicio de sesión manual, el uso de la plantilla de usuario portal nativa y la prevención de correos ya registrados.
- Si ocurre otro error durante la creación, el registro de Odoo conserva la excepción real bajo `No se pudo crear la cuenta nativa del portal de crédito CONEDERA` para facilitar la revisión por el administrador.
- Actualizar este módulo en Odoo (Upgrade) y reiniciar el servicio; no es necesario modificar el módulo de recursos humanos.

## Versión 18.0.1.1.0 — tipos de solicitante y documentación configurable

- **Configuración**: Crédito CONEDERA > Tipos de solicitante. Cree cualquier cantidad de tipos y establezca sus documentos desde la pestaña **Documentos exigidos**. Por requisito puede configurar orden, nombre, carácter obligatorio, visibilidad condicionada a que la solicitud informe un cónyuge, formato fotográfico y descripción.
- **Portal de solicitudes**: el campo Tipo de solicitante lee los registros activos del catálogo. Se conservan los campos de ambas páginas de la solicitud PDF; se separaron los campos Lugar y Fecha, y Ciudad/Cantón/Parroquia de la verificación interna de ubicación.
- **Portal documental**: después de que la solicitud sea aprobada, la lista de archivos a cargar corresponde al catálogo del tipo seleccionado, no a una lista codificada en el controlador. Permite guardado parcial. Las planillas de servicios y las fotografías interiores/exteriores se solicitan como archivos separados. La cédula del cónyuge solo se muestra cuando en la solicitud consta el nombre del cónyuge.
- **Tipos iniciales**: Persona natural y Persona jurídica; requisitos iniciales según las siete u ocho categorías indicadas, divididas en archivos independientes donde aplica.
- **Validaciones**: se aceptan PDF/JPG/PNG para documentos, JPG/PNG para fotos, máximo 12 MB, verificación del encabezado del archivo y verificación del documento seleccionado (su tipo debe corresponder al de la solicitud). La aceptación de la documentación se bloquea si faltan requisitos obligatorios.
- **Actualización**: se mantiene temporalmente el campo antiguo `person_type` para conservar datos históricos, pero **no** es el selector activo. Al actualizar se asigna el nuevo `applicant_type_id` a solicitudes anteriores y se copian los archivos legados para los requisitos iniciales sin duplicarlos. Los binarios antiguos siguen almacenados y se consultan en **Documentación recibida > Archivos de versiones anteriores**. La copia omite archivos antiguos sin un nombre/extensión recuperables o que no superen la validación; esos archivos permanecen disponibles en su campo histórico.

### Actualizar desde 18.0.1.0.9

1. Realice respaldo de base de datos **y filestore**.
2. Instale los archivos nuevos en la carpeta del módulo `custom_web_credito_conedera`.
3. Reinicie Odoo y actualice la lista de aplicaciones; actualice el módulo.
4. Confirme los tipos y requisitos en el menú de configuración.
5. Pruebe en el portal una solicitud de cada tipo, apruebe la solicitud, adjunte documentos de prueba y valide los contadores en la sección interna.
6. Revise la migración de expedientes previos antes de eliminar datos o archivos históricos. **No elimine** los campos legados durante esta actualización.

## Versión 18.0.1.2.0 — identificadores, estados y formulario paso a paso

- Los **nombres y apellidos** del propietario/representante inician vacíos en la solicitud, aunque el usuario haya iniciado sesión. El correo del usuario puede continuar precargado.
- Los **tipos de solicitante** poseen un **ID único permanente** (`code`): se conservan `natural` y `juridical` de los tipos precargados; los nuevos tipos reciben códigos de secuencia `TC-000001`, `TC-000002`, etc. El código aparece en su formulario/listado administrativo, no se puede modificar y las solicitudes/documentos siguen relacionados mediante Many2one, no nombres. Los tipos antiguos que carecían de código reciben uno al actualizar, sin cambiar los que ya existían.
- **Estados civiles**: catálogo nuevo `conedera.credit.marital.status`. Se precargan Soltero/a, Casado/a, Divorciado/a, Viudo/a, Unión de hecho y Otro. Puede añadir/renombrar, desactivar o eliminar estados no utilizados desde **Crédito CONEDERA > Estados civiles**. El antiguo `marital_status` se conserva para compatibilidad y se migra a `marital_status_id` sin alterar las solicitudes ya existentes. Los nuevos estados civiles también tienen código estable.
- **Etapas de solicitud**: continúan administrándose en **Crédito CONEDERA > Etapas del flujo** y ya no se limitan por una lista fija de nombres en la barra de estado. Se añade el atributo **Documentación recibida (acción automática)**, usado para localizar el destino de la acción sin depender de que el estado se llame literalmente “Documentación recibida”. La migración asigna el indicador a la etapa original. Si una etapa está vinculada con solicitudes, debe archivarse en vez de borrarla (integridad histórica).
- **Portal de cinco pasos**: (1) propietario/representante; (2) negocio/empresa; (3) actividad económica en relación de dependencia y referencias comerciales; (4) referencias personales y bancarias; (5) términos y condiciones. Navegación con **Siguiente/Anterior**, validación por paso y conservación de lo escrito mientras no se recargue la página. Las dos secciones legales se leen juntas bajo **Términos y condiciones**, pero cada una conserva sus casillas individuales de aceptación.
- **Envío bloqueado sin aceptaciones**: validación en navegador, controlador HTTP y `create()` del modelo. No se crea ningún registro hasta enviar la última pantalla con todas las aceptaciones afirmativas. Si hay validaciones de servidor, se devuelven los valores para que el usuario corrija la solicitud.
- El módulo no ofrece guardado de borrador entre sesiones o recargas de página: avanzar/retroceder se realiza dentro de un formulario sin crear todavía la solicitud. Se conservan los requisitos documentales configurables de la versión 18.0.1.1.0 y el registro por OTP de versiones anteriores.

### Instalación sobre versiones anteriores

1. Respalde base de datos y filestore.
2. Reemplace la carpeta del addon y reinicie Odoo.
3. Actualice el módulo **Portal de Solicitudes de Crédito CONEDERA** desde Aplicaciones.
4. Valide el catálogo de **Tipos de solicitante**, los **Estados civiles** y las **Etapas del flujo**.
5. Pruebe las cinco pantallas, el botón Anterior, una aceptación faltante, una solicitud correcta, su etapa y los archivos documentales.

Las verificaciones incluidas en el paquete son estáticas (compilación Python, parseo XML y sintaxis JavaScript, más inspección estructural del formulario). No se ha ejecutado una instancia de Odoo 18 ni probado la migración contra una base real.


### Versión 18.0.1.3.0
- Catálogo editable de tipos de vivienda, con identificadores estables (`VI-000001`), menú propio y migración de registros históricos.
- Cédula/RUC del solicitante: estructura y dígito verificador cuando corresponde; cédula opcional del cónyuge y celular de exactamente 10 dígitos. Validación en portal y ORM. No consulta en tiempo real al SRI/Registro Civil.
- Vehículos: dos filas predeterminadas en el formulario, botón «Agregar otro vehículo» (hasta 30 por solicitud para evitar envíos abusivos), almacenamiento One2many y migración idempotente de vehículos 1 y 2 de solicitudes anteriores.

## Novedades 18.0.1.4.0

- **Vehículos:** se muestra solo Vehículo 1. El botón «Agregar otro vehículo» crea Vehículo 2, 3, etc. (hasta 30 por formulario). Los datos se guardan en `vehicle_ids`.
- **Referencias:** se muestran tres líneas iniciales independientes para comerciales, personales y bancarias. Cada sección permite añadir filas (hasta 30) y eliminarlas; se guardan en `reference_ids`.
- **Documento del propietario:** `identification_type` es cédula ecuatoriana (10 dígitos con verificador), RUC (exactamente 13 numéricos) o cédula extranjera (exactamente 10 numéricos). El RUC del negocio exige 13 numéricos. Esta regla estructural no consulta ni garantiza existencia en el SRI.
- **Cónyuge:** los campos de nombre, identificación y profesión son obligatorios para los estados civiles marcados como **Requiere datos del cónyuge** (por defecto Casado/a y Unión de hecho); los demás tipos los ocultan y no los guardan. El documento admite cédula ecuatoriana válida o identificación extranjera numérica de 10 dígitos.
- **Ubicación:** `business_latitude` y `business_longitude` permiten escribir coordenadas o usar geolocalización del navegador mediante autorización. No se solicita ni genera enlace de Google Maps.
- **Permiso especial (actual):** el responsable autorizado habilita desde cada solicitud la actualización de datos, documentos o ambas opciones. El servidor valida la propiedad de la solicitud y los permisos individuales.
- **Verificación paralela:** `verification_status` es independiente de `stage_id`: Pendiente, En verificación, Verificado y No conforme. Para aprobar, se requiere Verificado, inspección realizada, dirección encontrada, dirección verificada y verificador identificado. Para rechazar, la verificación debe estar finalizada. La antigua etapa «Verificación» se archiva sin borrar su historial.
- **Una solicitud en trámite por usuario:** no se permite crear otra hasta que la anterior se apruebe o rechace; una solicitud ya aprobada que avanza al expediente documental sigue considerándose decidida. La comprobación se aplica también desde el ORM con bloqueo transaccional por usuario.

Instalación: respaldar base de datos y filestore, sustituir directorio, reiniciar Odoo y actualizar el módulo. Probar con una base de ensayo, especialmente si hay expedientes históricos, antes de llevarlo a producción.


## Versión 18.0.1.5.0 — corrección del historial, permisos y documentación

- El historial muestra **Actualizar** al propietario con el permiso especial y solicitud pendiente de decisión; abre los cinco pasos precargados con vehículos, referencias, datos de negocio y aceptaciones. Los demás usuarios solo pueden consultar **Ver detalle**.
- La versión 18.0.1.5.0 utilizó autorización global; el mecanismo vigente habilita cada solicitud individualmente. No se necesita ningún permiso global en el usuario de portal.
- En el backend, el botón inteligente **Acceso especial** requiere tanto el grupo de gestor de crédito como el permiso especial. Permite abrir datos (para corregir antes de la decisión), historial interno o expediente documental (solo tras aprobación).
- La carga documental depende ahora del estado real (Aprobada o Documentación recibida después de aprobar), no solo de un indicador booleano que pudo quedar activo. Se oculta en revisión, se bloquea la URL de carga incluso por acceso directo y se limpia el indicador obsoleto al actualizar el módulo. Se conservan los archivos históricos.
- Ningún usuario puede modificar una solicitud ajena desde el portal; una solicitud aprobada, denegada o con documentos ya recibidos no permite cambiar los datos iniciales desde el portal.


## 18.0.1.6.0 — Permisos por solicitud como Historial de Postulaciones

- A diferencia del permiso global anterior, cada solicitud almacena `portal_update_scope`: `none`, `history`, `documentation`, `both`. Por seguridad, los expedientes antiguos se mantienen sin permiso hasta que el responsable los habilite.
- En **Crédito CONEDERA → Solicitudes**, el usuario interno que pertenezca al grupo **Gestionar permisos de actualización del portal de crédito** ve el botón de cabecera **Habilitar permiso del portal** y el botón inteligente **Permiso portal**. Ambos abren el mismo asistente de autorización con botones **Habilitar/Cancelar**, como en `custom_web_hr_historial_postulaciones`.
- El responsable se puede autorizar desde **Ajustes → Usuarios → Puede habilitar permisos del portal de crédito**, o asignándole el grupo de administración correspondiente. Este grupo implica gestionar crédito y **no se otorga a usuarios portal**.
- **Historial:** aparecerá el botón **Actualizar** para la solicitud autorizada, mientras esté en trámite y no aprobada/rechazada. Se cargan los datos existentes del formulario de cinco pasos.
- **Documentación:** el primer ingreso de archivos se permite tras la aprobación; modificaciones posteriores de un expediente ya creado requieren el permiso `documentation` o `both` de esa solicitud (igual que el módulo de referencia). Sin aprobación no se permite cargar archivos ni mediante URL.
- Puede revocarse el permiso seleccionando **Ninguna sección**. Se guardan la fecha y el usuario responsable de la autorización.
- El permiso obsoleto de corrección global y su campo auxiliar quedan retirados a partir de 18.0.1.7.0.


## 18.0.1.7.0 — Retiro definitivo del grupo global obsoleto

- Se elimina del código el grupo de corrección global del portal y el campo auxiliar antiguo de `res.users`.
- Al **actualizar** una base que tenga versiones anteriores, `migrations/18.0.1.7.0/post-remove-old-portal-group.py` quita el grupo legado de `res.groups` y sus asignaciones a usuarios.
- Se mantiene sin cambios el grupo **Gestionar permisos de actualización del portal de crédito**, el botón inteligente **Permiso portal** y los permisos individuales de las solicitudes.
- La migración se ejecuta al actualizar el módulo por cambio de versión; no es suficiente reemplazar archivos sin actualizar el módulo en Odoo.


## Versión 18.0.1.8.0: permisos, colores y corrección de un solo uso
- El permiso de Historial permite actualizar una vez; al guardar se consume y la vista vuelve a `Ver detalle`. Si se concedieron ambas opciones, queda solo el permiso de documentación.
- Grupo **Usuario de crédito (revisión y verificación)**: lectura de datos del solicitante, movimiento de etapa y edición exclusiva de verificación de ubicación/negocio. El resto de modelos (catálogos, referencias, vehículos y documentos) queda en solo lectura. Las restricciones se comprueban en el ORM, además de las vistas.
- Grupo **Administrador de crédito (edición completa)**: gestión completa de solicitudes y catálogos, con pantalla **Crédito CONEDERA → Colores del portal** (colores HEX).
- Grupo **Gestionar permisos de actualización del portal de crédito**: para personal autorizado que concede permisos por solicitud; implica el rol administrador de crédito.
- Atención al actualizar: los usuarios que solo tenían el grupo anterior «Gestión de solicitudes» pasan a tener el rol de usuario limitado; para conservar la edición completa se debe asignar explícitamente **Administrador de crédito**.


## Corrección 18.0.1.8.1 (vistas Odoo 18)

- Corrige la definición de la vista de historial de etapas: los campos del modelo `conedera.credit.stage.history` no consultan el campo `credit_is_admin` de la solicitud principal.
- El historial permanece de solo lectura para todos los roles; el administrador gestiona la solicitud en su formulario y los empleados autorizados actualizan la etapa desde el encabezado.
- Mantiene la separación Administrador/Usuario de crédito, los colores configurables y la actualización del portal de un solo uso.


## Versión 18.0.1.8.2 — Solo coordenadas

- `maps_url` se conserva únicamente como campo técnico de compatibilidad con vistas antiguas ya guardadas en Odoo. No aparece ni se utiliza en formularios, rutas o correos; únicamente se usan latitud y longitud.
- El detalle de la solicitud presenta latitud y longitud; se mantiene el botón «Usar mi ubicación actual».
- El envío a cobranzas, cuando se registran coordenadas nuevas, incluye únicamente latitud y longitud.
- Conservadas las validaciones y restricciones de acceso del módulo anterior.

## Corrección 18.0.1.8.3: ubicación automática

El botón «Usar mi ubicación actual» distingue entre sitio sin HTTPS, permiso denegado, ubicación no disponible y tiempo agotado. La captura automática requiere HTTPS válido (o localhost para pruebas), permiso de ubicación del navegador y servicios de ubicación activos en el dispositivo. No depende de Google Maps y continúa permitiendo ingresar latitud y longitud manualmente.


## 18.0.1.8.5 - PDF y portal

- Compatible con vistas antiguas almacenadas en Odoo que todavía solicitan `maps_url` al leer solicitudes; no se muestra ni utiliza este campo.
- Se retiró del inicio del portal la tarjeta «Gestión de solicitudes» y su acceso «Acciones rápidas». Los accesos Historial de solicitudes e Ingreso de documentos continúan funcionando; las URL antiguas redirigen al historial.
- En Crédito CONEDERA > Solicitudes se añadió **Descargar solicitud PDF**, también disponible en el menú Imprimir.
- El reporte QWeb en A4 sigue los dos apartados del formato «SOLICITUD DE CREDITO CONEDERA ACTUALIZADA»: solicitud / datos económicos / referencias / autorizaciones y verificación de ubicación.
- Incluye vehículos y referencias de longitud variable; muestra los campos del cónyuge solo cuando corresponden al estado civil o tengan información histórica, y utiliza únicamente coordenadas para la ubicación del negocio.
- Para solicitudes con muchas líneas el documento puede ocupar páginas adicionales, sin recortar las referencias.


## Versión 18.0.1.8.7 — Croquis del cliente desde el portal

- En **Paso 2: Datos del negocio**, el cliente completa los datos de **Verificación de ubicación del negocio** (provincia, ciudad, cantón, parroquia, barrio, dirección, número de casa/local y referencia). Su documento y nombre se muestran automáticamente desde el paso 1.
- El croquis es obligatorio en nuevas solicitudes; se puede dibujar con mouse/pantalla táctil o adjuntar un PNG/JPG/WEBP/PDF de hasta 12 MB. No forma parte de los documentos posteriores a la aprobación.
- El sistema conserva el croquis histórico durante una corrección si el cliente no adjunta ni dibuja uno nuevo. El permiso individual para actualizar el historial sigue siendo de un solo uso.
- Los croquis existentes son accesibles desde el historial de la solicitud mediante una URL que valida la propiedad del expediente. No son archivos públicos.
- En el backend se separan las pestañas **Ubicación y croquis (cliente)** (solo lectura para usuario de crédito; editable para administrador) y **Verificación de ubicación (uso interno)**, donde el personal autorizado completa zona, estado del local, persona entrevistada, resultados, verificador y firma.
- El PDF continúa mostrando el croquis y la información de verificación con sus respectivos datos guardados. Los datos previos no se eliminan en la actualización.


## 18.0.1.8.8 · Croquis separado desde el historial
- Etapa En revisión (o etapa configurada con «Permitir subir croquis en el portal»): muestra el botón **Subir croquis** en el historial y en el detalle.
- El formulario independiente muestra datos del cliente y ubicación editable, permite adjuntar PNG/JPG/WEBP/PDF (máximo 12 MB) y ofrece previsualización adaptable antes de guardar.
- El croquis es opcional al enviar la solicitud inicial, para entregarlo después durante la revisión. No reemplaza ni desbloquea los documentos posteriores a la aprobación.
- El acceso se valida por propietario, etapa y servidor. El permiso especial de actualización del formulario sigue independiente y no se consume al cargar el croquis.
- El administrador puede habilitar/deshabilitar el botón por etapa desde «Etapas del flujo». Una migración idempotente configura la etapa de revisión previamente instalada.


## Versión 18.0.1.8.11 — Formato PDF y cierre de verificación

- Se oculta **Firma del verificador** en la ficha interna de solicitud; el campo técnico se conserva solo para no destruir archivos históricos. El reporte tampoco la muestra.
- El reporte de Solicitud de Crédito ahora sigue el formato CONEDERA: primera hoja con propietario, empresa, actividad, referencias, declaración y espacios en blanco independientes para la firma electrónica del **solicitante** y del **gerente**; segunda hoja con ubicación, croquis, inspección, resultados y verificador.
- El PDF incorpora los croquis de imagen. Si se adjunta PDF, intenta generar una vista previa de su primera página usando PyMuPDF o Poppler (`pdftoppm`) cuando esté disponible. En ausencia del conversor se mantiene la referencia al archivo digital, sin impedir imprimir.
- Las áreas de firma son espacios **visuales** para que un firmante firme después en un sistema de firmas electrónicas. El módulo no aplica certificados ni crea firmas digitales criptográficas por sí solo.
- Cuando hay muchas referencias o contenidos de texto extensos, el reporte puede ocupar páginas adicionales para evitar recortar información.

## Versión 18.0.1.8.12: habilitación del croquis por solicitud

En Solicitudes de crédito, el botón «Habilitar permiso del portal» ofrece tres casillas
independientes: (1) corrección de solicitud, (2) corrección de documentos y
(3) corrección de croquis del cliente. El responsable puede combinarlas libremente.
Los permisos existentes de versiones anteriores se preservan.

Mientras la etapa tenga activado «Permitir subir croquis en el portal»,
el primer croquis continúa habilitado por defecto para el cliente.
Tras guardarlo, el historial vuelve a «Ver detalle».
Si es necesario corregir el croquis ya entregado, el responsable marca
«Croquis del cliente» en el asistente para esa solicitud; reaparece
«Subir croquis». Al guardar, ese permiso se consume automáticamente sin
afectar la autorización de solicitud ni documentación. No se puede modificar
un croquis fuera de la etapa de revisión habilitada, incluso con el permiso.


## Versión 18.0.1.8.13 — catálogos de verificación y cierre obligatorio

- En Crédito CONEDERA → Zonas de verificación / Estados del local, el administrador puede añadir, editar, archivar y eliminar opciones que no estén vinculadas a solicitudes. Los usuarios de crédito solo las consultan y seleccionan.
- Zona y estado del local en la solicitud ahora son campos Many2one. Los valores históricos se enlazan mediante una migración repetible, conservando las columnas antiguas como compatibilidad.
- Debajo de Relación / parentesco aparece el campo Nombre de la persona entrevistada.
- El estado técnico de verificación se oculta del formulario interno; se determina automáticamente cuando el personal completa las cuatro respuestas y el nombre del verificador.
- Para aprobar o rechazar se exigen las cuatro respuestas, el nombre del verificador y la fecha (asignada automáticamente). Una inspección incompleta puede guardarse durante la etapa de revisión, pero no pasar a una decisión final.

## PDF y operación multiempresa (18.0.1.8.17)

- Las solicitudes nuevas usan la empresa del sitio web Odoo desde el que se enviaron.
- Los reportes usan `application.company_id` para logotipo y rótulos de gerencia, y no la compañía activa del usuario que imprime.
- El personal interno consulta expedientes exclusivamente de compañías permitidas por reglas de registro.
- Los catálogos generales (etapas, tipos, requisitos) siguen compartidos entre empresas.
- Las solicitudes anteriores no almacenaban empresa: se asignan a la empresa activa durante la actualización, y debe revisarse el resultado si ya trabajaba con varias compañías.
- Los textos legales (por ejemplo, ciudad de jurisdicción, referencias a la sede principal) deben ser revisados y personalizados por empresa antes de usarlos con personas jurídicas distintas.
- PDF del portal requiere sesión y pertenencia de la solicitud; las áreas de firmas se mantienen vacías y NO son una firma electrónica aplicada.


## Versión 18.0.1.8.20 - Documentos firmados

- Nueva pestaña **Documentos firmados** posterior a Verificación de ubicación, con dos PDF adjuntos a la solicitud: solicitud firmada y verificación de ubicación firmada.
- Solo el Administrador de crédito puede cargar o sustituir los archivos; el personal de revisión puede consultarlos.
- Validación de extensión .pdf, cabecera PDF y tamaño máximo 25 MB por archivo.
- En el portal, el menú de descarga permite obtener únicamente los PDFs firmados que se hayan cargado para la solicitud propia. Si aún no hay archivos muestra *Firmas pendientes*.
- Si están disponibles ambos, se ofrecen juntos en **ZIP**, no en un PDF fusionado: modificar un PDF firmado electrónicamente invalidaría sus firmas.
- Los reportes QWeb originales siguen disponibles para impresión en el backend; en el portal se descargan únicamente los PDF firmados guardados en la nueva pestaña.
- El archivo queda vinculado a la solicitud y su empresa, sin compartir adjuntos entre expedientes.


### Versión 18.0.1.8.22 — PDF firmados en el portal

- En el historial no se muestra la columna «Documentos» ni el botón de PDF.
- La pestaña **Documentos firmados** se mantiene inmediatamente después de **Verificación de ubicación (uso interno)**.
- En el detalle de una solicitud aparece **Descargar PDF** solo si ya está aprobada y se cargó al menos uno de los PDF firmados.
- El portal descarga exclusivamente los binarios originales de esa solicitud. Los dos PDF se entregan como ZIP sin fusionar, para conservar las firmas electrónicas.
- Para solicitudes en la etapa «Documentación recibida», la descarga requiere una aprobación previa registrada en el historial.

## Versión 18.0.1.8.23 - Cabecera compacta del propietario

- El primer paso ya no muestra ni obliga a introducir Lugar. El campo histórico del modelo se conserva para expedientes anteriores y no se borra al actualizar una solicitud.
- Tipo de solicitante, Fecha y Tipo de documento comparten una fila de tres columnas en escritorio. En móvil se apilan para evitar recortes.
- Se conservan las validaciones y todos los demás campos del formulario.


## Versión 18.0.1.8.25 — seis pasos y catálogos bancarios
- Paso 3: datos de ubicación y croquis del cliente (PNG/JPG/WEBP/PDF, 12 MB); se guardan en la misma solicitud.
- Los pasos de actividad y referencias pasan a 4 y 5 y términos a 6.
- El croquis deja de tener formulario independiente. Los enlaces anteriores redirigen al formulario integrado y sus POST antiguos se bloquean.
- Para solicitudes históricas sin croquis, la carga pendiente sigue disponible desde el formulario integrado durante la revisión; las correcciones autorizadas siguen siendo de un solo uso.
- Configuración > Tipos de cuenta bancaria: Corriente, Ahorros y nuevas opciones. Migración de registros existentes y reporte PDF con las nuevas denominaciones.
- La declaración general conserva su contenido con Ver más/Ver menos. Los PDF de Solicitud y Verificación siguen separados o combinables desde el backend.

### 18.0.1.8.32 — Catálogo de empleadores y ajustes responsivos
- En **Crédito CONEDERA > Configuración > Tipos de empleador**, el administrador puede crear, archivar y reordenar opciones. Privado y Público son registros iniciales, no un Selection fijo.
- Las solicitudes existentes conservan el valor anterior mediante el nuevo campo `employment_employer_type_id` y la rutina de migración idempotente.
- Eliminadas las dos ayudas textuales indicadas del portal; Anterior usa el color primario y Cancelar un color de alto contraste.
- Ajustes de diseño responsive para formularios, controles, navegación y tablas de referencias en móviles y tablets.

## PWA y formulario sin conexión (18.0.1.8.42)

- El portal conserva una interfaz estilo aplicación también al abrir el dominio desde el navegador móvil (sin instalar la PWA).
- Para usar el formulario sin conexión, el usuario debe entrar con sesión iniciada y abrir `/my/credito/nueva` al menos una vez con conexión HTTPS en ese dispositivo.
- La plantilla **vacía** del formulario y los recursos estáticos se guardan localmente. Los datos que ingresa el usuario, sus referencias, consentimientos y el archivo del croquis se almacenan en **IndexedDB** del dispositivo, no en la caché de páginas autenticadas. No usar dispositivos compartidos para información crediticia.
- Al enviar sin conexión o con red inestable, el formulario pasa a "Pendiente de envío". El cliente intenta sincronizarlo al volver la conexión (si el navegador permite Background Sync, también puede reintentarlo sin la pestaña abierta). El usuario puede consultar el estado local o eliminar el borrador.
- La sincronización utiliza un CSRF nuevo obtenido tras comprobar sesión, empresa y sitio web. Las validaciones originales del servidor siguen siendo obligatorias; un borrador incompleto no genera una solicitud.
- Cada borrador tiene un UUID de envío que se almacena en el expediente. Los reintentos con ese UUID devuelven la solicitud previamente registrada para evitar duplicados.
- Los documentos firmados y expedientes ya existentes NO se guardan offline. El usuario debe estar conectado para iniciar sesión, consultar el historial y descargar archivos.
- La disponibilidad de sincronización en segundo plano depende del navegador. En navegadores sin Background Sync, el reintento se produce al volver internet con la página abierta, o al reabrirla con sesión válida.
- El almacenamiento local puede borrarse automáticamente por políticas del navegador o al limpiar sus datos. No sustituye la confirmación de envío proporcionada por Odoo.
- Requisito: dominio de cada empresa configurado con HTTPS, sitio web y compañía correctamente asociados.

## 18.0.1.8.43: Guardado offline de todas las operaciones del portal

- Nueva solicitud: se conserva la cola e identificador único introducidos en 18.0.1.8.42.
- Actualización de solicitud y croquis integrado: al pulsar **Guardar**, el formulario y su archivo se conservan localmente (IndexedDB) antes de intentar enviarse.
- Documentos solicitados: los archivos nuevos de cada requisito (incluidos varios en planillas y fotografías) permanecen en el borrador local hasta confirmar su recepción en Odoo.
- Si se recupera internet con el portal abierto, se reintenta. En navegadores compatibles se solicita sincronización de fondo; en los demás se reintenta al reabrir el portal con sesión válida.
- El endpoint `/my/credito/offline/dispatch` aplica las mismas validaciones y permisos del formulario original, más un token idempotente por operación para evitar aplicar dos veces una corrección cuando se pierde la respuesta de red.
- Los borradores son exclusivos del origen, sitio web, empresa y usuario; **no** son documentos enviados ni se considera que Odoo los recibió hasta confirmar éxito.
- Los archivos y datos personales quedan en el dispositivo. No utilizar esta función en equipos compartidos; limpiar los borradores locales cuando deje de necesitarlos. El almacenamiento del navegador puede ser eliminado por el usuario o por políticas del dispositivo.
- Para abrir un formulario sin conexión desde cero, el usuario debe haberlo abierto previamente con internet en ese mismo navegador. Las solicitudes ya aprobadas y los permisos de un solo uso se comprueban nuevamente al sincronizar.
- El primer acceso, la autenticación y las descargas requieren red; la PWA requiere HTTPS para el funcionamiento del service worker.

## 18.0.1.8.44 — Envío online prioritario / cola únicamente sin conexión

- Al pulsar **Enviar** o **Guardar** con conexión, el navegador realiza primero la solicitud a Odoo y espera una confirmación JSON `sent`. No marca una operación como pendiente antes de intentar enviarla.
- Cuando falla realmente la comunicación (fallo de transporte o solicitud sin respuesta dentro del tiempo máximo), conserva el formulario y sus archivos en IndexedDB como **Pendiente de sincronización** y permite reintentos automáticos.
- Un error HTTP, una sesión caducada, la respuesta de validación `review/blocked` o un error de servidor `retry` no se interpreta como falta de red. En estos casos conserva el **borrador** y muestra el motivo para permitir volver a intentar tras corregirlo.
- El autoguardado no puede convertir en envío confirmado un borrador; solo un clic en Guardar/Enviar o una cola previamente confirmada autoriza la sincronización automática.
- Mantiene el UUID de la solicitud u operación al reintentar después de una caída de red para no duplicar registros.
- Caché de PWA actualizado a `credit-safe-static-v1844` para renovar los scripts del portal.

**Nota**: la sincronización confirmada continúa dependiendo de una sesión vigente, de los permisos y de las validaciones de Odoo. El guardado local no equivale a un guardado en la base de datos.


### v18.0.1.8.45 — Login obligatorio antes de abrir la ficha
- La ficha `/my/credito/nueva` sigue protegida con `auth='user'`; sin una cuenta y sesión iniciada no se puede consultar ni enviar.
- Las entradas públicas `/credito`, `/credito/solicitar`, `/my/credito` y `/credito/registro` conducen al login nativo `/web/login?redirect=%2Fmy%2Fcredito%2Fnueva` para visitantes anónimos. Las personas ya autenticadas llegan directamente a su ficha.
- **Entrada por el dominio principal del sitio**: si el sitio actual se llama exactamente **Solicitud de Crédito**, **Solicitud de Crédito CONEDERA** o **Crédito CONEDERA**, entrar a su URL base `/` redirige al login (o a la ficha si ya inició sesión). Los otros sitios web de la base se mantienen sin cambios.
- Para un sitio con otro nombre, ir a **Sitio web > Configuración > Sitios web**, editar ese sitio y activar **Abrir login al entrar a este sitio web**. La compañía sigue siendo la que tenga asignada ese sitio.
- El registro de cuenta `/web/signup` y la verificación OTP continúan habilitados para personas que aún no tienen una cuenta; registrarse **no equivale** a poder utilizar la ficha sin autenticación.
- El menú *Solicitar crédito* apunta a `/credito`, que decide entre el login y la ficha según la sesión.
- La redirección raíz utiliza `302` y `Cache-Control: no-store`; no altera el `/` de otros sitios web ni el inicio del backend.

**Pruebas sugeridas en Odoo:** (1) abrir el dominio del sitio de crédito en incógnito y confirmar que aparece el login; (2) iniciar sesión como cliente portal y confirmar que se abre la ficha; (3) abrir `/my/credito/nueva` sin sesión y confirmar que Odoo exige login; (4) abrir el dominio de otro sitio de la misma base y confirmar que conserva su portada; (5) registrar cuenta nueva con OTP y confirmar que después requiere iniciar sesión.


### 18.0.1.8.46 — Registro y documento de la ficha

- Una vez verificado el OTP, el usuario se crea por `auth_signup`, se autentica en Odoo 18 y se dirige a `/my/credito/nueva` sin pasar nuevamente por `/web/login`. Si la autenticación automática falla, la cuenta queda creada y se ofrece el login usual.
- La fecha del paso 1 es de solo lectura y se asigna exclusivamente desde el servidor en nuevos envíos; en correcciones se conserva la fecha original. Un POST manipulado no puede alterarla.
- Para el tipo estándar `juridical`, el documento es RUC y se valida como 13 dígitos. Para persona natural están disponibles cédula, cédula extranjera y RUC.
- Los borradores recuperados sin conexión respetan la fecha actual y sincronizan automáticamente el tipo de documento.


### v18.0.1.8.47: tipo de documento fijo en persona jurídica
- Persona jurídica: el selector del paso 1 muestra exclusivamente **RUC** y queda bloqueado. El formulario envía RUC mediante un input oculto mientras el select está deshabilitado.
- Persona natural: se restauran las opciones cédula ecuatoriana, cédula extranjera y RUC; el selector se puede cambiar libremente.
- Se conserva la normalización en el controlador del servidor a RUC para persona jurídica, y la recuperación de borradores sin duplicar campos en persona natural.


## v18.0.1.8.48 — Contactos Odoo vinculados a solicitudes

- `partner_id` vincula el expediente con `res.partner`. Las solicitudes web reutilizan el contacto existente por documento e identidad del usuario o crean uno si no existe. Para persona jurídica se vincula la empresa (RUC) sin reemplazar el contacto del representante que creó la cuenta.
- Al crear solicitudes en backend, el administrador selecciona **Contacto solicitante**. Un `onchange` copia a la solicitud los datos disponibles del contacto; los valores faltantes (incluido RUC del negocio, si es necesario) se completan en la ficha. No crea una cuenta de portal automáticamente.
- `portal_user_id` es opcional en backend; solo los expedientes con usuario asociado se muestran en ese portal.
- Las aceptaciones legales del portal **no se inventan** para una solicitud ingresada manualmente: quedan sin marcar hasta que exista evidencia legítima.
- La actualización ejecuta `_migrate_credit_partner_links()` para enlazar expedientes antiguos sin alterar sus etapas ni sus datos originales.
- La relación admite contactos compartidos o de la empresa de la solicitud. No se modifican los datos de contactos comerciales existentes.

- La ficha del Contacto muestra el botón inteligente **Solicitudes de crédito**, con el historial de expedientes vinculados y acceso a crear uno nuevo desde ese contacto (según permisos).


## Versión 18.0.1.8.49 — Solicitante asociado directamente a Contactos
- `applicant_name`: `fields.Many2one('res.partner')` calculado e invertible desde `partner_id`.
- En el back, **Solicitante** permite elegir un contacto ya creado en Odoo.
- La actualización conserva el texto antiguo `applicant_name` en `applicant_name_text` mediante migración SQL previa.
- El portal conserva su captura de nombres como texto, pero solo el servidor resuelve el contacto; no acepta un ID de contacto arbitrario.
- Los reportes y documentos mantienen el nombre declarado para respetar el histórico (representante en persona jurídica).
- Si falta vinculación de un expediente antiguo se intenta enlazar mediante el procedimiento existente por documento, RUC y empresa, sin fusionar contactos ambiguos.
- Se mantiene `partner_id` para compatibilidad con la ficha de Contactos y con instalaciones v18.0.1.8.48.
**Actualizar el módulo instalado** (no desinstalarlo), tras realizar una copia de seguridad de la base y el filestore.


### 18.0.1.8.50 — Permisos independientes

- Administrador de crédito y Usuario de crédito son roles independientes; asignar uno no activa automáticamente el otro.
- El permiso adicional para habilitar correcciones del portal tampoco obliga a marcar Usuario.
- Administrador conserva acceso a menús, fichas, verificación, PDFs, documentos y autorización de correcciones del portal gracias a ACL, reglas y vistas propias.
- Las reglas de multiempresa ahora incluyen ambos roles de forma explícita.
- En la actualización, se elimina la asignación heredada del grupo Usuario para cuentas que también tienen Administrador; quienes necesiten ambos pueden marcar Usuario de nuevo. No se cambian usuarios solo revisores.


## Corrección 18.0.1.8.51 — formulario de creación en backend

- Se precarga `credit_is_admin` en `default_get` para el formulario **Nuevo**.
- Los campos de la solicitud nueva no dependen de un valor computado todavía sin inicializar (`readonly="not credit_is_admin and id"`).
- En expedientes existentes, el rol Administrador mantiene la edición completa; Usuario de crédito se limita a etapa y verificación.
- Número, controles de aprobación/documentación e indicadores calculados permanecen protegidos.
- El campo Solicitante continúa siendo un `Many2one(res.partner)`; los permisos independientes de 18.0.1.8.50 permanecen intactos.

Actualice el módulo (no lo reinstale). Las validaciones de Odoo en el servidor siguen siendo obligatorias.


## Versión 18.0.1.8.52 — corrección definitiva de campos del backend

- Corregida la edición de solicitudes nuevas y existentes por el grupo Administrador de crédito.
- La vista del backend usa campos separados por `groups` y modificadores fijos `readonly=0` / `readonly=1` en vez de `readonly="not credit_is_admin and id"`.
- El Usuario de crédito conserva permisos de revisión/etapas/verificación pero no puede modificar los datos generales.
- El campo `applicant_name` sigue siendo relación `Many2one(res.partner)` y se conservan historial, PDF, reglas de empresa y permisos independientes.
- El administrador puede también corregir el `applicant_name_text` (nombre declarado en la ficha), cuando sea diferente de la razón social del contacto.
- Campos de secuencia, aceptación registrada, fechas automáticas y estado de documentación siguen protegidos.

Actualizar el módulo desde Aplicaciones después de reiniciar el servicio Odoo. No desinstalar.
