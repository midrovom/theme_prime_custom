# Portal de Solicitudes de Crédito CONEDERA - Odoo 18

Módulo nuevo e independiente de los módulos de Recursos Humanos utilizados como referencia.

## Funcionalidades incluidas

- Registro de portal en `/credito/registro` con nombre, correo, contraseña y consentimiento.
- Código de verificación OTP de seis dígitos enviado por correo; vence en 3 minutos y limita los intentos de validación.
- La cuenta portal se crea únicamente después de validar el código. Luego se solicita iniciar sesión y el acceso por defecto redirige a `/my/credito/nueva`.
- Formulario web que reproduce los campos legibles de la página 1 del PDF de solicitud: propietario/representante, tipo persona natural/jurídica, negocio, datos económicos, relación de dependencia y hasta tres referencias comerciales, personales y bancarias.
- Historial personal de solicitudes y detalle con etapas visibles para el cliente.
- Kanban interno por etapas para arrastrar solicitudes y avanzar el proceso. Los cambios se registran en la línea de tiempo y generan intento de notificación por correo al solicitante.
- La etapa **Aprobada** habilita la carga documental. El tipo de persona gobierna los campos mostrados y los requisitos obligatorios.
- Gestión de la documentación recibida y controles para aceptar el expediente o pedir correcciones.
- Campos de la página 2 del PDF destinados a la verificación interna de la ubicación del negocio.
- Se incluye el envío del enlace de Google Maps a `cobranzas@viteltek.com`, ya que esa dirección aparece explícitamente en el PDF proporcionado.

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
- Los datos de verificación de ubicación son campos internos. El formulario web del cliente solo solicita la dirección del negocio y el enlace de Google Maps.
- La declaración/autorización del formulario web sigue el texto de la solicitud PDF entregada. Por tratarse de una autorización legal de crédito, el área legal de CONEDERA debe validar la versión web antes de producción.
- Este paquete se validó estáticamente (estructura, XML y sintaxis Python). No se ejecutó contra una instancia real de Odoo ni se verificó el SMTP, por lo que se recomienda instalar primero en una base de pruebas.


### Ajustes de registro y aceptación documental
- El código de verificación vence a los 3 minutos. Al terminar el contador se habilita **Enviar código**; cada reenvío genera un código nuevo e invalida el anterior.
- Antes de enviar la solicitud, el cliente debe aceptar por separado las cláusulas sugeridas sobre relación comercial previa, citación telemática, consulta de score crediticio por cualquier plataforma o buró de crédito autorizado, firma/sello de CONEDERA y documentos financieros adicionales.
- Tras la aprobación, el expediente documental también solicita un PDF consolidado con las últimas seis declaraciones del IVA, la declaración del Impuesto a la Renta del año anterior y un certificado bancario correspondiente a los últimos seis meses.
- La autorización para consulta de score/historial se muestra como bloque independiente y no identifica a un proveedor específico.
