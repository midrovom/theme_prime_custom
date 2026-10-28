# v2.38 — Editar rutas sin embarque y retornar viajes a preparación

**Solo se actualiza `transcash_guias_api`; `logistica_transcash` v5.32 no se altera.**

## Hoja de ruta sin viaje

- `borrador`: se abre **Modificar datos y guías** directamente desde la PWA o el backend.
- `planificada` / `cargada`: **Reabrir para modificar** devuelve la hoja a borrador, libera los vínculos de las guías, mantiene su selección y abre el editor. Se debe confirmar de nuevo la hoja de ruta.
- La pantalla permite cambiar destino ERP, chofer, transportista, placa, vehículo u origen. Un cambio de destino limpia las guías previamente seleccionadas, que deben revisarse otra vez.
- Ruta vinculada a cualquier viaje, aceptada, con salidas o entregas: no se permite editar por esta función.
- Evidencias anteriores se conservan como historial inmutable. Si hubo evidencia de carga anterior a la reapertura, **no cumple el requisito de evidencia de un despacho nuevo**; registrar al menos una evidencia de carga posterior a la revisión en el embarque en preparación.
- Se mantienen todas las validaciones de rutas: máximo de 100 guías, mismo código ERP destino y reasignaciones con autorización.

## Viaje enviado al chofer

- El viaje `embarcado` sin aceptación ni salida puede volver a `preparacion` desde la PWA o el backend.
- Esto incluye viajes objetados: se conserva la bitácora de objeciones, que se debe resolver antes de volver a liberar la carga.
- No se permite si tiene aceptación, salida, cierre o relación financiera.
- Se conservan las rutas y evidencias. La lógica del módulo original decide el estado operativo al reabrir.

## Pruebas recomendadas en Odoo

1. Crear ruta, seleccionar dos guías, confirmar y reabrir, verificar la selección y reconfirmarla.
2. Editar el destino: el selector debe vaciar las guías incompatibles.
3. Eliminar un viaje no aceptado que tenía evidencia, reabrir su ruta y comprobar que la vieja foto permanece visible pero no autoriza liberar una carga nueva.
4. Enviar viaje, regresar a preparación sin aceptación y liberarlo de nuevo.
5. Registrar una objeción desde el chofer; retornar a preparación, documentar corrección, resolver y reenviar.
6. Intentar reabrir un viaje aceptado o una ruta vinculada: debe bloquearse.
7. Confirmar que no se alteran fletes, aprobaciones, liquidaciones ni acceso Portal.

Validaciones locales: sintaxis, estructura de vistas y comprobación de XPath contra el código real v5.32. Pendiente prueba funcional en instancia Odoo.
