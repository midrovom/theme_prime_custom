# Incentivos a clientes y cobro a proveedores — Odoo 18

Aplicación interna para crear y completar **manualmente** requerimientos/boletines de incentivos, rebates y acuerdos de pago.

## Alcance manual de esta versión

- El usuario crea el requerimiento y llena manualmente el cliente beneficiario, proveedor, vendedor, tipo de solicitud, términos de pago, idioma, descripción y líneas de producto/programa.
- No se importan automáticamente datos de ventas, CRM, facturas de proveedor ni movimientos contables.
- Al guardar las líneas, el módulo calcula únicamente las fórmulas solicitadas: `Total de línea = Unit × Target Qty`, suma global de `Target Qty` y suma global de `Total`.
- Las etapas cambian solo cuando el usuario pulsa el botón correspondiente.
- Las transferencias, notas de crédito, facturas de cobro y cruces contables **no se crean ni se contabilizan automáticamente** por este módulo.
- Los usuarios contables registran manualmente en la pestaña de liquidación el método, monto, fecha, referencia, evidencia y, si corresponde, el vínculo a un documento contable que ya exista.
- Para un cruce real, el equipo contable debe hacer y conciliar el movimiento desde Contabilidad de Odoo. El módulo guarda el detalle y permite controlar el saldo manualmente; no efectúa la conciliación por sí solo.

## Funciones incluidas

- Tipos de requerimiento configurables; se instalan **Rebate** y **Acuerdo de pago** como opciones iniciales.
- Encabezado con cliente beneficiario, proveedor por cobrar, vendedor, términos de pago nativos (`account.payment.term`) e idioma de impresión.
- Líneas de producto con No. producto, tipo de programa, fechas Desde/Hasta, Unit, Target Qty y Total calculado.
- Suma de Target Qty y Total general al pie de las líneas, más descripción.
- Flujo manual: Borrador → Enviado → Aprobado → En ejecución → Pagado al beneficiario → Pendiente de cobro al proveedor → Cerrado; las solicitudes pueden rechazarse durante la aprobación.
- Selección de **Transferencia** o **Cruce contable** tanto para el pago al beneficiario como para recuperar el valor del proveedor.
- Detalle manual por vendedor y transacción: pago/cruce, dirección (beneficiario/proveedor), importe, fecha, referencia, vínculo opcional a un pago contable existente y evidencia.
- Evidencias y documentos adjuntos, historial de cambios y reporte PDF en el idioma seleccionado.
- Filtros por requerimiento propio, vendedor, cliente, proveedor, estado, tipo y términos de pago; agrupaciones para consulta.
- Grupos de seguridad para solicitante, aprobador, contabilidad y administrador.

## Instalación

1. Copie la carpeta `customer_incentive_management` en un directorio de addons de Odoo 18.
2. Reinicie Odoo.
3. Active el modo desarrollador y actualice la lista de aplicaciones.
4. Busque **Customer Incentives & Supplier Collections** e instale la aplicación.
5. En Ajustes → Usuarios, asigne los grupos de Incentivos según las funciones de cada usuario.
6. Active los idiomas de Odoo que se utilizarán y revise los tipos de requerimiento configurables.

## Uso recomendado

1. Cree el requerimiento y complete manualmente todos los campos.
2. Agregue una o varias líneas. El subtotal de cada línea se calcula como `Unit × Target Qty`; al pie se suman Target Qty y Total.
3. Adjunte los documentos necesarios y pulse **Enviar a aprobación**.
4. Un aprobador pulsa **Aprobar** o **Rechazar**. Después de aprobar, pulsa **Iniciar ejecución** cuando corresponda.
5. En **Detalle de pagos por vendedor**, Contabilidad agrega manualmente uno o varios registros de pago/cruce al beneficiario. Incluya la evidencia y el importe requerido; luego pulsa **Confirmar liquidación al beneficiario**.
6. Ingrese manualmente la referencia, fecha e importe del documento de cobro al proveedor; seleccione los términos de pago y pulse **Registrar documento de cobro**. El término queda guardado como información del requerimiento; el documento contable y sus vencimientos se crean por separado, de forma manual, desde Contabilidad.
7. Contabilidad agrega detalles de cobro por transferencia o cruce, con referencia y evidencia. Pulse el botón correspondiente para verificar el saldo registrado. Se permiten cobros parciales; el estado pasa a Cerrado cuando el total registrado cubre el importe por cobrar.

## Cómo funciona el cruce de cuentas

Ejemplo: la empresa tiene una factura de compra por pagar al proveedor de $60 y, a la vez, el proveedor debe $100 a la empresa por el incentivo. Un cruce de $60 compensa ambos saldos y deja $40 por cobrar al proveedor. No representa una salida de dinero del banco.

En esta versión, el requerimiento registra manualmente que se hizo el cruce, el importe, la fecha, la referencia y la evidencia. El cruce contable real debe ejecutarse en Contabilidad de Odoo conciliando las partidas correctas del mismo contacto y luego anotarse en el requerimiento. No marque un cruce como realizado antes de verificar la conciliación contable.

## Términos de pago

La aplicación permite seleccionar términos nativos de Odoo, por ejemplo a 6 o 12 cuotas, desde el inicio. Deben configurarse previamente en Contabilidad → Configuración → Términos de pago. Como esta versión no crea facturas automáticamente, el usuario debe seleccionar manualmente el término también en la factura contable que genere desde Odoo.

## Notas importantes

- Los importes del boletín siguen la fórmula indicada. Los importes fiscales de una factura o nota de crédito pueden variar por impuestos, por lo que Contabilidad debe validar el tratamiento tributario aplicable en Ecuador.
- El total de cobro, cobros registrados y saldo pendiente en este módulo se controlan a partir de los importes que ingresan los usuarios; el saldo contable real debe contrastarse con las facturas y conciliaciones en Odoo Accounting.
- La aplicación está diseñada para usuarios internos; no crea un portal de autoservicio para proveedores externos.
- No se pudo ejecutar una instalación funcional contra una instancia real de Odoo 18 en este entorno. Antes de utilizarla en producción, pruébela en una base de desarrollo con los permisos y flujos de su empresa.
