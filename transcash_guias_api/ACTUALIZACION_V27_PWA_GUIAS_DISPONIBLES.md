# Transcash Guías API 2.7 – Corrección de guías invisibles en la PWA

## Problema confirmado

En v2.6 la consulta inicial exigía igualdad SQL directa sobre `transcash.guia.chofer_usuario_id` y `proveedor_id.commercial_partner_id`. El registro ERP puede conservar `chofer_contacto_id`, `ruc_chofer` y datos del transportista en `tc.guide` sin haber completado los Many2one operativos. La búsqueda los excluía antes de validar su identidad y por eso la PWA mostraba 0 guías.

## Cambios

- Conserva las tres condiciones obligatorias: transportista, chofer y destino seleccionados en la ruta.
- Consulta solo guías `registrada`, de la misma compañía, sin ruta ni embarque; valida el origen `tc.guide` si faltan relaciones operativas.
- Chofer por usuario directo, o identidad fiscal/cédula coincidente con el contacto ERP y el login/contacto del usuario seleccionado.
- Transportista por empresa comercial o RUC normalizado. Si el ERP no suministra RUC, acepta **solo nombre legal exacto** y descarta homónimos fiscalmente distintos o sin identificación inequívoca.
- Destino por el maestro, código ERP o nombre de ciudad/lugar **exacto** de la fuente. No presume que destinatario y destino sean el mismo sitio.
- Al guardar una selección verificada, vincula los Many2one faltantes exclusivamente a las guías seleccionadas; nunca modifica guías asignadas, entregadas o de otra compañía. Incluye bloqueo de filas, token de concurrencia y `savepoint`.
- `Seleccionar todas` se aplica solamente a las guías compatibles mostradas, hasta 100.
- Se muestra un resumen de guías libres, revisadas y compatibles, además de cuántas no coinciden por destino, chofer o transporte. Si se superan 6.000 guías candidatas o 400 compatibles, indica usar búsqueda concreta.
- La PWA sigue disponible solo para operadores internos/jefes autorizados de la compañía de la ruta.
- No cambia seguridad comercial, permisos Portal, API Administrator, facturación, embarques ni liquidaciones.

## Instalación

1. Hacer respaldo de base y del addon `transcash_guias_api` vigente (v2.6).
2. Sustituir solo la carpeta `transcash_guias_api` por la versión 2.7.
3. Reiniciar el servicio Odoo; actualizar el addon en Aplicaciones.
4. Refrescar la PWA (incluido el service worker/caché instalado si sigue mostrando la versión anterior).
5. Crear/abrir una hoja de ruta **en borrador** con compañía, transportista, chofer y destino, y comprobar el resumen de filtros antes de marcar.
6. Guardar una sola guía; confirmar la ruta solo tras comprobar que el detalle tiene el contacto/usuario/transportista correctos.

## Si el contador sigue en cero

- `Guías libres en la compañía = 0`: no hay guías en estado `registrada` sin ruta/embarque en esa empresa. Verificar sincronización/publicación/estado.
- `No coinciden con destino`: homologar en el maestro el destino ERP exacto; no seleccionar arbitrariamente otro almacén.
- `No coinciden con chofer`: cotejar `ruc_chofer`, `chofer_contacto_id`, cédula del usuario Portal y cuenta vinculada.
- `No coinciden con transportista`: cotejar el RUC real, `transport_partner_id`, `transport_tax_raw` y nombre legal; resolver duplicados ambiguos.
- Contador **límite**: buscar por número de guía para reducir el universo.

Se adjuntan `docs/diagnostico_pwa_v27.sql` (consultas de solo lectura) y `docs/test_filtro_pwa_v27.py` (pruebas locales). Sin conexión a la base de producción, el resultado definitivo requiere la prueba en Odoo 18.
