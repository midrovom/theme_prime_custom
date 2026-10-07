# custom_web_hr_historial_postulaciones

Módulo para Odoo 18 que extiende `custom_web_hr_datos_candidatos`.

## Funcionalidades

- Agrega al portal la tarjeta **Historial de postulación**.
- Lista las postulaciones asociadas al `res.users` mediante `hr.applicant.portal_user_id`.
- Muestra: **Postulación, Puesto, Fecha, Estado**.
- Muestra **Actualizar** únicamente cuando RRHH haya usado el botón **Permitir actualización**.
- La actualización reutiliza los formularios `recruitment_form_1`, `recruitment_form_2` y `recruitment_form_3` del módulo original.
- Después de guardar una actualización, el permiso se revoca automáticamente.
- Agrega **Ingreso de documentación** al portal cuando al menos una postulación alcanza la etapa de secuencia **3 o superior**.
- Crea `applicant.documentation`, relacionado con `hr.applicant`, con 14 documentos obligatorios.
- Valida archivos obligatorios en servidor. Los documentos administrativos se cargan en PDF; la fotografía permite JPG, PNG o PDF.
- Agrega una pestaña de documentación al formulario interno de `hr.applicant`.

## Instalación

1. Copiar la carpeta `custom_web_hr_historial_postulaciones` a la ruta de addons personalizados.
2. Reiniciar Odoo.
3. Actualizar la lista de aplicaciones.
4. Instalar **Portal - Historial de Postulaciones**.

El módulo depende de `custom_web_hr_datos_candidatos`, por lo que este debe estar instalado primero.

## Flujo de actualización

1. RRHH abre una postulación.
2. Pulsa **Permitir actualización**.
3. El postulante entra al portal y ve **Actualizar** en Historial de postulación.
4. El formulario reutiliza el formulario nativo del módulo original y carga los datos existentes.
5. Al guardar correctamente, `portal_update_allowed` vuelve a `False`.

## Flujo documental

1. La postulación llega a una etapa con `stage_id.sequence >= 3`.
2. El portal muestra **Ingreso de documentación**.
3. El postulante debe completar los 14 documentos.
4. Si falta cualquiera, el servidor rechaza el envío indicando la documentación pendiente.
5. Una vez completos, la postulación queda marcada como documentación completa.
