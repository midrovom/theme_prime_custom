# Caja Chica - Recibos y Saldos (Odoo 18 Community)

Módulo adicional para `petty_cash_control` versión 18.0.3.1.0 o posterior.

## Funciones

- Imprime un recibido individual por gasto con el logo de la compañía y espacios de firma.
- Permite enviar y aprobar gastos sin adjuntar un archivo de comprobante.
- Conserva proveedor, beneficiario y departamento como datos obligatorios.
- Muestra el fondo máximo de la caja y el saldo resultante de restar los gastos
  de esa liquidación, tanto en pantalla como en PDF.
- Incluye la descripción como "Nota del gasto" en el reporte general.
- Impide tener más de una liquidación pendiente para la misma caja. Una
  liquidación rechazada debe anularse o volver a borrador para terminar su flujo.

## Instalación

1. Mantenga instalado y actualizado `petty_cash_control`.
2. Copie la carpeta `petty_cash_receipt_extension` en la ruta de addons.
3. Reinicie Odoo y actualice la lista de aplicaciones.
4. Instale **Caja Chica - Recibos y Saldos**.

El logo se obtiene de **Ajustes > Compañías > Logo**.
