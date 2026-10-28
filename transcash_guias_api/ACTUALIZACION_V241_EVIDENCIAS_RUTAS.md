# Transcash Guías API 18.0.2.41.0 — envío al chofer y evidencias

## Causa comprobada en el código base de Logística v5.32

`transcash.embarque.action_reopen_packing()` devuelve indiscriminadamente
las rutas del viaje a estado `planificada`, aunque conserven las fotos/video
registrados. `action_ready_for_driver()` exige `ruta.state == 'cargada'` y
`ruta._has_carga_evidence()`, por lo que rechaza un viaje con evidencia válida.

## Cambios

- Tras **Volver a preparación**, las rutas con evidencia válida mantienen su
  estado de carga documentada (`cargada`). Las rutas sin evidencia válida
  permanecen `planificada`.
- Para viajes que ya quedaron así por una versión anterior, al pulsar
  **Enviar al chofer** se comprueban primero todas las rutas y se corrige
  automáticamente el estado de las que sí tienen evidencia válida. No se
  crea ni elimina ninguna foto.
- Si la ruta se reabrió y se modificó la carga, las fotos anteriores siguen
  siendo históricas: se solicita una evidencia nueva y se indica el número
  de ruta que la necesita, en lugar del error genérico.
- La pantalla PWA distingue evidencia *lista* de evidencia *histórica* y
  cuenta las rutas con fotos válidas independientemente del estado dejado
  por versiones anteriores.
- Cuando se reabre una ruta para editarla, se guarda el ID de la última
  evidencia existente; así una foto nueva tomada en el mismo segundo no
  se descarta por la precisión de fecha de Odoo.
- Se preserva el bloqueo por objeciones del chofer, la aceptación, salida,
  las guías, las finanzas, los perfiles y la modalidad de transporte del cliente.

## Pruebas sugeridas en copia de producción

1. Viaje con dos rutas, cada una con una foto. Enviar, volver a preparación
   antes de aceptación y reenviar: debe funcionar sin repetir las fotos.
2. Viaje existente en preparación con ruta `planificada` pero foto vigente:
   debe auto-corregir la ruta al enviar al chofer.
3. Reabrir una ruta libre para cambiar la carga y reinsertarla en un viaje:
   la foto anterior no autoriza enviar; cargar foto nueva y reenviar.
4. Dejar una ruta sin evidencia: debe mostrar cuál está pendiente.
5. Mantener una objeción del chofer sin resolver: el envío debe continuar
   bloqueado aunque todas las rutas tengan fotos.
6. Probar transporte del cliente: respetar la misma validación de evidencia
   sin crear aceptación ficticia del chofer.

**No se modificó `logistica_transcash`.** La prueba de servidor Odoo real sigue
pendiente. No ejecutar reparaciones manuales de SQL para este cambio.
