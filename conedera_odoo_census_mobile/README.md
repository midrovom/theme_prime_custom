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
- Crear un borrador de nuevo catastro.
- Editar datos de un catastro no protegido, quedando sujeto a validaciones al sincronizar.
- Ver y administrar la cola local de pendientes.

## Qué sigue siendo online

- Crear/modificar proformas estándar de Odoo.
- Solicitudes de edición y reasignación del Catastro protegido.
- Administración de permisos, equipos y compañías.
- Cualquier operación que dependa de información transaccional en tiempo real.

## Seguridad y consistencia

- La cola usa un UUID único. Un reintento no crea dos visitas ni dos catastros.
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
