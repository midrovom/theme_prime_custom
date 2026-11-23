# Catastro – Políticas comerciales ERP por Excel (Odoo 18 Community)

Este módulo **no reemplaza ni modifica** los addons base de Odoo, Catastro, Loyalty ni Radis. Requiere `sale_management` y `sale_loyalty`.

## Qué incluye

- **Loyalty > reglas:** carga SKU en `loyalty.rule.product_ids` (añadir/reemplazar).
- **Loyalty > recompensas:** carga SKU y un porcentaje único en `loyalty.reward.discount_product_ids` y `discount`. Odoo solo admite **un porcentaje por recompensa**.
- **Política ERP completa:** un Excel `SKU,descuento_pct` con porcentajes distintos se agrupa por porcentaje; se crea un programa `promotion` automático independiente por porcentaje, con `loyalty.rule` y `loyalty.reward` limitadas a los mismos SKU. No se mezclan porcentajes entre productos. Se identifica cada lote por `Código política ERP`, de modo que las recargas actualizan sus programas. Con modo **Reemplazar**, los porcentajes retirados desactivan sus antiguos programas; no afectan a programas manuales.
- **Listas de precios:** desde lista existente o nueva, se pueden importar variantes por SKU con precio fijo o descuento porcentual, y cantidad mínima. Solo se actualizan las entradas `catastro_excel_managed`; los ítems creados manualmente no se sobrescriben.
- **Usuarios autorizados:** marcar «Restringir esta lista a usuarios autorizados» y añadir usuarios de la empresa. Solo esas personas podrán leer esa lista de precios por Odoo y, si la PWA utiliza el ORM sin `sudo`, también en su selección. Las listas no restringidas conservan visibilidad normal. Los usuarios requieren además los permisos nativos de Ventas/Odoo.

## Uso

1. Instalar en una **base de pruebas** con copia de seguridad.
2. Abrir **Políticas comerciales ERP > Importar Excel SKU**. También existe la opción en las vistas nativas de Loyalty, sus reglas/recompensas y Listas de precios.
3. Elegir operación, compañía, programa/lista de destino, modo de actualización.
4. Subir uno de los Excel modelo en la carpeta `static/templates` (los de ejemplo contienen SKU ficticios; sustitúyalos antes de importar).
5. Pulsar **1. Validar Excel**. Se detiene sin modificar datos si falta algún SKU, hay duplicados o un valor inválido.
6. Solo cuando la vista previa sea correcta, pulsar **2. Aplicar importación**.

## Columnas de Excel

| Tipo | Cabeceras primera hoja | Notas |
|---|---|---|
| Reglas Loyalty | `SKU` | Solo una selección de variantes. |
| Recompensa Loyalty | `SKU`, `descuento_pct` | Todas las filas de una recompensa deben tener el mismo porcentaje. |
| Política completa | `SKU`, `descuento_pct` | Admiten porcentajes distintos, agrupados en programas. |
| Lista de precios | `SKU`, `precio_fijo`, `descuento_pct`, `cantidad_minima` | Usar **uno** de precio_fijo o descuento_pct por fila. |

**SKU:** se compara con `product.product.default_code` mediante coincidencia exacta, variante por variante. Los SKU deben estar activos y vendibles, pertenecer a la compañía o ser compartidos. Si dos productos coinciden con el SKU, se rechaza el lote completo. Formatear la columna SKU como **Texto**, para no perder ceros iniciales.

**Descuento:** introducir `15` para 15 %. Introducir `0.15` representa 0,15 %, no 15 %. El importador no calcula impuestos, posiciones fiscales ni precios finales: Odoo sigue realizando esos cálculos.

**Excel:** solamente `.xlsx`, primera hoja, hasta 8 MB y 10.000 SKU; importación atómica: si falla, Odoo revierte toda la transacción.

## Seguridad y limitaciones

- La importación está disponible para Gerente de Ventas / administradores. No da acceso adicional de producto o ventas a vendedores.
- Las listas restringidas aplican una regla de registro de lectura sobre `product.pricelist`. Es importante configurar usuarios autorizados antes de restringir. No se modifica su ACL de escritura.
- Una política ERP completa crea distintos programas de promoción porcentual específicos por grupo de SKU. En cualquier política nueva, configure las **bodegas aplicables** desde el complemento de Loyalty por bodega que ya utiliza su instalación, si procede. El importador no cambia las bodegas de programas existentes.
- No convierte tarjetas regalo, recompensas de monto fijo o productos gratuitos. Su objetivo es la política plana porcentual por SKU del ERP.
- Los programas nativos Loyalty pueden representar descuentos con líneas de recompensa; las personalizaciones previas de Catastro gestionan el tratamiento por producto. Verifique cotización, Radis, impuestos y XML SRI antes de producción.
- No se incluyen aquí cambios a `conedera_odoo_census_mobile`, `stock_api_assing` ni puentes Radis.
