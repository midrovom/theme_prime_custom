# Inventario Inteligente TRANSCASH v1.35 (Odoo 18)

## Corrección principal

Las consultas de inventario que expresan condiciones como **«Dame una lista de porcelanatos que el stock en unidades sea menor a 100 y mayor a 0»** ya se reconocen como listados de existencias. La versión 1.34 solo reconocía una comparación cuando iba inmediatamente después de `stock`, y fallaba con «en unidades sea», «stock físico es», «stock en cantidad», entre otras construcciones naturales.

Al detectar un listado de stock, el sistema no invoca OpenAI: interpreta las condiciones estrictas en servidor, comprueba categoría, marca, formato y proveedor contra el catálogo de la **empresa activa**, genera un SELECT parametrizado sobre la versión vigente de Odoo y devuelve la tabla con SKU, descripción y stock. Las dos condiciones se combinan con AND, no se pierde ninguna, y los resultados de Cerámica no pueden aparecer en un filtro explícito de Porcelanato.

Ejemplo de predicados de la consulta (solo ilustrativo):

```sql
WHERE fp.snapshot_id = %s
  AND fp.company_id = %s
  AND LOWER(TRIM(fp.categoria)) = LOWER(TRIM(%s))
  AND fp.stock_unidades < %s
  AND fp.stock_unidades > %s
```

Los valores pasan como parámetros, no se concatena SQL del usuario. Las consultas se auditan en la bitácora privada y la pantalla solo muestra resultados y exportación Excel.

## Contexto para consultas con ChatGPT

El diccionario de modelos autorizados (`ai_schema.schema_context`) incluye ahora un glosario en español que diferencia el stock físico de su valor monetario y la categoría Porcelanato de Cerámica, además de un ejemplo de plan que usa varios límites simultáneos. Las preguntas complejas continúan utilizándolo para elaborar planes declarativos, **no SQL arbitrario**.

## Compatibilidad

Basada en v1.34; no altera modelos, tablas, sincronización API Administrator, fotos, permisos, menús, dashboard, exportaciones ni configuración multiempresa. No requiere una nueva importación. Actualizar addon sin desinstalarlo.

## Validación

Pruebas locales de variantes en español, validación de límites >0 y <100, separación de categorías, SQL parametrizado por empresa/versión y lectura de las importaciones históricas. La conexión con el PostgreSQL de producción debe comprobarse después de instalar.
