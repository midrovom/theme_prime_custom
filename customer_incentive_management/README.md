# Incentivos a clientes y cobro a proveedores — Odoo 18

Aplicación interna para registrar manualmente requerimientos/boletines de incentivos, rebates y acuerdos de pago, con responsabilidades separadas por función. El módulo no crea facturas, pagos ni asientos contables automáticamente.

## Diseño por responsabilidades

### 1. Solicitante — `Incentive Request User`
- Crea y completa requerimientos manualmente.
- Selecciona el tipo de requerimiento, cliente beneficiario, proveedor al que se cobrará, vendedor responsable, términos de pago e idioma.
- Registra las líneas con No. producto y Program type como texto manual, fechas, Unit y Target Qty. No utiliza `product.product` ni requiere que exista un catálogo de productos de Odoo.
- Adjunta sustento y envía a aprobación.
- Puede corregir y reenviar una solicitud rechazada.
- No puede registrar la liquidación financiera ni editar los datos después de enviar, hasta que la solicitud regrese a Borrador o sea rechazada.

El solicitante y el vendedor responsable son campos distintos: la persona que llena el requerimiento no tiene que ser necesariamente el vendedor relacionado con la operación.

### 2. Aprobador — `Incentive Approver`
- Tiene una bandeja separada de solicitudes pendientes de aprobación.
- Revisa datos, líneas y documentos; aprueba o rechaza.
- No puede cambiar las líneas ni ejecutar pagos/cobros.
- Por separación de funciones, no puede aprobar ni rechazar una solicitud que él mismo creó o que tenga asignada como vendedor.

### 3. Tesorería — `Treasury - Beneficiary Payments`
- Ve la bandeja de solicitudes aprobadas/en ejecución.
- Inicia la etapa En ejecución.
- Registra cada pago o cruce realizado al beneficiario, con vendedor relacionado, método, importe, fecha, referencia y evidencia.
- Confirma el pago al beneficiario cuando el detalle cubre el importe contable del requerimiento y existe evidencia.
- No crea ni contabiliza el pago automáticamente: primero se registra en Contabilidad de Odoo y luego se referencia en este módulo.

### 4. Cuentas por Cobrar / Cobro a proveedores — `Supplier Collection - Accounts Receivable`
- Ve la bandeja de solicitudes pagadas al beneficiario y pendientes de cobro.
- Registra la referencia, fecha e importe del documento de cobro al proveedor.
- Usa los términos de pago que quedaron seleccionados desde el inicio del requerimiento.
- Registra movimientos por transferencia y/o cruce, con vendedor, importe, referencia y evidencia.
- Puede registrar cobros parciales. La solicitud pasa a Cerrado cuando los movimientos registrados completan el importe configurado para cobrar.
- La factura y la conciliación real deben crearse/ejecutarse manualmente en Contabilidad.

### 5. Contabilidad combinada y administrador

- `Incentive Accounting - Treasury and Collection`: grupo opcional para empresas donde el mismo equipo hace Tesorería y Cobros; hereda ambos permisos operativos, pero no el permiso de aprobar solicitudes. Los grupos de Tesorería y Cobros incluyen acceso de usuario contable de Odoo porque deben registrar manualmente los documentos reales en Contabilidad.
- `Incentive Manager`: administra tipos de requerimiento y puede acceder a todas las bandejas. La validación contra la autoaprobación sigue activa.

## Flujo

`Borrador → Enviado para aprobación → Aprobado → En ejecución → Pagado al beneficiario → Pendiente de cobro al proveedor → Cerrado`

El aprobador puede rechazar una solicitud mientras está pendiente de aprobación. El solicitante corrige los datos y la vuelve a enviar.

## Campos y cálculos

- No. producto: texto ingresado manualmente.
- Program type: texto ingresado manualmente (por ejemplo, Rebate, arreglo de local o publicidad).
- From Date / To Date: período de vigencia.
- Unit: importe unitario.
- Target Qty: cantidad objetivo.
- Total de línea: `Unit × Target Qty`.
- Total Target Qty: suma de todas las cantidades.
- Grand Total: suma de todos los totales de línea.
- Description: descripción libre.

Los totales de cantidad e importe se calculan automáticamente; los datos comerciales de las líneas son manuales. El módulo depende de `account` y `mail`, no del módulo de productos.

