# TRANSCASH V5.16 — El flete corresponde al EMBARQUE, no a cada ruta

**Cambio operativo:** una hoja de ruta solo organiza guías, destino, transportista y video. **No genera un valor de flete.** Se factura/liquida **un único valor por embarque**, independientemente del número de rutas o guías incluidas.

## Flujo

1. **Logística → Tarifario por viaje y destino:** registre un precio por tipo de transporte y destino de referencia. Ejemplo: camión → Quito: USD 250 por viaje, no USD 250 por ruta.
2. **Logística → Hojas de ruta:** cree y confirme rutas con sus guías. Ya no se necesita una tarifa para confirmar una ruta.
3. **Logística → Armar embarque desde rutas:** seleccione rutas del mismo chofer, transportista, placa, compañía y tipo de vehículo. El sistema determina el importe una sola vez utilizando el tarifario del destino de cobro.
4. Si las rutas tienen destinos diferentes, **elija explícitamente el destino de cobro** entre los destinos de esas rutas. No se supone que el más lejano ni el último sea el cobrado. Si hay un único destino, se propone automáticamente. Si no existe tarifa activa, configure una antes de registrar el embarque.
5. Al registrar el embarque quedan guardados **destino del tarifario, tarifa aplicada, valor referencial por viaje y valor acordado**. El jefe de Logística conserva la acción «Negociar valor del viaje» para modificar el acuerdo antes de la aprobación.
6. **Agregar rutas al mismo embarque:** no cambia el valor referencial ni el valor acordado. Si corresponde renegociar por nuevos destinos, el jefe de Logística lo hará expresamente.
7. Al liquidar, el valor utilizado es **`embarque.valor_acordado` UNA sola vez**, no un subtotal por cada hoja de ruta. El proceso documental de proveedor y Contabilidad permanece sin cambios.

## Ejemplo

| Elemento | Destino | Valor del transporte |
| --- | --- | ---: |
| Hoja R-001 (guías 1, 2) | Quito | — |
| Hoja R-002 (guías 3, 4) | Sangolquí | — |
| Embarque E-001 con dos rutas; destino de cobro Quito; tipo camión | Quito | **$250 (una vez)** |
| Nueva ruta R-003 agregada a E-001 | Quito | **$0 adicional** |
| Valor final acordado por Logística, si renegocia | Viaje E-001 | **Monto que indique el jefe** |

*Importes únicamente ilustrativos.*

## Importante: embarques históricos V5.9–V5.15

- Los valores previos de embarques, liquidaciones, facturas y pagos **NO se reescriben automáticamente**.
- Se conservan los campos históricos `hoja_ruta.tarifa_id` y `hoja_ruta.tarifa_referencial` para proteger los datos registrados; ya no se llenan ni se presentan para rutas nuevas. La columna histórica `embarque.tarifa_referencial_total` se mantiene almacenada pero deja de calcularse como suma.
- Un jefe de Logística puede abrir un embarque **pendiente de aprobación y sin liquidación** y pulsar **«Revisar tarifa ÚNICA del embarque»**. Selecciona destino de cobro y revisa el precio del tarifario. Puede actualizar el *referencial* sin tocar el *negociado*, o marcar **«Actualizar también el valor negociado»** si desea corregir ambos. El cambio queda en el historial de mensajes.
- **No se permite** ejecutar esa corrección sobre embarques aprobados o liquidados: cualquier conciliación posterior requiere un procedimiento administrativo externo.

## Instalación / actualización

1. Realice respaldo **de base de datos PostgreSQL, filestore y carpeta `logistica_transcash`**.
2. Extraiga el ZIP y reemplace **la misma carpeta** del addon `logistica_transcash` V5.15. NO desinstale el módulo.
3. Reinicie el servicio Odoo 18.
4. Actualice «Transcash - Seguimiento de Guías» en Aplicaciones o mediante la opción `-u logistica_transcash` en ambiente de pruebas.
5. Recargue el navegador (Ctrl+Shift+R).

## Pruebas funcionales obligatorias en Odoo 18 (staging)

- Confirmar hoja de ruta de un destino sin tarifa: debe permitirla.
- Intentar armar embarque sin tarifa aplicable: debe informar qué tarifa falta.
- Crear embarque de 2 rutas con igual destino y precio $250: valor del embarque $250, no $500.
- Crear embarque de rutas con distintos destinos: exige escoger el destino de cobro y muestra el precio del vehículo/destino escogido; no suma tarifas.
- Agregar otra ruta antes de liberar: valor no cambia.
- Cambiar el precio en el tarifario después de crear el embarque: valor histórico no cambia.
- Negociar el valor por el jefe y aprobar: liquidación del proveedor debe contener un importe por cada **embarque**, no por ruta.
- Verificar que Contabilidad y proveedor vean el valor aprobado y que registros de pago anterior conserven sus montos.
- Revisar un embarque histórico no aprobado con «Revisar tarifa ÚNICA»: sin casilla debe conservar el monto acordado; con casilla aplica el nuevo precio negociado.

## Alcance de la verificación del ZIP

La validación fuera de Odoo puede verificar sintaxis de Python y JavaScript, estructura XML, contenidos de manifiesto y ZIP. Las pruebas en `tests/test_rutas_v59.py` y en el resto de la carpeta `tests/` **requieren Odoo 18 con una base de pruebas**: no se han ejecutado en la instalación del usuario.
