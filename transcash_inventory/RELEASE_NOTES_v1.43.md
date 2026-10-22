# Inventario Inteligente v1.43 — Consultas naturales más robustas

## Origen de la incidencia
El planificador GPT devolvía SQL válido como intención, pero no siempre ajustado
al dialecto limitado del analizador. El segundo intento repetía generación SQL libre,
por lo que solicitudes sencillas terminaban con "SELECT no autorizado".

## Corrección
1. Mantener ChatGPT como intérprete libre de la pregunta (sin enumerar frases).
2. Primero generar un SELECT sobre la vista semántica protegida `inventario`.
3. Si no supera el parser, solicitar a ChatGPT un plan JSON estricto (columnas,
   agregaciones, filtros, grupos, orden, límite) y compilarlo de nuevo en Odoo.
4. Volver a analizar ese SELECT en el parser de seguridad antes de ejecutarlo,
   con valores parametrizados, empresa y versión obligatorias, timeout y límite.
5. Normalizar opcionalmente los delimitadores Markdown SQL y un único `;` final.
6. Mejorar el contexto para interpretar "productos más vendidos" como unidades
   vendidas si el usuario no pide facturación monetaria.
7. Guardar el diagnóstico de ambos intentos únicamente en la bitácora administrativa.

## Alcance
La mejora no altera tablas, datos importados, endpoints, menú móvil, dashboard,
configuración de IA o exportación Excel. Las preguntas que requieren campos no
existentes siguen sin poder resolverse; ninguna IA puede garantizar literalmente
todas las consultas de lenguaje natural.

## Actualización
Reemplazar COMPLETAMENTE el módulo `transcash_inventory`, reiniciar TODOS los
procesos de Odoo y actualizar Aplicaciones. Comprobar `__manifest__.py` 18.0.1.43.0.
No desinstalar ni borrar datos, y no reimportar la información por este cambio.
