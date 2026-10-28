# v2.39: quitar una hoja de ruta de un viaje sin aceptación

## Dónde aparece
- PWA: Operación logística > Viajes > detalle de viaje; botón **Quitar esta ruta del viaje** dentro de cada hoja de ruta.
- Backend: formulario del embarque > botón **Quitar hoja de ruta**; asistente para escoger la ruta del mismo viaje.

## Comportamiento
- Un viaje en `preparacion` admite retirar una hoja de ruta mientras no haya aceptación, salida, entrega o liquidación.
- Si está `embarcado` pero el chofer todavía no lo aceptó, primero se devuelve mediante `action_reopen_packing()` a `preparacion`; entonces se retira la ruta.
- Las guías **conservan `hoja_ruta_id`** y el estado `registrada`; solamente se limpia el vínculo `embarque_id` de la ruta y sus guías.
- Las evidencias quedan en su ruta; no se borra ninguna evidencia ni se crea otro viaje.
- Las demás rutas y guías continúan en el mismo embarque.
- Si es la última ruta, el viaje queda vacío en preparación; se le pueden agregar otras rutas o eliminar el viaje mediante la acción preexistente.
- La bitácora interna del viaje registra ruta, responsable y cantidad de guías desvinculadas.

## Protecciones
- Operador interno de rutas o jefe de Logística; compañía autorizada.
- La decisión se comprueba en el modelo ORM, también ante llamadas RPC, no solo en botones.
- Bloqueado si el chofer ya aceptó, hubo salida, entregas, o movimientos de liquidación/ aprobación.
- Si el flete se negoció o calculó, primero debe revisarlo el jefe para no mantener un precio de un viaje cuya composición cambió.
- Los bloqueos de fila previenen cambios concurrentes con acciones del chofer o de otros operadores.
- Incluye comprobación de integridad entre guías y rutas.

## Instalación
- Respaldar base y carpeta `transcash_guias_api`.
- Reemplazar solo el complemento; reiniciar Odoo; actualizar addon; recargar PWA.
- Probar con viaje en preparación, otro embarcado sin aceptación y otro ya aceptado.
- Odoo en servidor real sigue pendiente de prueba funcional.