## Registro por vendedor y método

Cada detalle contiene:
- Vendedor relacionado con el movimiento.
- Operación: Pago al beneficiario o Cobro del proveedor.
- Método: Transferencia bancaria o Cruce contable.
- Importe, fecha, referencia y evidencia.
- Enlace opcional a un pago contable que ya exista en Odoo.

Esto permite que una solicitud contenga varias operaciones y que el informe identifique qué vendedor corresponde a cada pago/cruce. El método se define por movimiento, por lo que una liquidación puede documentar más de una transferencia o compensación.

## Cruces contables

Ejemplo: la empresa debe $60 al proveedor por facturas de compra y el proveedor debe $100 a la empresa por el incentivo. Al compensar $60 se liquidan ambos saldos por esa cantidad y quedan $40 por cobrar al proveedor. No sale dinero del banco por los $60 compensados.

En el módulo se guarda el registro, referencia y evidencia del cruce. La conciliación real debe ejecutarse en Contabilidad de Odoo contra las partidas abiertas correctas del mismo contacto. No se genera un asiento automático y no se debe marcar un cruce como realizado antes de comprobar la conciliación contable.

## Términos de pago

Se reutiliza el modelo nativo `account.payment.term` para seleccionar, desde el inicio, términos como 6 o 12 cuotas. Los términos deben estar configurados previamente en **Contabilidad → Configuración → Términos de pago**. La aplicación conserva esta selección para el seguimiento, pero no crea automáticamente la factura de cobro ni aplica en ella las cuotas: el usuario debe seleccionar el mismo término cuando cree la factura manualmente en Contabilidad.

## Filtros y acceso de proveedores

Las bandejas permiten filtrar por cliente, proveedor, solicitante, vendedor, tipo, estado y términos de pago, y agrupar por proveedor o vendedor. El módulo es para usuarios internos; no crea usuarios de portal ni da a proveedores externos acceso a sus solicitudes. Los filtros por proveedor están destinados al equipo interno que administra el cobro.

## Instalación y configuración

1. Descomprima `customer_incentive_management` en un directorio de addons de Odoo 18.
2. Reinicie Odoo y actualice la lista de aplicaciones.
3. Instale **Customer Incentives & Supplier Collections**.
4. En **Ajustes → Usuarios**, asigne a cada persona únicamente el grupo correspondiente a su responsabilidad.
5. En **Contabilidad → Configuración → Términos de pago**, configure los términos de 6, 12 cuotas u otros que usará el equipo solicitante.
6. Desde **Customer Incentives → Configuration → Request Types**, el administrador puede agregar nuevos tipos. Se incluyen Rebate y Acuerdo de pago como valores iniciales.
7. Active y configure los idiomas utilizados por la empresa.

### Actualizar desde la versión 18.0.1

1. Haga una copia de seguridad de la base de datos y del directorio de addons.
2. Reemplace la carpeta antigua por la nueva `customer_incentive_management` conservando el mismo nombre técnico.
3. Reinicie Odoo y actualice la lista de aplicaciones.
4. En Aplicaciones, pulse **Actualizar/Upgrade** sobre este módulo; no lo desinstale ni lo instale con otro nombre.
5. La migración `18.0.2.0.0` intenta conservar el número de producto de las líneas anteriores usando el código o nombre del producto nativo como texto y elimina las columnas obsoletas de producto y método general. Si no encuentra un producto anterior, conserva un identificador `LEGACY-*` para no perder la trazabilidad.

## Consideraciones antes de producción

- Los valores del requerimiento son manuales. Impuestos u otros ajustes de las facturas/ notas de crédito pueden hacer que el importe contable sea distinto; Contabilidad debe validar el tratamiento fiscal aplicable en Ecuador.
- Los saldos de cobro que muestra este módulo se calculan con base en importes capturados manualmente; deben contrastarse con facturas, pagos y conciliaciones reales en Odoo.
- Valide los grupos con usuarios de prueba: solicitante, aprobador, Tesorería y Cobros, incluyendo el intento de autoaprobación y la visibilidad por compañía.
- El paquete se ha revisado estáticamente, pero debe instalarse y probarse en una base de desarrollo Odoo 18 antes de producción.
