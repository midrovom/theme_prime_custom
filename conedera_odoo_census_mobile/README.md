# Conedera Catastro - App de Campo (Odoo 18 Community)

Addon complementario para `conedera_odoo_census` que agrega una experiencia móvil tipo web app y captura offline sin reemplazar el módulo principal.

## Objetivo

- Mantener intacto el motor actual de Catastro, visitas, proformas, permisos, bitácora y multiempresa.
- Dar al comercial una interfaz táctil y rápida para trabajo de campo.
- Permitir guardar información localmente cuando no hay cobertura y sincronizar cuando vuelve Internet.
- Evitar duplicados por reintentos de red mediante UUID idempotente por operación.

## Qué funciona offline

- Consultar los catastros descargados en la última sincronización.
- Consultar bitácora reciente descargada (visitas y proformas).
- Consultar resumen de productos proformados descargado.
- Crear una visita con mini encuesta, observaciones y fotografía.
- Crear un borrador de nuevo catastro, con tantas franjas horarias como sean necesarias.
- Editar datos y horarios de un catastro no protegido, quedando sujeto a validaciones al sincronizar.
- Ver y administrar la cola local de pendientes.

## Qué sigue siendo online

- Crear/modificar proformas estándar de Odoo.
- Solicitudes de edición y reasignación del Catastro protegido.
- Administración de permisos, equipos y compañías.
- Cualquier operación que dependa de información transaccional en tiempo real.

## Seguridad y consistencia

- La cola usa un UUID único. Un reintento no crea dos visitas ni dos catastros.
- Al crear un catastro, la app muestra coincidencias por nombre o RUC/cédula: de la copia local sin cobertura, y del servidor al estar online.
- Puede seleccionar un cliente de Odoo que aún no es catastro para completar su ficha **sin duplicarlo**. Los catastros ya registrados se abren en lugar de crearlos otra vez.
- Un RUC/cédula capturado offline se vuelve a validar globalmente al sincronizar.
- Las actualizaciones de catastros usan `write_date`; si el servidor cambió después de la última descarga, la app devuelve conflicto y no sobrescribe silenciosamente.
- Los datos offline se guardan en IndexedDB del navegador del dispositivo.
- Existe un botón `Borrar caché local`; no borra datos del servidor.

## HTTPS

Service Worker/PWA requiere contexto seguro HTTPS. En HTTP la app funciona online y puede continuar capturando después de perder cobertura mientras la pestaña siga abierta, pero no puede garantizar apertura desde cero sin Internet.

Con HTTPS la app registra automáticamente `/conedera/sw.js`, cachea el shell y puede instalarse en la pantalla de inicio.

## Acceso

Después de instalar el addon aparece una aplicación nueva **Catastro Campo**. También puede abrirse directamente en:

`/conedera/app`

## Instalación

1. Mantener instalado `conedera_odoo_census`.
2. Copiar esta carpeta al `addons_path`.
3. Actualizar lista de aplicaciones.
4. Instalar `Conedera Catastro - App de Campo`.
5. Abrir `Catastro Campo` una vez con conexión para descargar datos.

Este addon no requiere desinstalar ni reemplazar el módulo principal.

## Cambios en 18.0.1.1.0

- Búsqueda de clientes por nombre, cédula y RUC con sugerencias online y offline.
- Selección de un cliente ya registrado sin duplicarlo; las reglas y bloqueos del módulo base se verifican nuevamente al sincronizar.
- Editor de múltiples franjas horarias por día en creación y edición, y visualización legible de días y horas en la ficha móvil.
- Detección de nombres, tipos y opciones de día del modelo de horario realmente instalado (`conedera_odoo_census`). Si el esquema no es compatible, muestra un error explícito en lugar de omitir la información.
- Las ediciones que no tocaron horarios no reemplazan los horarios existentes.
- Pantalla de catastros como inicio, con botón visible **Nuevo catastro** y soporte de cola offline existente.

### Actualización sin pérdida de datos

1. Haga una copia de seguridad de la base de datos y de sus addons.
2. Reemplace **solo** la carpeta `conedera_odoo_census_mobile`; **no desinstale** el módulo base `conedera_odoo_census`.
3. Reinicie Odoo y actualice la aplicación `Conedera Catastro - App de Campo` (`-u conedera_odoo_census_mobile` o desde Aplicaciones).
4. Abra `/conedera/app` con conexión; actualice la pantalla para instalar la nueva versión del Service Worker.
5. Verifique búsqueda, registro de dos franjas el mismo día, guardado/lectura posterior, edición protegida y sincronización tras perder cobertura.

