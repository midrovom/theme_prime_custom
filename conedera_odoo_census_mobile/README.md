**Última actualización:** consulte [ACTUALIZACION_18.0.1.5.9.md](ACTUALIZACION_18.0.1.5.9.md) para stock por bodega, Loyalty, permisos de precio negociado, recargos y venta a consumidor final.

**Actualización nueva:** consultar [`ACTUALIZACION_18.0.1.5.0.md`](ACTUALIZACION_18.0.1.5.0.md) para URL `/catastro`, cotizaciones PWA y restricciones por personalizaciones comerciales.

# Catastro - App de Campo · Odoo 18 Community

**Versión del complemento:** `18.0.1.5.9`  
**Dependencia:** `conedera_odoo_census` `18.0.1.8.7` o posterior (para esta entrega se incluye `18.0.1.8.8`)

Este complemento no modifica el módulo original. La PWA funciona como opción independiente en **Catastro → Abrir Catastro PWA** o en `/conedera/app`; Odoo y el resto de los módulos continúan en `/web`. En escritorio presenta menú lateral y en móvil navegación inferior.

## Cambios incluidos

1. **Finalizar y proteger desde el formulario nuevo.** Al pulsar ese botón la PWA valida datos mínimos; en la sincronización Odoo ejecuta `res.partner.action_register_census()`, con todas las verificaciones originales de completitud, compañía, equipo y permisos. También está disponible **Finalizar y proteger** desde un catastro en borrador.
2. **Guardar borrador** separado del cierre. Si falla el intento de cierre durante la creación, la ficha se conserva como borrador con una advertencia visible y puede completarse después. Nunca se muestra como protegida sin confirmación de Odoo.
3. **Solicitar edición de catastro protegido** desde su ficha. El responsable envía un motivo utilizando el asistente original `conedera.census.unlock.wizard`, que aplica los permisos y envía la solicitud al supervisor.
4. **Actualizar estado de solicitud**, con estados pendiente/aprobada/rechazada/vencida y motivo de rechazo. Tras una aprobación, el usuario autorizado puede editar y **Finalizar edición**. Esa acción cierra el permiso temporal mediante el método del módulo original.
5. **Búsqueda de clientes** por nombre, RUC o cédula usando el buscador global del módulo base. Reutiliza contactos existentes disponibles, sin asumir propiedad de fichas de otro vendedor.
6. **Horarios** de múltiples días y varias franjas al día con validaciones de solapamiento; usa exactamente `conedera.partner.opening.hour.day_of_week/opening_time/closing_time`.
7. **Visitas** únicamente cuando el catastro esté protegido; las respuestas de la mini encuesta usan los valores de selección que espera Odoo (`yes/no`) y se finalizan con `action_mark_done`.
8. **PWA y offline**: conserva catastros y operaciones en IndexedDB, con UUID para reintentos idempotentes. El cierre sin señal queda pendiente; la protección real ocurre al sincronizar con Odoo. Solicitar/aprobar la edición requiere conexión.
9. **GPS** opcional para local y visitas; fotografía opcional para visitas, con HTTPS para permisos del navegador.
10. **Acceso aislado:** la PWA no interfiere con `/web`. Service Worker limitado a su página y recursos, sin interceptar otros módulos. Menú existente actualizado como submenú, sin duplicarlo.
11. **Protección de sesión:** antes de sincronizar se verifica usuario y compañía para impedir enviar operaciones offline con otra sesión.

## Actualizar

1. Realice **backup** de base de datos y carpeta de complementos. Ensaye primero en una **copia de pruebas**.
2. Conserve instalado e intacto `conedera_odoo_census` versión `18.0.1.8.7`.
3. Reemplace **solo** la carpeta `conedera_odoo_census_mobile` en el directorio del `addons_path` (no mezcle archivos de versiones anteriores).
4. Reinicie Odoo y actualice la aplicación en la base correspondiente, por ejemplo:
   `./odoo-bin -d NOMBRE_BD -u conedera_odoo_census_mobile --stop-after-init`
   (adapte el ejecutable y la configuración del servicio a su instalación).
