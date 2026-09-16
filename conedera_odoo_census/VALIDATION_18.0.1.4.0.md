# Validación técnica — 18.0.1.4.0

## Resultado
**Validación estática: APROBADA.**

Se revisó el paquete final con los siguientes controles:

- 24 archivos Python parsean/compilan correctamente.
- 13 XML parsean correctamente.
- 81 IDs XML explícitos sin duplicados.
- 30 botones `type="object"` apuntan a métodos Python presentes.
- 15 filas de ACL referencian modelos definidos por el módulo.
- Manifiesto 18.0.1.4.0, dependencias, archivos de datos y assets presentes.
- JavaScript del widget GPS pasa `node --check`.
- Búsqueda por RUC/cédula usa normalización que ignora separadores.
- El wizard muestra y reutiliza los datos del `res.partner` existente.
- La Bitácora contiene vista Kanban móvil y acción de vista completa.
- El resumen por producto usa líneas reales de `sale.order`/`sale.order.line` y excluye documentos cancelados y anticipos.
- El historial por producto tiene orden descendente por fecha.
- La ficha estándar de `product.template` incluye cantidad, importe, precio promedio y última proforma, más acceso al historial.
- Existe migración 18.0.1.4.0 que verifica las tres vistas SQL analíticas después del upgrade.
- No se distribuyen `__pycache__` ni `.pyc`.

## Validaciones contra Odoo 18 oficial
Se contrastó con el código/documentación oficial de Odoo 18 que:

- `sale.order` usa `date_order`, `state`, `currency_id`, `user_id`, `amount_total`.
- `sale.order.line` usa `product_id`, `product_uom_qty`, `product_uom`, `price_unit`, `discount`, `price_subtotal`, `is_downpayment`.
- `product.product_template_form_view` contiene `button_box` y `list_price_uom`, usados por la vista heredada.
- los campos relacionales soportan modo `kanban` y Odoo 18 prioriza Kanban en pantallas móviles.
- los modelos `_auto = False` con vistas SQL son el mecanismo documentado para reportes calculados.

## Límite de esta validación
Este entorno no contiene un servidor Odoo 18 + PostgreSQL ejecutable, por lo que no se pudo ejecutar una instalación real ni el test suite de Odoo. La validación definitiva es ejecutar `-u conedera_odoo_census --stop-after-init --no-http` sobre una copia de la base y completar el checklist funcional del archivo de actualización.
