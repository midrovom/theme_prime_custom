# Separación de funciones Logística Transcash — v2.21

## Alcance

Complemento `transcash_guias_api` sobre `logistica_transcash` v5.32. No se modifica el módulo principal ni el flujo de importación `getguiaslogistica`.

## Responsabilidades

| Rol | Actividades autorizadas | Actividades NO autorizadas |
| --- | --- | --- |
| Responsable de bodega | Supervisar carga, confirmar despacho conforme a las reglas existentes, consultar incidencias y evidencias | Negociar, consultar tarifas, aprobar fletes, enviarlos al proveedor, gestionar pagos |
| Operador de logística | Crear rutas, agregar guías compatibles, agrupar rutas en embarque, documentar carga, liberar el viaje y resolver objeciones operativas | Consultar precios y tarifarios, negociar valor, aprobar/publicar fletes, validar facturas, realizar pagos |
| Jefe de logística | Funciones operativas + configurar tarifarios, revisar expedientes, fijar valor negociado, aprobar y publicar el flete tras cierre operativo | Registrar el pago bancario desde el flujo de Contabilidad |
| Chofer (Portal) | Viajes y guías propios, aceptación, evidencias y cierre de entregas | Acceso a precios internos, aprobaciones, viajes ajenos |
| Cliente (Portal) | Sus guías, evidencias y recepción/objeción conforme a los permisos existentes | Tarifas y fletes, guías de otros clientes |
| Proveedor de transporte (Portal) | Viajes de su empresa, fletes aprobados y liquidación/factura propios | Negociar/autorizar el importe desde portal, ver datos de otros proveedores |
| Contabilidad | Liquidaciones, facturas, comprobantes y pagos | Autorizar el flete en nombre de logística, editar rutas/carga |

## Cambio específico v2.21

- Cuando **solo el operador** arma un embarque, se crea con `valor_acordado=0` y `tarifa_referencial_total=0`, sin buscar la tarifa ni fijarla automáticamente. Puede seguir agregando rutas y registrando evidencias sin precios.
- Si **el jefe** utiliza el asistente heredado, se preserva su comportamiento actual de referencia; el jefe puede revisar y cambiar el importe negociado.
- Un embarque nuevo del operador sigue apareciendo en el circuito operativo, pero **no puede aprobarse** hasta que el jefe registre un importe positivo y se complete la entrega.
- Se retira el permiso de lectura al tarifario del grupo operador. En los modelos también se restringen a roles financieros los campos de importe y tarifa, para evitar acceso por RPC normal; y se ocultan en PWA/backend.
- La aprobación ya estaba protegida en `transcash.embarque._check_logistics_finance`, y las rutas `/transcash/finanzas/*` validan el grupo jefe; esos controles existentes se mantienen.
- El historial de chatter de embarque se reserva a jefe/contabilidad porque contiene mensajes históricos con importes. El operador sigue consultando guías, rutas, evidencias y seguimiento operativo.
- **No se recalculan ni modifican importes históricos** o embarques existentes, ni se toca la asignación de guías o las liquidaciones.

## Instalación

1. Respaldar PostgreSQL y carpeta `transcash_guias_api`.
2. Copiar el contenido del ZIP v2.21, reemplazando la carpeta del complemento.
3. Reiniciar Odoo y actualizar **solo** `transcash_guias_api`.
4. Limpiar caché de navegador/PWA y ejecutar la matriz de pruebas siguiente.

## Validación funcional en Odoo

1. Iniciar sesión **solo con operador** (sin grupo jefe ni contabilidad): crear ruta y embarque. La PWA y el backend no deben mostrar precio ni tarifario; el nuevo embarque debe tener `valor_acordado=0`, y debe permitir documentar la carga.
2. Desde operador intentar el endpoint de aprobación `/transcash/finanzas/embarques/<id>/aprobar` y el método RPC `action_approve_transport`: ambos deben bloquearse.
3. Iniciar sesión con **jefe**: abrir el embarque, registrar valor positivo con motivo en `/transcash/finanzas`, completar el circuito operativo y aprobarlo. El proveedor podrá visualizarlo solamente cuando esté aprobado.
4. Iniciar sesión con **contabilidad**: registrar/revisar factura/pago, sin permiso de aprobar flete.
5. Iniciar con **chofer, proveedor y cliente** de portal: comprobar aislamiento de sus propios viajes y que no puedan acceder al tarifario ni a la pantalla operativa interna.
6. Abrir embarques y liquidaciones históricos: no deben cambiar sus estados, importes o relaciones.
7. Comprobar que una ruta pueda agregarse a un embarque preexistente **sin cambiar su valor económico**.

## Notas

Las asignaciones reales de grupos pueden variar por usuario. Si un operador también tiene explícitamente el grupo **Jefe de Logística**, Odoo lo tratará como jefe. Debe retirársele ese grupo desde administración de usuarios. La pertenencia del jefe al grupo operador por herencia es intencionada para habilitar la gestión logística.

La ocultación de precios en las vistas no reemplaza las comprobaciones de permisos del ORM ni las de los controladores; por eso se han aplicado los tres niveles.
