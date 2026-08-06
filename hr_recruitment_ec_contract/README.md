# Recruitment EC - Contratos y Décimos (Odoo 18 Community)

Módulo complementario para **Reclutamiento**, **Empleados** y **Contratos**.

## Flujo automático

Cuando una solicitud de empleo entra en una etapa marcada por Odoo como **Hired Stage / Etapa contratada**:

1. Crea el empleado automáticamente, si la configuración lo permite.
2. Crea el registro de contrato en `hr.contract`.
3. Selecciona el texto configurable según la plantilla y el tipo de contrato.
4. Genera cuatro PDF independientes:
   - contrato;
   - solicitud de acumulación de décimo tercero;
   - solicitud de acumulación de décimo cuarto;
   - ficha individual del empleado.
5. Crea un paquete persistente con un borrador de correo editable y los cuatro documentos adjuntos.
6. El correo **no se envía automáticamente**: Recursos Humanos debe revisarlo y pulsar **Enviar correo**.

## Instalación

1. Descomprima el ZIP dentro de una ruta incluida en `addons_path`.
2. Reinicie Odoo.
3. Active el modo desarrollador.
4. Actualice la lista de aplicaciones.
5. Busque `Recruitment EC - Contratos y Décimos` e instálelo.

Dependencias: `hr_recruitment`, `hr_contract` y `mail`.

## Configuración

Abra **Contratación EC > Configuración**:

- **Plantillas**: edite o cree textos por tipo de contrato y para cada documento.
- **Automatización**: configure por compañía la creación del empleado, generación de décimos, plantilla de contrato y correo predeterminado.

En cada candidato puede seleccionar el **tipo de contrato**; el módulo escogerá la plantilla activa configurada para ese tipo. También puede definir manualmente la plantilla, fecha de inicio, fecha final y sueldo contractual.

## Consideraciones

- El módulo genera documentos administrativos configurables; la empresa debe revisar el texto legal antes de usarlo.
- La generación PDF requiere que Odoo tenga operativo su motor estándar de reportes PDF.
- El envío requiere un servidor de correo saliente configurado en Odoo.
