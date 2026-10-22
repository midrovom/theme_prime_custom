# Transcash Guías API 18.0.2.9.0 — Filtro PWA por proveedor operativo

## Causa

El filtro anterior revisaba `tc.guide.transport_tax_raw` y `tc.guide.transport_partner_id` ANTES de `transcash.guia.proveedor_id`. Un dato legado/pendiente de homologación podía descartar una guía cuyo proveedor ya coincidía con la ruta. El contador `transporte` del diagnóstico anterior indicaba *rechazadas por transporte* y no *coincidentes*.

## Cambio

- Se considera en primer lugar `transcash.guia.proveedor_id` comparado con `transcash.hoja.ruta.proveedor_id`.
- Comparación por `commercial_partner_id`, y, para contactos duplicados, RUC fiscal normalizado cuando existe en ambas partes.
- Si `proveedor_id` está asignado a otra empresa (RUC diferente), NO se permite elegir esa guía aunque la fuente ERP sea distinta.
- Los datos `tc.guide.transport_*` se usan únicamente cuando la guía operativa NO tiene `proveedor_id`.
- Al guardar, solo se llena `proveedor_id` si está vacío; no se cambia el proveedor que ya tenía una guía.
- Diagnóstico PWA: incorpora **Coinciden con destino**, **Coinciden con chofer**, **Coinciden con proveedor de transporte**, contados de manera independiente. **Guías compatibles** cuenta solo las que cumplen los tres filtros simultáneamente.
- Los valores `destino`, `chofer`, `transporte` antiguos en el reporte se siguen usando únicamente como número de rechazadas según la primera causa, para conservar compatibilidad interna.

## Instalación

1. Respaldar BD y addon actual.
2. Reemplazar solamente el directorio `transcash_guias_api`.
3. Reiniciar Odoo y actualizar el módulo `transcash_guias_api`.
4. Refrescar la PWA y entrar en Hoja de ruta > Agregar guías.
5. Comparar el proveedor de la ruta y el campo **Proveedor** de la guía operativa; deben coincidir por partner comercial o RUC.

## Comprobaciones

- `python docs/test_filtro_pwa_v27.py`
- `python docs/test_filtro_proveedor_v29.py`

Si una guía sigue sin aparecer, comprobar que el estado sea `registrada`, no esté asignada a otra ruta/embarque y coincida también con chofer, destino y empresa Odoo.