**Limitación de validación**: este ZIP es solamente el complemento móvil. La correspondencia exacta con las clases del módulo base debe probarse en la instalación real; no se incluyó el addon base ni una base de datos de Odoo en esta entrega.

## Versión 18.0.1.2.0 — PWA integrada con módulo base 18.0.1.8.7

**Compatibilidad objetivo confirmada por inspección de código**: `conedera_odoo_census_18_community_18.0.1.8.7.zip`. Este complemento NO sustituye ni reescribe el addon base.

### Paridad de flujos del módulo original

- La búsqueda global ya utiliza el método **`conedera.census.customer.lookup.wizard.search_global_candidates` del módulo original**. Ofrece coincidencias de nombres, nombres comerciales, cédula y RUC y devuelve el estado de uso, visualización o solicitud sin exponer los datos privados de otros comerciales. La consulta solo funciona online; offline se usan los catastros previamente descargados y cualquier alta se revalida al sincronizar.
- Si el contacto existe sin catastro y el módulo original permite reutilizarlo, la PWA **activa la ficha existente** en lugar de crear duplicados. Si pertenece a otro comercial, permite solicitar reasignación cuando Odoo lo autoriza.
- Los horarios usan **`conedera.partner.opening.hour`** (`day_of_week`, `opening_time`, `closing_time`) con varios turnos por día, validación de superposiciones y compatibilidad con cierre a las 24:00. No se modifican cuando se editan otros campos de un catastro.
- El estado de la solicitud de edición y el motivo de rechazo provienen de los campos calculados del módulo base. La PWA puede crear una solicitud de habilitación de catastro protegido y actualizar sus estados por medio del botón Actualizar.
- Visitas: banderas de Sí/No convertidas a las selecciones `yes/no` que espera el módulo base, observaciones, próxima visita, fotografía y GPS. La validación de catastro completo y permisos sigue a cargo del módulo original.
- Clasificación del cliente, negocio, marcas y GPS del local; captura de datos y cola de envío cuando el dispositivo está offline.

### Experiencia de uso

- **Pantalla pequeña**: navegación fija inferior, tarjetas, formularios táctiles y franjas horarias ampliables.
- **Escritorio**: navegación lateral persistente, espacio de trabajo a todo lo ancho, indicadores de actividad y lista de catastros en columnas. No se limita a una maqueta estrecha de teléfono.
- Iconos PNG 192/512 y variante maskable, Service Worker revisado, manifiesto instalable en navegadores compatibles bajo **HTTPS**.
- Verificación de identidad/empresa: si cambian entre la última descarga y la sesión online, **no se sincroniza automáticamente la cola del usuario anterior**. La persona debe volver a su sesión previa o elegir explícitamente borrar la información local (advertencia de pérdida de pendientes).

### Despliegue controlado

1. Respaldar base de datos, código de addons y adjuntos antes de aplicar actualizaciones.
2. Conservar instalado el addon base versión 18.0.1.8.7; instalar o **actualizar solamente** `conedera_odoo_census_mobile` a 18.0.1.2.0 (`-u conedera_odoo_census_mobile`).
3. Reiniciar los procesos de Odoo, cargar de nuevo `/conedera/app` con conexión y comprobar el cambio de Service Worker. Servir Odoo con HTTPS válido para instalación y apertura offline tras precarga.
4. Validar en **base de pruebas** los siguientes casos antes de producción: coincidencia de otro comercial, selección de contacto existente, doble turno de lunes, catastro propio protegido, solicitud rechazada y comentario, visita GPS, operación sin señal y reconexión, cambio de sesión/compañía.

### Alcance y límites

Este ZIP fue sometido a validación estática de XML/Python/JavaScript y pruebas unitarias de lógica JS, **no** a una actualización real contra una base PostgreSQL de Odoo 18. No se garantiza compatibilidad con personalizaciones adicionales ajenas a las dos versiones inspeccionadas. La creación y administración de proformas, aprobación de solicitudes por supervisores y funciones administrativas avanzadas continúan disponibles en las pantallas del módulo base de Odoo; la PWA dispone de enlaces a esas pantallas. El cache offline de IndexedDB guarda información empresarial en el dispositivo: requiere dispositivos de confianza y medidas de protección de sesión y almacenamiento adecuadas.
