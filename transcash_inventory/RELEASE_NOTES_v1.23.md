# TRANSCASH Inventario Inteligente — v1.23 (Odoo 18 Community)

## Corrección de reactividad

- Unifica proveedor, formato y marca como filtros **globales** visibles en todas las pantallas.
- Categoría, marca, proveedor, formato, bodega, búsqueda y períodos se aplican sobre el mismo conjunto de SKU en el motor del dashboard (`calculate`).
- Las opciones desplegables y la escritura por texto provocan recálculo automático sin cambiar de menú; el texto se agrupa durante 160 ms para evitar cálculos innecesarios mientras el usuario escribe.
- Consolida actualizaciones mediante `requestAnimationFrame`, con aviso del intervalo y filtros activos.
- Conserva la selección de filtros durante la navegación entre pantallas.
- Evita resultados de IA obsoletos tras cambios de filtros. No llama automáticamente a OpenAI al seleccionar filtros.
- Corrige un identificador HTML duplicado para el aviso de período y actualiza el identificador de versión de CSS y JavaScript para evitar recursos anteriores almacenados en caché.
- No modifica modelos, tablas, endpoints, derechos de acceso, importaciones, fotografías ni configuraciones de IA existentes.

## Significado del período

Ventas, compras, utilidad bruta, ABC y estimaciones de cobertura usan el período seleccionado. Stock y valorización siguen siendo la fotografía del **último corte**, puesto que no hay cierres mensuales de inventario en la fuente.

## Verificación

Pruebas locales con 16.150 SKU importados: selección de 3/6/12 meses; filtro de PORCELANATO, proveedor GRAIMAN y formato 60×120; actualización dentro de Resumen, ABC, ABC×XYZ, Riesgo, Reposición, Bodegas, Compras/Proveedores, Explorador y Rentabilidad por proveedor; limpieza de filtros; sin errores JavaScript.

## Instalación

1. Respaldar base PostgreSQL y filestore.
2. Sustituir la carpeta `transcash_inventory` por la incluida en este ZIP, sin desinstalar.
3. Reiniciar el servicio Odoo 18 y **Actualizar** el módulo en Aplicaciones.
4. Cerrar la pestaña anterior y usar `Ctrl+F5`. El dashboard carga recursos identificados como `18.0.1.23.0`.
5. Probar los filtros sin navegar de sección. La validación dentro de la instancia Odoo del usuario sigue pendiente.
