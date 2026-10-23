# v1.51 — Cobertura total de SKU para fotografías públicas (Odoo 18)

## Contexto
El inventario API puede incluir 16.136 SKU mientras la web pública ofrece solo ~969 artículos. El contador de la web NO equivale al universo del ERP. No es técnicamente posible descargar imágenes para SKU que no tienen ficha pública accesible.

## Correcciones
- El escáner ya no termina artificialmente en 90 páginas; incluye un límite de protección de 1.500 páginas y conserva el fin natural de catálogo en la tienda.
- Nuevo cron **TRANSCASH: Buscar fotografías para todos los SKU del inventario** (cada 2 minutos): crea de forma incremental registros `unchecked` para TODOS los SKU del último snapshot de cada empresa, 400 por lote/empresa. Avance persistente por empresa y por versión del snapshot, sin borrar asociaciones anteriores.
- Acelera el índice de catálogo a 2 páginas cada 2 minutos; una vez recorrido y completado el lote de SKU, consulta individualmente la tienda para los códigos aún no encontrados. Cada ejecución tiene un presupuesto de 45 s y máximo 8 intentos por compañía, con rotación multiempresa. Si la tienda responde con bloqueo HTTP 403/429/503, la búsqueda global se pausa automáticamente durante 30 minutos para evitar sobrecargarla.
- Conserva validación estricta del SKU en la URL de la ficha y validación real del binario JPEG, sin asignaciones aproximadas por nombre.
- Optimización de resolución: consulta O(1) para SKU canónicos del inventario, evitando búsquedas O(N²) al cubrir miles de SKU.
- La interfaz distingue 1) productos en el ERP, 2) enlaces públicos examinados, 3) SKU preparados para búsqueda y 4) fotos realmente verificadas. Muestra estados pendientes, sin publicar y fallidos y actualiza el progreso cada 15 segundos mientras la página permanece abierta.
- Se mantienen activas la reparación de miniaturas, el aislamiento multiempresa, la caché local, los roles, ABC/XYZ, reposición, IA, APIs y exportaciones de la versión 1.50.

## Operación
1. Respaldar PostgreSQL y filestore; reemplazar carpeta, reiniciar Odoo y actualizar el módulo sin desinstalar.
2. Comprobar en Ajustes > Técnico > Automatización > Acciones planificadas los crons de indexación, búsqueda de todos los SKU y reparación.
3. Los registros se irán preparando y comprobando gradualmente. La tienda no dispone necesariamente de fotos publicadas para todo el catálogo del ERP.
4. Para dar cobertura a SKU que faltan en la web pública se requiere publicar sus fichas o proporcionar un catálogo/API autenticado de fotos con asociación verificable por SKU.
