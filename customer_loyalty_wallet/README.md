# Billetera de Recompensas para Clientes — Odoo 18 Community

Módulo independiente de Contabilidad para controlar dólares acumulados por clientes y permitir su consulta desde el portal móvil de Odoo.

## Alcance incluido

- Una billetera por cliente y compañía.
- Abonos por pago puntual, bonos de campaña o ajustes.
- Consumos por uso del saldo.
- Validación para impedir saldo negativo.
- Estados activa, bloqueada y cerrada.
- Confirmación de movimientos y trazabilidad del usuario que confirma.
- Movimientos confirmados inmutables.
- Reversos mediante un movimiento contrario, sin borrar el historial.
- Acceso móvil del cliente en `/my/wallet`.
- Saldo, total acumulado, total utilizado e historial filtrable.
- Separación por compañías y permisos para operador/administrador.
- Sin dependencia de `account`, facturas, pagos ni conciliaciones.

## Instalación

1. Copiar la carpeta `customer_loyalty_wallet` al directorio de addons personalizados.
2. Reiniciar el servicio de Odoo.
3. Activar modo desarrollador.
4. Ir a Aplicaciones y pulsar **Actualizar lista de aplicaciones**.
5. Buscar **Billetera de Recompensas para Clientes** e instalar.
6. Asignar a los usuarios internos el grupo **Operador de billetera** o **Administrador de billetera**.

## Uso interno

1. Abrir Contactos y seleccionar un cliente.
2. Pulsar el botón **Billetera**; si no existe se crea automáticamente.
3. Usar **Registrar abono** para acumular dólares.
4. Usar **Registrar consumo** para descontar saldo.
5. Confirmar el movimiento. Una vez confirmado no se edita ni elimina.
6. Los errores se corrigen con **Reversar**, disponible para administradores.

## Acceso del cliente

El cliente debe tener un usuario de portal vinculado al mismo contacto. Desde su teléfono ingresa al portal de Odoo y abre **Mi billetera**. Solo puede consultar; no puede crear ni modificar movimientos.

## Recomendación operativa

Utilizar siempre el campo **Referencia externa** para guardar el número de cuota, comprobante, autorización o ticket que originó el abono/consumo. Esto permite auditar el programa sin conectarlo a Contabilidad.
