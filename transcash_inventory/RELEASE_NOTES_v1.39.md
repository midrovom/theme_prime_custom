# Inventario Inteligente v1.39 — Consultas IA a SQL semántico

## Causa
El motor v1.38 desviaba peticiones con «más stock» al analizador de umbrales,
aunque el usuario solicitara un TOP ordenado y no un límite numérico.

## Arquitectura

- El navegador envía la pregunta sin clasificarla según frases codificadas.
- OpenAI, con el diccionario de modelos y métricas, devuelve SQL de lectura
  **sobre una vista semántica virtual `inventario`**.
- Un analizador formal del dialecto restringido comprueba gramática,
  operaciones, tablas, columnas y funciones. **Nunca ejecuta SQL original del modelo**.
- Odoo reconstruye SQL parametrizado; las tablas base están restringidas
  siempre a empresa y versión. Ventas y compras se agregan por separado.
- La transacción emplea límites de tiempo. Los detalles técnicos se registran
  únicamente en la bitácora administrativa.
- La UI recibe solo columnas y datos, y permite exportación XLSX.

## Consultas admitidas por el nuevo SQL semántico

Ejemplos NO codificados en rutas de decisión:

- «Dame el top 10 de productos con más stock en unidades».
- «Stock en unidades agrupado por formato».
- «Ventas y utilidad por marca y categoría con margen bruto».
- «Porcelanatos con stock superior a cero e inferior a cien».
- «Por SKU, muéstrame stock, cantidad comprada, cantidad vendida y última compra».

Funciones semánticas limitadas: `SUM`, `COUNT(*)`, `MIN`, `MAX`, `AVG`,
`MARGEN()`; condiciones `WHERE`, agregación `GROUP BY`, orden `ORDER BY`,
`LIMIT` máximo 3.000 filas. No soporta SQL libre de PostgreSQL, uniones a
otras tablas, procedimientos ni modificaciones; agregar nuevos campos o
nuevas operaciones implica ampliar el catálogo seguro.

## Seguridad

Solo la fuente virtual `inventario` y campos de la lista blanca.
Filtros de empresa y versión en todas las subconsultas, nunca tomados del modelo.
Filtros globales enviados desde el panel aplicados en conjunción a la consulta.
No se envían credenciales, SQL ni parámetros al navegador. No permitir que el
usuario edite el SQL que se ejecuta; auditar cualquier rechazo.

## Despliegue

Actualizar sobre v1.38, con copia de seguridad previa. No desinstalar.
Este paquete incorpora una copia localizada de `Lark` v1.3.1 (MIT) para que
la instalación no dependa de paquetes Python adicionales.
Se verificó compilación, parsing, filtros, rechazo de sentencias no seguras,
formato XLSX y resultados simulados. Es obligatorio probar la llamada real
OpenAI + PostgreSQL en un entorno Odoo 18 de pruebas antes de usarlo en producción.
