# Corrección v2.40 — Quitar ruta desde PWA con operador logístico/bodega

## Problema
La acción `action_tc_detach_route()` consultaba `embarque.liquidacion_linea_id` sin sudo, provocando `AccessError` del modelo `transcash.pago.liquidacion.linea` en usuarios de operaciones. El mismo patrón existía en los bloqueos para `action_reopen_packing()` y eliminación del viaje.

## Cambios
* `route_detach_v239.py`: tras verificar el rol operativo y compañía, leer la relación financiera y los importes mediante un `fiscal = self.sudo()` local. No se escriben datos financieros ni se devuelven al usuario.
* `route_reopen_edit_v238.py`: verificar liquidaciones existentes vía `trip.sudo().liquidacion_linea_id`, sin elevar la acción completa.
* `route_trip_editing_v235.py`: igual corrección para el bloqueo de eliminación de viajes no aceptados.
* Mismos controles de aceptación, despacho, entrega, estado financiero y valores negociados. Nunca se permite quitar una ruta de un viaje aceptado ni liquidado.

## Instalación
Reemplazar únicamente el addon `transcash_guias_api`, reiniciar Odoo 18 y actualizar el addon. No cambiar ACL, ni asignar grupos financieros al operador, ni modificar `logistica_transcash`.

## Prueba funcional pendiente en Odoo real
Entrar con perfil operador rutas/bodega **sin** grupo Contabilidad ni Jefe. En un embarque en preparación y sin flete ni liquidación, retirar una ruta. Repetir desde un viaje `embarcado` aún no aceptado (debe pasar a preparación). Verificar que la ruta y sus guías conservan sus vínculos y evidencias salvo el `embarque_id`. Comprobar que un viaje aceptado, con flete o con liquidación sigue bloqueado. Probar también regresar a preparación y eliminar un viaje sin aceptar. 
