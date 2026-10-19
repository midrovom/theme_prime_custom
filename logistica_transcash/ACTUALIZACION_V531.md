# Transcash V5.31 — Retiro de controles obsoletos por guía

La facturación y el pago del transporte se manejan exclusivamente por **embarque**. La hoja de ruta es el agrupador operativo de guías. Las guías permanecen en el sistema como documentos ERP, detalle de entrega y soporte de incidencias y evidencias, nunca como una unidad de liquidación.

## Navegación actual

- **Operación logística → Hojas de ruta**: crear la hoja, definir chofer, proveedor, destino y **Agregar / quitar guías** (proceso activo).
- **Operación logística → Guías para armar rutas**: consulta restringida a guías registradas y todavía no vinculadas a otra ruta o embarque; no ofrece facturación ni edición libre.
- **Operación logística → Embarques**: administrar viajes, rutas, entregas, evidencias y tarifa única.
- **Contabilidad · Transporte → Bandeja contable / Liquidaciones y pagos / Transferencias y conciliación**: liquidaciones por viaje, facturas, pagos y confirmaciones.
- **Control de novedades**: sigue vigente para gestionar daños, roturas y recepción de clientes, **no es un flujo de cobro por guía**.

## Desactivado

- Liquidaciones antiguas (por guía).
- Guías en curso (antiguo control operativo independiente de las rutas).
- Incidencias (vista antigua y duplicada por guía; se mantiene Control de novedades).
- Aprobar evidencias de carga (flujo antiguo vinculado a guía; ahora la evidencia de carga se registra por ruta en el embarque).
- Iniciar carga (guía antigua) y Autorizar salida en el formulario individual de guía.
- Filtro «Lista para pago» en la consulta de guías.

Las acciones XMLID heredadas siguen existiendo y, cuando procede, redirigen a embarques, novedades o liquidaciones por viaje. Los asistentes históricos inactivos se conservan por seguridad de actualización y no conceden acceso financiero.

**No se eliminan** guías, rutas, embarques, firmas, videos, evidencias, liquidaciones, facturas, pagos, incidencias ni sus archivos. No se modifica ninguna tabla ni se altera el contenido histórico.

## Instalación

1. Respaldar PostgreSQL, filestore y addon V5.30.
2. Sustituir `logistica_transcash` por V5.31 en addons_path. **No desinstalar**.
3. Reiniciar Odoo y actualizar el módulo desde Aplicaciones o usando `-u logistica_transcash` sobre una copia.
4. Recargar escritorio y comprobar: guías se seleccionan desde una hoja, el viaje muestra su costo único, Contabilidad solo liquida viajes, y los cuatro menús antiguos desaparecen.

Validación de sintaxis y referencias XML estática; se requieren pruebas de instalación con Odoo 18 para certificar el despliegue.
