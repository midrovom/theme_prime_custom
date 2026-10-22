# Transcash Guías API v2.5 - Seleccionar todas las guías

Se añade **Seleccionar todas las guías disponibles** en el asistente de Odoo (hoja de ruta → Agregar / quitar guías) y en la WebApp interna (/transcash/operacion/rutas/<id>).

- Selecciona solo las guías **visibles y elegibles** de la búsqueda actual. Las que sean de otro destino, compañía o ya estén utilizadas siguen bloqueadas.
- Las guías que exijan reasignación de chofer o transportista requieren activar primero la autorización. Se mantienen las verificaciones originales en el momento de guardar.
- Respeta el límite de **100 guías por embarque** del módulo operativo. El asistente de backend muestra un máximo de 150 candidatas por búsqueda; si hay más guías, utilice el filtro y prepare otra selección.
- Desactivar la casilla desmarca las guías de la pantalla, **pero solo se confirma al pulsar «Guardar selección»**. Cancelar no altera la ruta.
- Las guías ya seleccionadas tienen prioridad si hay más de 100 candidatas.
- No se modifica la sincronización ERP, la seguridad, el dashboard ni el módulo `logistica_transcash`.

**Instalación:** reemplazar solo la carpeta `transcash_guias_api`, reiniciar Odoo y actualizar este addon en Aplicaciones. Recargar el navegador para la WebApp.

**Pruebas manuales:**
1. Abrir ruta borrador con 3 guías elegibles y 1 bloqueada: marcar Todas → 3 marcadas, bloqueada no.
2. Desmarcar Todas → ninguna marcada; Cancelar → ruta intacta.
3. Activar Todas y Guardar selección → ruta muestra las guías.
4. Guía de otro chofer: sin autorización no seleccionable masivamente; con autorización sí, sujeta a validación final.
5. Filtros de búsqueda: marca solo las elegibles listadas.
6. Si hay más de 100, el selector masivo nunca marca más de 100.
7. Verificar la misma experiencia en la WebApp de operaciones.
