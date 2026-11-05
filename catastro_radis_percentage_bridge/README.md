# Catastro — Puente porcentajes Radis (Odoo 18)

## Propósito

**No cambia ningún archivo de `stock_api_assing`.** Este módulo hereda
`api.administrator.call_api` y solamente añade dos claves en los productos y el código ERP de la forma de pago en cabecera
enviados en la llamada `POST check_update_qoutes`, tanto desde el botón
`Enviar a Radis` como desde el cron original.

- `discount_percent`: valor efectivo de `sale.order.line.discount`, incluso Loyalty.
- `increase_percent`: `sale.order.line.catastro_payment_surcharge_percent`
  solo si `catastro_payment_surcharge_applied` está activo; en los demás casos 0.

- `order_payment_code`: código ERP (texto) de `catastro.quote.payment.option.erp_code`,
  en la cabecera de cada cotización que tenga una condición PWA seleccionada.
  Ejemplo: `"order_payment_code": "TC03"`. Un código `"001"` conserva sus ceros.

**Antes del envío:** en Catastro → Configuración → Condiciones de pago PWA,
complete el campo **Código ERP** de cada forma de pago. Si una proforma tiene
esa condición seleccionada pero no un código, la exportación se detiene con
un error claro, antes de llamar a Radis. Las proformas antiguas creadas fuera
de la PWA sin condición de pago PWA no reciben un código inventado ni se bloquean.

No reemplaza `price_unit` ni `negotiable_price`; conserva el resto del JSON.
No genera columnas nuevas, no modifica estados y no implementa HTTP ni credenciales.

### Ejemplo ilustrativo de una línea

```json
{
  "sku": "ART-001",
  "quantity": 2.0,
  "price_unit": "105.0",
  "discount_percent": 10.0,
  "increase_percent": 5.0
}
```

**Atención:** `price_unit` ya incluye el incremento. Radis **no debe aplicarlo otra
vez**. Los campos son porcentajes numéricos (no valores monetarios), con hasta
cuatro decimales. La aceptación de estas claves por Radis debe confirmarse
con el equipo responsable de su API.

## Instalación

1. Respaldar la base y el filestore. Confirmar `stock_api_assing` original instalado.
2. Actualizar la PWA `conedera_odoo_census_mobile` a 18.0.1.5.26.
3. Instalar o actualizar la carpeta **independiente** `catastro_radis_percentage_bridge`.
4. Reiniciar todos los workers Odoo; actualizar lista de aplicaciones e instalar puente.
5. Enviar UNA cotización de prueba y verificar el payload realmente recibido en Radis.
   Repetir con el cron (en una instancia de pruebas).

### Seguridad y compatibilidad

- Busca cada `sale.order` por **empresa y número**, usando `sudo()` solo para
  poder procesar el cron del módulo original. No modifica registros.
- Valida orden, SKU, bodega, cantidad y precio antes de añadir datos al JSON.
  Ante inconsistencias detiene el envío en lugar de atribuir un porcentaje
  a otro producto.
- No cambia rutas de PWA, módulos base, almacenamiento offline ni permisos.
- Si no está instalado el puente, la PWA bloquea proformas con descuento o
  incremento para evitar perder esos valores en el envío.
- La exportación automática existente de Radis mantiene los mismos criterios
  originales para elegir órdenes. Este puente solo agrega campos al JSON.
- Si el receptor rechaza las nuevas claves, no considere el envío compatible
  hasta que Radis confirme su contrato.

## Pruebas previas a producción

- Borrador sin descuento/recargo: porcentajes 0/0.
- Descuento Loyalty 10%, pago 5%: porcentajes 10/5, sin cambio de `price_unit`.
- Dos productos con diferentes descuentos y bodegas autorizadas.
- Envío manual y automático, sin duplicados ni cambio no autorizado de estado.
- Cotización con recompensas Loyalty como líneas especiales: revisar contrato
  de Radis, que todavía puede requerir tratamiento diferenciado.

### Contrato de cabecera ERP

La clave nueva de la API se llama **`order_payment_code`** y contiene únicamente
el código ERP del maestro, no la etiqueta visible ni el porcentaje de recargo.
Debe confirmarse con el equipo receptor de Radis que acepte esa clave exacta.
No se cambia ninguna otra clave de cabecera ni de producto.
