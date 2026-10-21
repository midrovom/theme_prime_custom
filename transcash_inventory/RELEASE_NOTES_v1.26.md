# TRANSCASH Inventory v1.26 — reparación estructural del dashboard

## Causa reproducida

El código antiguo reemplazaba el `innerHTML` completo de `.risk-banner` cuando `suspiciousStock` era falso. Eso eliminaba `#warehouseWarning`, que se utilizaba en `update()` y ocasionaba `Vista desactualizada: falta elemento #warehouseWarning`. Se confundía una excepción de presentación con ausencia de importaciones.

## Corrección

- La advertencia de calidad se actualiza solo mediante `#stockQualityMessage`, conservando `#warehouseWarning` y la estructura del documento.
- Una advertencia auxiliar de bodega no impide actualizar los KPI si falta accidentalmente en alguna plantilla.
- Se comprobaron las referencias DOM estáticas y se cambió el nombre de los recursos (`dashboard_v126.js`, `dashboard_v126.css`) para evitar mezclas en caché con versiones anteriores.
- Se actualizó el iframe y el manifiesto a `18.0.1.26.0`.
- No se alteran controladores, modelos, importación por API Administrator, seguridad, fotos, ChatGPT, cálculos ni tabla de hechos.

## Despliegue

Realizar respaldo; reemplazar la carpeta del módulo; reiniciar Odoo; actualizar módulo (sin desinstalar); recargar interfaz. El recurso HTML del panel debe cargar `dashboard_v126.js`. Revisar el monitor de consola y las pestañas con filtros de período/categoría/marca/formato/proveedor/bodega. La instalación no ha sido ejecutada contra el servidor de producción.
