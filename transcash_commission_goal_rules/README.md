# Transcash Commissions - Metas y Liquidaciones

Módulo de extensión para Odoo 18. Depende únicamente de `transcash_commission` y modifica la lógica de metas, gestión de administradores y reportes de liquidación.

## Funcionalidad

- La meta del vendedor es global al período y **no depende de localidad**.
- Solo vendedores con meta activa generan una fila en la liquidación.
- La gestión del administrador se configura en una cabecera por **Período + Administrador + Local**.
- En la cabecera se agregan los vendedores a cargo como líneas.
- Cada vendedor puede tener su propio mínimo administrativo:
  - monto fijo; o
  - porcentaje de su propia meta.
- Cada vendedor tiene un porcentaje específico de comisión para el administrador.
- El vendedor debe superar su mínimo administrativo y el local de la cabecera debe cumplir su meta.
- Las ventas usadas para comprobar el mínimo y calcular la gestión son todas las ventas del vendedor en el período; la localidad solo se usa como condición de habilitación.
- Se evita que el mismo vendedor quede asignado activamente más de una vez en un mismo período.
- Incluye PDF consolidado de liquidación y PDF individual por vendedor.

## Corrección de actualización 18.0.1.2.0

La versión anterior intentaba agrupar reglas históricas desde `model.init()`. Durante la actualización del registro de Odoo, ese código podía ejecutarse antes de que PostgreSQL creara la columna nueva `management_id`, produciendo:

`psycopg2.errors.UndefinedColumn: column r.management_id does not exist`

En `18.0.1.2.0` se eliminó completamente esa migración de `init()` y se movió a:

`upgrades/18.0.1.2.0/post-10-group-manager-lines.py`

La fase `post` se ejecuta después de que Odoo haya cargado y actualizado el esquema del módulo. El script verifica además que la tabla y la columna existan antes de migrar y es seguro ante reintentos.

## Cómo actualizar después del RPC_ERROR

1. Reemplazar la carpeta `transcash_commission_goal_rules` del servidor por la incluida en este ZIP.
2. Reiniciar el servicio de Odoo para que cargue el código nuevo.
3. Actualizar la lista de aplicaciones si fuera necesario.
4. Ejecutar **Actualizar** sobre `Transcash Commissions - Metas y Liquidaciones`.

No es necesario crear manualmente `management_id` ni ejecutar SQL en PostgreSQL.

## Dependencia

- `transcash_commission`
- `web`

Versión: `18.0.1.2.0`
