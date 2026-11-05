# Catastro PWA 18.0.1.5.23 — One2many de bodegas y stock comparativo

- Administración: **Catastro → Configuración → Bodegas para cotizar por usuario** ahora abre una **ficha de usuario** con una tabla One2many editable para agregar varias bodegas en la misma pantalla.
- Se reutiliza el modelo `catastro.quote.warehouse.access` y sus asignaciones previas; no se elimina ni migra información.
- La validación original sigue impidiendo asignar bodegas de compañías no permitidas al usuario y registrar bodegas duplicadas.
- Tarjetas PWA: bloque de **Stock en bodegas** por producto; bodega seleccionada visible primero, otra a continuación y opción de desplegar el resto. Incluye existencias 0 para información completa.
- Usuarios Tienda: consulta todas las bodegas de la compañía activa, aun cuando solo puedan cotizar en sus bodegas asignadas.
- Otros usuarios: consulta exclusivamente las bodegas asignadas. No se expone stock de otras compañías.
- Detalle de ubicaciones internas se mantiene en un desplegable independiente.
- La cotización y los envíos a Radis siguen usando exclusivamente la bodega autorizada elegida.
- Stock por bodega y ubicaciones no se guarda en la caché offline. Es información de consulta en línea.

## Instalación

1. Respaldar PostgreSQL y filestore; sincronizar operaciones offline pendientes.
2. Reemplazar la carpeta `conedera_odoo_census_mobile` sin desinstalar.
3. Reiniciar los workers y actualizar el módulo desde Aplicaciones o `-u conedera_odoo_census_mobile`.
4. Abrir `/catastro/app?version=18.0.1.5.23`.
5. Confirmar con usuario Tienda (lectura compañía completa) y Campo (lectura limitada).

**No se ha ejecutado contra PostgreSQL/Odoo en este entorno**; verificar en ambiente de pruebas antes de producción.
