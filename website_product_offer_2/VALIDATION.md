# Validación técnica

Versión revisada: `18.0.1.0.0`

## Controles ejecutados antes del empaquetado

- Compilación de todos los archivos Python.
- Importación aislada de modelos y controladores para detectar símbolos o dependencias faltantes.
- Parseo estricto de todos los XML con `lxml`.
- Validación del manifiesto, rutas de archivos, datos, seguridad y activos.
- Validación sintáctica del JavaScript con Node.js.
- Revisión de compatibilidad de vistas de Odoo 18: etiqueta `list`, expresiones directas y ausencia de `attrs`/`states` antiguos.
- Revisión de seguridad: ningún ACL para usuarios públicos; creación web únicamente por controlador validado.
- Revisión multiwebsite: habilitación, reglas, lista de precios, almacén y producto se obtienen del website actual.
- Revisión del ZIP y de su carpeta raíz.

## Pruebas automatizadas incluidas

- Conversión de una oferta aprobada a presupuesto nativo.
- Conservación de producto, cantidad, precio, website y vínculo de origen.
- Rechazo de cantidades no positivas.
- Contraoferta y conversión con el precio aceptado por el cliente.

## Pruebas funcionales recomendadas en la instancia

La base real puede contener temas y módulos personalizados que cambien vistas estándar. Antes de publicar, instalar en una copia de la base y verificar:

1. Website mayorista con ofertas activas y website público con ofertas desactivadas.
2. Producto con variantes y stock en el almacén asignado al website.
3. Envío como visitante y como usuario portal.
4. Contraoferta, aceptación desde el correo/portal y creación del presupuesto.
5. Impuestos, posición fiscal y lista de precios usados por la empresa.

