# TRANSCASH V5.22 — Evidencias y cierre operativo por hoja de ruta

Actualización incremental para Odoo 18, basada exclusivamente en el módulo **V5.21**. **No desinstalar:** se mantienen datos, usuarios, guías, archivos, firmas, liquidaciones y filestore.

## 1. Flujo operativo aprobado

**Embarque → Hoja de ruta → Guías → Evidencias de carga / descarga / firmas.**

1. Logística crea cada hoja de ruta con las guías correspondientes y arma un solo embarque. Registra una o varias evidencias de carga por hoja de ruta. El valor del flete sigue siendo **único por embarque**, nunca por ruta.
2. El chofer revisa las evidencias de carga del viaje, acepta u objeta el embarque y comienza el traslado.
3. En destino, el chofer registra **la entrega de cada guía**, con evidencia de descarga, nombre de quien recibe y firma. Las evidencias están asociadas a su guía, y para supervisión se **agrupan automáticamente dentro de la hoja de ruta** correspondiente. Esto evita atribuir una firma a otro destinatario cuando varias guías comparten ruta.
4. Cuando la última guía de una hoja de ruta se cierra operativamente, esa ruta pasa a **Ruta entregada**; se guarda el momento de cierre y un evento en su bitácora. El estado de planificación (planificada/cargada/aceptada) permanece intacto.
5. Cuando **todas las rutas** y todas las guías del viaje se cerraron por el chofer, el embarque pasa automáticamente a **Entregas finalizadas por chofer**. No requiere conformidad del cliente para liberar el próximo viaje. Guías históricas sin ruta también deben cerrarse si están dentro del mismo embarque.
6. El cliente revisa después y registra sus novedades o roturas, sin alterar el cierre operativo; Contabilidad y Logística siguen gestionando las incidencias y liquidaciones según sus permisos.

## 2. Nueva consulta de evidencias

Al final de cada embarque, tanto en PWA como en el backoffice de Odoo, las evidencias se presentan así:

- **Ruta 001 — Quito:** progreso (por ejemplo, 2 de 3 guías entregadas); **Carga** (fotos/videos de Logística); **Descarga / entrega** (fotos/videos agrupados e identificados por guía); **Firmas** (identificadas por guía y nombre del receptor).
- **Ruta 002 — Cuenca:** los mismos tres apartados, sin mezclar archivos de la primera ruta.
- **Guías sin hoja de ruta:** sección de compatibilidad para embarques anteriores a la planificación por rutas.

Puedes saltar a una hoja de ruta desde el resumen del embarque y desde los enlaces de acceso rápido. Fotografías, videos y firmas siguen abriéndose directamente en el visor privado sin obligar a descargarlos.

En la ficha individual de una guía se presenta su expediente. **El destinatario Portal ve únicamente la evidencia y firma de su propia guía**; no obtiene los videos generales de carga de la ruta, los otros destinatarios, objeciones del chofer ni valores económicos. Los proveedores transportistas, operadores y áreas internas conservan sus permisos de lectura previos.

## 3. Campos de seguimiento nuevos

En `transcash.hoja.ruta`:

| Campo | Uso |
|---|---|
| `estado_entrega` (calculado) | Sin guías / Pendiente de entrega / Entregas en curso / Ruta entregada |
| `guias_cerradas_chofer` (calculado) | Cuenta de guías cerradas operativamente en esa hoja |
| `fecha_cierre_operativo` (guardado) | Fecha del primer cierre completo de esa ruta |

El embarque conserva su estado y fecha de cierre general. No se crean nuevas relaciones de archivos: la bitácora de carga ya depende de la hoja, mientras las descargas y firmas dependen de las guías que ella contiene. **No se pierde ni se duplica ningún archivo existente.**

## 4. Instalación sobre V5.21

1. Respaldar PostgreSQL, filestore y la carpeta actual `logistica_transcash`.
2. Extraer el ZIP y reemplazar la **misma carpeta** del addon.
3. Reiniciar el servicio de Odoo 18 y actualizar la aplicación Transcash (desde Aplicaciones o por `-u logistica_transcash` con tu configuración habitual). No desinstalar.
4. Entrar a la PWA con conexión, recargar, y comprobar que el navegador cargó los recursos V5.22. El service worker tiene nueva versión; no borrar datos offline pendientes sin sincronizarlos.
5. Revisar una ficha de embarque desde Odoo y desde teléfono, y verificar los saltos por ruta.

## 5. Pruebas funcionales recomendadas en tu VPS

- **Caso A:** embarque con dos rutas: ruta A con dos guías, ruta B con una. Cerrar solo la primera guía de A: estado **En entrega**, viaje todavía **En ruta**. Cerrar la segunda guía de A: **Ruta A entregada**, viaje sigue **En ruta**. Cerrar guía de B: **Ruta B entregada** y viaje **Entregado** automáticamente.
- **Caso B:** cliente de la primera guía todavía sin aceptar y una rotura abierta. El chofer ya puede finalizar todas las entregas y crear otro viaje; se mantienen pendientes la aceptación/reclamación y la revisión financiera.
- **Caso C:** cada ruta tiene fotos de carga y descarga y firma; comprobar que ninguna aparece debajo de una ruta distinta. Fotos y videos se reproducen dentro del visor, sin descarga forzada.
- **Caso D:** la ruta contiene dos guías de destinatarios diferentes. En la cuenta Portal de cada cliente solo se visualiza su guía y su firma; probar también un enlace copiado de la otra guía: debe denegarse.
- **Caso E:** embarque antiguo sin hojas de ruta: las evidencias quedan en el apartado histórico y el cierre por última guía continúa funcionando.
- **Caso F:** comprobar la vista de Odoo para jefatura, operador, proveedor y Contabilidad; los choferes y clientes no deben ver montos ni objeciones internas ajenas.

## 6. Validaciones y límites

La entrega se empaqueta con validación estática Python, XML, JavaScript, integridad ZIP y pruebas de regresión añadidas en `tests/test_route_evidence_v522.py`. También se ejecuta un ejemplo aislado de agrupamiento para comprobar que no mezcla rutas ni evidencias del cliente.

**No se han ejecutado las pruebas automatizadas dentro de Odoo 18 real ni se ha probado el VPS.** Antes de producción, ejecutar la batería de tests en una base de staging y los casos descritos arriba.
