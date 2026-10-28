# v2.37 — Agregar rutas existentes a un viaje en preparación

La sección «Agregar ruta existente al viaje» muestra las hojas de ruta libres,
planificadas o cargadas, del mismo transportista, chofer, tipo de vehículo y
placa. Cada ruta tiene un botón «Agregar ruta» que hace POST con CSRF al
embarque abierto. El formulario no crea embarques nuevos: reutiliza el asistente
`transcash.armar.embarque.wizard` del módulo principal, con `embarque_id`.

Se aplican los mismos bloqueos del asistente: solo viajes en preparación,
rutas con guías, máximo 100 guías en el embarque, verificación de compañía y
sin cambios al importe del viaje. En la pantalla se omiten rutas que excederían
el límite. Una hoja de ruta en borrador debe confirmarse para poder agregarse.

El antiguo enlace «Agregar otras rutas» ya no abre el asistente general de
armar viaje, sino que conduce al listado del mismo embarque.

Pruebas funcionales recomendadas en Odoo: ruta planificada sin viaje visible,
ruta de otro chofer invisible, ruta de otra placa invisible, ruta ya vinculada
invisible, añadir ruta preserva ID del viaje y su valor, recarga y verifica
que no aparece duplicada, límite de 100 guías y permisos de otro usuario.
