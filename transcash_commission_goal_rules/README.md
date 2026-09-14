# Transcash Commissions - Metas y Liquidaciones

Versión: **18.0.1.10.0**

Extensión para Odoo 18 sobre el módulo técnico `transcash_commission`.

## Dependencias Odoo

Solo declara:

- `transcash_commission`
- `web`

No se agregó ningún addon Enterprise ni módulo `board`, `spreadsheet`, `sale`, `account` o similar. El dashboard usa vistas estándar de Odoo (`graph`, `pivot`, `list`) sobre un modelo analítico propio, evitando dependencias adicionales de frontend.

El lector de promociones sigue usando únicamente la librería estándar de Python para XLSX/CSV. El formato `.xls` antiguo continúa siendo opcional y requiere `xlrd`; no es necesario para `.xlsx` o `.csv`.

## Exclusiones de clientes por período

En **Comisiones > Operación > Períodos y metas > Clientes excluidos** se configuran los clientes cuyas ventas no deben generar comisión.

Cada línea contiene:

- Cliente.
- **Contar para metas / mínimos**.
- Observación.
- Activo.

La coincidencia se hace por nombre normalizado del campo `Cliente` de `commission.sale`. Se ignoran diferencias de mayúsculas/minúsculas, acentos, signos y espacios repetidos. No se utiliza coincidencia difusa para evitar excluir clientes parecidos por error.

### Regla de cálculo

Una venta de cliente excluido **nunca genera comisión**, incluso si se marca para contar en metas.

Si **Contar para metas / mínimos = Sí**:

- cuenta para seleccionar el rango de comisión del vendedor;
- cuenta para el porcentaje de cumplimiento de su meta;
- cuenta para metas de local;
- cuenta para el mínimo del vendedor que habilita comisión al administrador;
- cuenta para el mínimo de venta de productos promocionales/liquidación;
- **no** integra la base sobre la cual se paga la comisión;
- **no** genera comisión de proyecto;
- **no** genera comisión de gestión del administrador;
- **no** genera bono por m².

Si **Contar para metas / mínimos = No**, se excluye tanto del pago como de todos esos cumplimientos.

Ejemplo:

- rango: desde 35.000 -> 1%;
- venta normal comisionable: 30.000;
- cliente excluido: 7.000;
- `Contar para metas = Sí`.

El vendedor califica con 37.000 y alcanza el rango de 1%, pero la comisión se calcula solamente sobre 30.000: **300**.

## Dashboard de comisiones

Nuevo menú **Comisiones > Dashboard** con:

- Resumen mensual.
- Por vendedor.
- Por línea de producto.
- Por almacén / bodega.

Las vistas son estándar `graph/pivot/list` y permiten además analizar por:

- período/mes;
- comisionista;
- vendedor que originó la venta;
- localidad;
- línea de producto;
- almacén/bodega;
- origen;
- cliente;
- componente de comisión.

Medidas disponibles:

- ventas brutas;
- ventas consideradas para metas;
- ventas comisionables;
- comisión;
- líneas de venta;
- cantidad/m².

El dashboard se reconstruye automáticamente al calcular/recalcular la liquidación. En una liquidación ya existente se puede usar **Actualizar dashboard** sin recalcular los importes de comisión.

La comisión se distribuye a nivel de venta usando las tasas efectivas finales del cálculo (incluyendo la reducción de tasa por incumplir liquidación), por lo que se puede agrupar por línea de producto y almacén.

## Funciones anteriores preservadas

Se mantienen:

- vendedor independiente de `res.users`;
- metas del vendedor sin localidad;
- rangos escalonados por monto de venta, aplicados sobre toda la base comisionable;
- proyectos por origen sin necesidad de meta retail;
- gestión de administrador con cabecera y vendedores a cargo;
- mínimo administrativo fijo o porcentaje de meta;
- meta local como condición de gestión;
- lista de productos promocionales por nombre desde XLSX/CSV;
- bono por m²;
- reducción de tasa por incumplir la meta promocional;
- vendedores exentos de esa reducción;
- vendedores sin parametrización fuera de la liquidación;
- duplicación integral del período y su configuración;
- PDF total e individual.

## Actualización

1. Reemplazar la carpeta existente `transcash_commission_goal_rules`.
2. Reiniciar Odoo.
3. Actualizar la lista de aplicaciones si corresponde.
4. Actualizar el módulo **Transcash Commissions - Metas y Liquidaciones**.
5. No ejecutar SQL manual.

Las nuevas columnas/modelos son creados por el ORM durante la actualización.
