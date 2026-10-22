# v1.47 - Visualización de miniaturas recuperadas en backoffice (Odoo 18)

- Diagnóstico: el botón v1.46 confirmaba que el JPEG podía leerse usando `sudo`,
  pero la acción `display_notification` no refrescaba el formulario y el widget
  binario estándar `/web/image` puede no transmitir los adjuntos para los
  usuarios autorizados según la configuración real de `ir.attachment`.
- Formulario y lista de «Imágenes vinculadas»: vista HTML computada no almacenada
  a partir de la ruta autenticada `/transcash_inventory/photos/thumb`. Esta ruta
  valida usuario, permisos y empresa antes de entregar el JPEG; no revela rutas
  del filestore ni permite consultar otra empresa.
- El campo binario `image_thumbnail` original **no se borra ni se modifica**;
  no se requiere migración, reindexación, ni pérdida de vínculos/SKU.
- «Reparar miniatura» recarga la vista tras el aviso; la URL de vista previa
  añade una versión por `write_date` y el endpoint evita caché obsoleta.
- No se alteraron cálculos, consultas SQL/IA, filtros, fotografías por SKU,
  API Administrator, importaciones, perfiles, dashboards ni sincronización.

Prueba de producción: abrir un SKU, reparar, volver a la lista y observar
la fotografía; comprobar además GET `/transcash_inventory/photos/thumb?sku=...`
como usuario con grupo de consulta. Si endpoint responde 200 JPEG y el HTML
no carga, examinar reglas CSP/proxy en la pestaña Network del navegador.
