# v1.46 - Reparación de miniaturas (no altera inventario)

Problema: registros `status=verified` podían conservar ese valor aunque `image_thumbnail`
(attachment de Odoo) fuese nulo, estuviera dañado, no existiera en filestore
o devolviese una cadena de `bin_size` en lugar de base64 real.

- Verificación de la firma JPEG almacenada para reportar solo miniaturas existentes.
- La ruta `/photos/thumb` lee los bytes con `bin_size=False`, con ACL por empresa
  y sin otorgar permisos de escritura al usuario de consulta.
- La búsqueda de imagen entre empresas no copia miniaturas vacías o inválidas.
- La cola y el cron detectan imágenes históricamente verificadas sin miniatura.
- La reparación intenta primero la URL pública verificada guardada y conserva
  la asociación del SKU si la tienda no responde temporalmente.
- En el formulario **Imágenes vinculadas**, botón **Reparar miniatura** para
  administradores/responsables; proceso automático cron cada 15 minutos.
- No se modifica la importación API, datos, análisis ABC/XYZ, IA, ni dashboard móvil.

## Diagnóstico en producción

Si una base de datos fue copiada de pruebas sin el filestore, PostgreSQL conserva
las URLs y el estado verificado, pero Odoo no tiene los bytes de los archivos.
La reparación necesita acceso HTTPS saliente desde el servidor a la tienda
configurada. No debe vaciarse ni reiniciarse la tabla de fotografías.
