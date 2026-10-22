# TRANSCASH Inventario Inteligente v1.42

- Interpretación libre: ChatGPT elabora un plan SELECT tipado por columnas, agregaciones, filtros, HAVING, GROUP BY, ORDER BY y LIMIT.
- Odoo compila exclusivamente SELECT parametrizados sobre la vista virtual acotada a empresa y versión; no ejecuta SQL libre del modelo.
- Eliminada la compilación Lark del arranque del módulo, evitando el error SIGNED_NUMBER; el parser antiguo queda bajo carga diferida para compatibilidad.
- Análisis narrativos fundamentados en los resultados reales cuando el usuario solicita explicaciones, interpretación o recomendaciones.
- Corregidos rankings por cantidad vendida y distinción de cantidades frente a importes monetarios.
- Se conservan navegación móvil, dashboards, cargas API, permisos multiempresa y exportaciones XLSX.
- Los importes monetarios y cantidades siguen sujetos a la granularidad y cobertura histórica del corte de inventario.