5. Vuelva a iniciar Odoo, entre a `/web`, abra **Catastro → Abrir Catastro PWA** o navegue directamente a `/conedera/app`.
6. Con conexión, recargue la PWA para que se actualicen sus archivos y el Service Worker. Si los recursos antiguos persisten, cierre y vuelva a abrir la PWA instalada; no borre datos del dispositivo mientras haya pendientes sin sincronizar.

## Casos de aceptación a probar en Odoo real

- Crear catastro con todos los datos obligatorios → **Finalizar y proteger** → confirmar campo `census_locked=True` y que **Nueva visita** se habilita.
- Crear catastro incompleto → **Guardar borrador** → editar faltantes → **Finalizar y proteger**; no debe quedar protegido antes de completar los requisitos.
- Crear borrador sin cobertura con finalización solicitada → mostrar operación pendiente; al recuperar señal, revisar el estado de sincronización, no dar por protegido antes de respuesta exitosa.
- Catastro protegido propio → **Solicitar habilitación** con motivo → supervisor aprueba/rechaza en Odoo → **Actualizar estado**; rechazo muestra `review_note`, aprobación habilita edición únicamente al usuario y durante el plazo original.
- Editar durante habilitación → guardar cambios → sincronizar → **Finalizar edición** → volver a bloqueado.
- Registrar visita finalizada con mini encuesta; en Odoo la visita debe quedar `state=done`.
- Revisar la búsqueda de clientes existentes, pertenencia a equipo, horarios con más de un turno y que otro módulo de Odoo siga navegable desde `/web`.
- Probar en iOS/Android y pantalla de escritorio; con otra cuenta de Odoo el dispositivo no debe sincronizar operaciones pertenecientes a una cuenta distinta.

## Alcance de validación

Se ha realizado análisis de código del módulo principal `18.0.1.8.7`, pruebas de sintaxis Python/JavaScript, parseo XML, pruebas de lógica de horarios y validación de completitud, y pruebas automatizadas del DOM de la PWA en anchos móvil y escritorio **con datos simulados**.

**No se ha ejecutado una instalación ni la transición real de estados en su servidor Odoo/PostgreSQL.** Una versión previa `18.0.1.3.0` fue generada en el historial, pero sus bytes no estaban disponibles para una comparación directa en este entorno; esta versión integra las funciones solicitadas tomando el módulo móvil adjunto `18.0.1.0.0` y el módulo original `18.0.1.8.7` como fuentes verificables. Es recomendable probar en staging antes de reemplazar el complemento en producción.

## Marca neutra, sin cambiar los identificadores

En esta versión, Odoo muestra **Catastro** como nombre de la aplicación principal y
**Catastro - App de Campo** para el complemento. La barra lateral de escritorio
muestra **CATASTRO** en vez del nombre de una empresa. La PWA instalada conserva
el título **Catastro de Campo**.

Se conservan la ruta `/conedera/app`, los nombres técnicos de los módulos,
modelos, XML IDs, tablas, permisos, datos existentes, lógica y flujo offline.
El nombre de autor en los metadatos sigue reflejando el desarrollo original;
no es el nombre que se muestra en el menú.

Para reflejar los nombres nuevos en Odoo, actualizar **ambos** módulos (`-u
conedera_odoo_census,conedera_odoo_census_mobile`) en una base de pruebas.
Recargar la aplicación con conexión para renovar el Service Worker y el
manifest de instalación. Si se instaló como PWA en la pantalla de inicio,
el sistema operativo puede necesitar que se cierre y reabra o que se vuelva
a instalar el acceso directo para refrescar el nombre. No borrar datos
locales si quedan operaciones pendientes sin sincronizar.


## Versión 18.0.1.5.7 — integración de precio negociado existente

Consulte `ACTUALIZACION_18.0.1.5.7.md` para la integración exclusiva con el campo personalizado `sale.order.line.negotiable_price` de Odoo, sin crear campos ni sobrescribir `price_unit`. Las funciones de catálogo visual, listas, fotografías, stock y selección múltiple implementadas en 18.0.1.5.5 se conservan.
