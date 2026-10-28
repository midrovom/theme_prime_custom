# v2.33 — Aviso de correo al trabajar en la PWA

## Causa

En Odoo 18, `mail.thread.message_post()` valida `email_from` del usuario
que crea el mensaje y eleva `UserError` antes de enviarlo cuando el contacto
no tiene correo. Por eso al escribir notas automáticas en rutas o embarques
puede fallar un POST, con el mensaje «No se puede enviar el mensaje, configure
la dirección de correo electrónico del remitente».

## Corrección

- Las notas de auditoría interna de transporte del cliente y la homologación
  de guías se guardan mediante `mail.thread._message_log()` (sin envío de correo).
- Los POST del centro de operaciones marcan su contexto como
  `tc_pwa_audit_note` y `mail_notify_force_send=False`.
- Solo las notas automáticas simples (`body` y, si existen, `message_type` o
  `subtype_xmlid='mail.mt_note'`) usan `_message_log` en hojas de ruta,
  embarques y guías; el resto usa `message_post` original.
- No se atrapan ni ocultan excepciones de guardado, acceso, foto o estado.
- No se altera el proceso de facturas, liquidaciones o correos comerciales.

## Prueba manual

1. Copiar la base a un entorno de pruebas, iniciar sesión como operador
   interno con `res.partner.email` vacío.
2. Con un embarque **en preparación**, subir una foto válida a una hoja de
   ruta, comprobar que quede registrada una sola vez en evidencias y en la
   bitácora y que no aparezca el error del remitente.
3. Revisar la ficha del embarque desde «Viajes» (sin un parámetro `?error=`
   antiguo en la URL).
4. Intentar subir un archivo inválido o confirmar una ruta no apta: se debe
   seguir mostrando la validación operativa.
5. Verificar el flujo de aprobación del jefe y notificaciones financieras;
   esos correos siguen requiriendo una configuración de remitente real.

Nota: el mensaje persistirá en una URL histórica que ya contiene `?error=...`.
Navegar desde «Viajes» abrirá la ficha sin ese parámetro.
