# Transcash Commission Goal Rules — 18.0.1.11.0

Extensión de `transcash_commission` para metas, promociones, exclusiones de clientes, gestión administrativa, liquidaciones y analítica.

## Cambios 1.11.0

### Cliente seleccionable en el período

Se incorpora el maestro independiente `commission.client`. El maestro se alimenta automáticamente al crear/importar ventas mediante ORM y no depende de `res.partner`.

Cada `commission.sale` conserva el texto original `client` y además queda enlazada mediante `client_id` al cliente maestro normalizado. Al instalar/actualizar esta versión se crean y enlazan los clientes históricos existentes.

En **Período → Clientes excluidos** ya no se escribe el nombre manualmente: se selecciona `client_id` desde un Many2one. El texto `client_name` se conserva únicamente por compatibilidad con versiones anteriores.

La exclusión mantiene dos comportamientos:

* La venta del cliente seleccionado **nunca genera comisión**.
* `Contar para metas / mínimos = Sí`: la venta sí interviene en rangos del vendedor, meta local, mínimo administrativo y mínimo promocional.
* `Contar para metas / mínimos = No`: la venta también se excluye de dichos cumplimientos.

### Rendimiento del cálculo

Se redujeron operaciones costosas dentro de los bucles mensuales:

* clasificación de clientes en una sola pasada y sin uniones crecientes de recordsets;
* agrupación de ventas por IDs de vendedor/local antes del cálculo;
* metas de vendedores precargadas en un mapa por vendedor;
* reglas de proyectos precargadas para el período;
* nombres promocionales calculados una sola vez y reutilizados;
* no se vuelve a clasificar el mismo conjunto de ventas al generar el dashboard;
* el dashboard se materializa **agregado por dimensiones**, en vez de crear una fila por venta y por componente.

La analítica conserva mes, comisionista, vendedor origen, local, bodega, línea de producto, origen, cliente y componente.

### Dashboard interactivo en una sola vista

Menú: **Comisiones → Dashboard → Dashboard interactivo**.

La vista predeterminada es un Pivot nativo de Odoo:

* panel lateral para seleccionar vendedor/comisionista, período, local y componente;
* meses en columnas;
* localidades → bodegas → líneas de producto en filas;
* medidas de ventas brutas, ventas para metas, ventas comisionables y comisión;
* cambio directo a gráfico o lista desde la misma acción;
* el gráfico muestra evolución mensual segmentada por local.

No se incorpora JavaScript propio, Spreadsheet, `board` ni módulos Enterprise. Se utilizan las vistas estándar `pivot`, `graph`, `list` y `searchpanel` de Odoo 18.

## Dependencias

Manifest:

```python
"depends": ["transcash_commission", "web"]
```

No se añadieron dependencias Odoo adicionales ni paquetes Python opcionales nuevos.

## Instalación / actualización

1. Reemplazar la carpeta `transcash_commission_goal_rules`.
2. Reiniciar Odoo.
3. Actualizar la lista de aplicaciones si corresponde.
4. Ejecutar **Actualizar** sobre `Transcash Commissions - Metas y Liquidaciones`.
5. No ejecutar SQL manual.

La actualización `18.0.1.11.0` incluye migración post-esquema para crear el maestro de clientes desde ventas/exclusiones históricas y enlazar `client_id`. Un `post_init_hook` cubre también la instalación inicial del addon sobre una base que ya contenga ventas en `transcash_commission`.

## Funcionalidad preservada

Se mantienen las funcionalidades previas: metas por rangos monetarios, proyectos por origen, gestión de administradores, metas locales, productos promocionales por coincidencia normalizada de nombre, bono por m², reducción de tasa por incumplimiento promocional, vendedores exentos, duplicación integral del período y PDF total/individual.

### Dashboard histórico después de actualizar

Las líneas analíticas 1.10.0 existentes se conservan para no ejecutar una reconstrucción pesada durante el upgrade. Para aprovechar la agregación optimizada en períodos históricos, abra la liquidación y pulse **Actualizar dashboard**. Los nuevos cálculos/recalculos ya generan directamente el formato agregado 1.11.0.
