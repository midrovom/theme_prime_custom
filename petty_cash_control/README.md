# Control de Caja Chica — Odoo 18 Community

Versión técnica: 18.0.3.1.0

Módulo independiente de Contabilidad para administrar varias cajas chicas.

## Funciones

- Varias cajas, responsable principal y responsables alternos.
- Entrega inicial y reposición de fondos con aprobación.
- Gastos categorizados, proveedor, RUC, tipo/número de comprobante y adjuntos.
- Proveedor seleccionado desde Contactos con carga automática de RUC/Cédula.
- Beneficiarios seleccionados desde Contactos y marcados como beneficiarios de caja chica.
- Departamento responsable del gasto para medición y análisis.
- Mantenimiento de departamentos desde **Caja chica > Configuración > Departamentos**.
- Validación de comprobante obligatorio, límite por categoría y saldo disponible.
- Liquidaciones con carga automática de gastos aprobados y devolución de sobrantes.
- Reporte PDF por rango de fechas, cajas y categorías.
- Filtros de reporte por beneficiario y departamento.
- PDF detallado de cada liquidación disponible en cualquier estado.
- Análisis dinámico en tablas pivote y gráficos.
- Perfiles: Usuario, Aprobador y Administrador.
- Historial de cambios y actividades mediante chatter.

## Instalación

1. Copie la carpeta `petty_cash_control` dentro de la ruta de addons de Odoo.
2. Reinicie el servicio de Odoo.
3. Active el modo desarrollador y seleccione **Aplicaciones > Actualizar lista de aplicaciones**.
4. Busque **Control de Caja Chica** e instálelo.
5. En **Ajustes > Usuarios**, asigne a cada persona su perfil de Caja chica.

## Flujo recomendado

1. El administrador crea categorías y cajas.
2. Se registra y aprueba la entrega inicial.
3. El responsable registra gastos y adjunta su comprobante.
4. El aprobador acepta o rechaza cada gasto.
5. El responsable crea una liquidación y carga los gastos aprobados pendientes.
6. El aprobador aprueba y cierra la liquidación; si existe sobrante, se registra su devolución.
7. Cuando corresponda, se crea una reposición de fondos.

Este módulo no crea asientos, pagos ni movimientos contables.
