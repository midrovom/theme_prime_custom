# Catastro PWA v18.0.1.5.18 — Proformas de Consumidor Final, PDF y WhatsApp

## Acceso

En la PWA, `Cotizar` -> `Venta directa · Consumidor Final` -> `Buscar proformas`. También existe acceso desde la pantalla inicial de Tienda. Requiere el grupo **Catastro PWA: cotizador de tienda**, contacto Consumidor Final configurado por empresa y permisos de lectura de Ventas.

- Busca por número de cotización o referencia externa, entre `draft` y `sent`, respetando compañía y las reglas de registro de `sale.order`.
- Muestra bloques de 20 proformas por petición con paginación; no descarga todo el historial.
- `Ver proforma` abre su detalle y las acciones disponibles para el usuario.
- `Duplicar` crea **un nuevo borrador** con el `copy()` nativo y preserva la original. Mantiene la condición de pago si sigue activa. Restaura base de precios antes de recalcular el recargo para que no se aplique dos veces. Recalcula las recompensas con `sale_loyalty`, si está instalado. Bloquea el copiado desde Tienda de cotizaciones con `negotiable_price` existente. En caso de diferencias introducidas por personalizaciones, cancela la transacción con un error en vez de crear una copia incompleta.
- Después de duplicar, revisar precios, promoción y disponibilidad de stock. La copia no reserva inventario.

## PDF

La ruta autenticada `/catastro/app/quote/pdf/<ID>` genera el PDF a partir de `sale.action_report_saleorder` (el reporte QWeb de Odoo), utilizando las reglas de registro, el usuario y la empresa activos. No crea enlaces públicos a la cotización ni modifica el borrador. La impresión necesita el motor PDF instalado y configurado en Odoo.

## WhatsApp

- `Compartir PDF` intenta el diálogo de compartir archivos del navegador (Web Share API). En un teléfono compatible, el vendedor elige WhatsApp y el destinatario.
- Si el navegador no soporta compartir archivos, se descarga el PDF para adjuntarlo manualmente.
- `Abrir chat de WhatsApp` admite números internacionales (+código), con el formato local 09XXXXXXXX para Ecuador. El texto se prepara para ese chat; **no adjunta ni envía el PDF automáticamente**. El número no se guarda en el contacto Consumidor Final.
- Para enviar directamente el PDF al número sin intervención se requiere **WhatsApp Business Platform/Cloud API** o una integración de Odoo ya configurada con número emisor, permisos, plantillas y consentimiento. No está incluido en este módulo.
- Web Share con archivos suele requerir HTTPS y un navegador compatible; mediante HTTP queda disponible el método de descargar y adjuntar.

## Instalación segura

1. Respaldar PostgreSQL y la carpeta de módulos. Sincronizar operaciones offline pendientes.
2. Reemplazar **únicamente** la carpeta `conedera_odoo_census_mobile` por esta versión, sin desinstalar el módulo ni borrar IndexedDB.
3. Reiniciar el servicio Odoo y los workers. Actualizar el módulo (no solamente refrescar el navegador).
4. Abrir `/catastro/app?version=18.0.1.5.18` y confirmar versión de cliente y servidor.
5. Probar búsqueda, duplicación y PDF real con los permisos de la tienda. También probar con una promoción Loyalty y forma de pago con recargo para detectar interferencias con módulos personalizados.

**Validación local:** sintaxis Python y JavaScript, estructura XML e interfaz con servidor simulado en móvil y escritorio. **Pendiente:** instalación, `copy()`, generación QWeb del PDF y reglas de promociones en la base real de Odoo. No se modificó el módulo base.
