# Capacitaciones y Certificados por QR — Odoo 18 Community

Módulo independiente para registrar participantes desde un formulario público abierto por QR, generar un certificado PDF personalizado y enviarlo automáticamente por correo electrónico.

## Funciones

- Un QR y enlace público únicos por capacitación.
- Formulario móvil sin inicio de sesión: nombres completos, correo y empresa.
- Empresas participantes configurables con su logo.
- Cursos reutilizables y duración predeterminada.
- Plantillas configurables: logos, fondo, colores, textos, firmas y correo.
- Certificado PDF A4 horizontal con numeración única.
- Envío inmediato al correo ingresado.
- Prevención de registros duplicados por capacitación y correo.
- Fechas opcionales de apertura y cierre del formulario.
- Descarga del certificado al finalizar el registro.
- Panel de participantes con descarga, regeneración y reenvío.

## Variables de las plantillas

- `[NOMBRE]`
- `[CORREO]`
- `[EMPRESA]`
- `[CURSO]`
- `[FECHA]`
- `[DURACION]`
- `[INSTRUCTOR]`
- `[CERTIFICADO]`

## Instalación

1. Copie la carpeta `digital_training_certificate` dentro de la ruta de addons de Odoo 18.
2. Reinicie el servicio de Odoo.
3. Active el modo desarrollador y actualice la lista de aplicaciones.
4. Busque **Capacitaciones y Certificados por QR** e instale el módulo.
5. Asigne al responsable el grupo **Administrador de capacitaciones**.
6. Configure un servidor de correo saliente y el correo de la compañía en Odoo.

## Uso inicial

1. Abra **Capacitaciones > Configuración > Empresas participantes** y registre las empresas.
2. Cree el curso en **Cursos**.
3. Edite **Plantillas de certificado > Certificado corporativo** y cargue logos, firmas, textos y colores.
4. Cree una capacitación, seleccione empresas y plantilla, y pulse **Abrir registro**.
5. Pulse **Mostrar QR** para proyectarlo al finalizar la inducción.

## Consideraciones

- La URL pública de Odoo debe estar correctamente configurada en `web.base.url`. También puede definirse una URL pública diferente en cada capacitación.
- El envío es inmediato. Si el servidor SMTP devuelve un error, el participante conserva la descarga directa y el administrador puede reenviar el certificado.
- Regenerar el QR invalida inmediatamente el enlace anterior.

