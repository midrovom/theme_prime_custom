# Versión 18.0.1.8.8 · Persistencia de filtros en el tablero

## Motivo del cambio

El selector **Vista** y el botón **Guardar en Favoritos** conservaban la definición de filtros
(`ir.filters`), pero al volver al **Tablero** la acción cliente OWL ejecutaba siempre
`get_default_filters()` y cargaba datos sin recuperar la última selección aplicada.

## Implementación

- Se agrega el modelo técnico `dispatch.dashboard.state` (solo accesible desde el servicio
  autorizado `dispatch.dashboard`), que guarda la última consulta aplicada por usuario y
  conjunto de compañías activas.
- Se mantienen la fuente, corte, fechas, ciudad, modalidad, selección múltiple de bodegas,
  alcance y agrupación del plan, tablero elegido y favorito activo.
- Al entrar al tablero se consultan primero las fechas por defecto y el estado anterior;
  si existe un estado guardado, se restaura antes de cargar los indicadores.
- Cuando el usuario aplica filtros, el tablero recuerda solo la consulta cargada correctamente.
  Los cambios aún sin aplicar no sustituyen la última consulta.
- Al seleccionar un favorito o guardar uno nuevo se conserva también la selección activa.
  Si se quita la selección del favorito, ese cambio también se recuerda.
- La apertura explícita de un tablero desde **Mis tableros** mantiene prioridad sobre el
  tablero recordado; los demás filtros se conservan.
- El guardado desde el navegador se ejecuta secuencialmente para que respuestas tardías
  no reemplacen la última selección.
- El estado de otro usuario o de otro conjunto de compañías no altera la selección actual.

**Alcance:** el selector personalizado **Vista** y los filtros del **Tablero**.
No modifica el comportamiento general de los filtros nativos de otras acciones de Odoo.
En dichas vistas Odoo proporciona la opción «Usar por defecto» al guardar favoritos.

## Instalación

1. Copiar la carpeta `transcash_dispatch_analysis` de este ZIP sobre la carpeta del módulo.
2. Actualizar la lista de aplicaciones y actualizar el módulo a `18.0.1.8.8` (con Odoo o `-u transcash_dispatch_analysis`).
3. Reiniciar el servicio de Odoo cuando proceda y forzar recarga del navegador para renovar los assets JS/XML.
4. En el tablero, aplicar filtros; navegar a otra opción del módulo y volver al Tablero.
   Debe mostrarse la misma consulta y, si estaba seleccionado, el mismo favorito.

## Pruebas

- Pruebas unitarias standalone: 274 en total, incluyendo 5 casos nuevos de persistencia.
- Comprobaciones sintácticas de Python, JS y XML.
- Una prueba de integración de Odoo incluida para comprobar la persistencia usando ORM real.
  La integración con un servidor Odoo requiere validación después de instalar/actualizar.
