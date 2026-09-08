# Transcash Commissions - Metas y Liquidaciones

Addon de extensión para Odoo 18. Depende de `transcash_commission` y no modifica los archivos del módulo original.

## Alcance

Este módulo incorpora únicamente los cambios funcionales solicitados sobre metas, gestión administrativa y liquidaciones:

1. **Meta de vendedor sin localidad**
   - La meta es única por vendedor y período.
   - La comisión propia suma todas las ventas del vendedor dentro del período, independientemente de la localidad de la venta.
   - Se mantienen los rangos de cumplimiento y porcentajes del módulo original.

2. **Gestión del administrador por vendedor**
   - Nueva regla `commission.manager.seller.rule`.
   - Configuración por **Período + Administrador + Vendedor a cargo**.
   - Cada vendedor puede tener un mínimo administrativo distinto.
   - El mínimo puede expresarse como:
     - monto fijo de ventas; o
     - porcentaje de la meta propia del vendedor.
   - El porcentaje de comisión de gestión es un parámetro independiente y específico para esa relación.
   - El local asignado debe cumplir su meta para habilitar el pago de gestión.
   - Las ventas del vendedor usadas para validar su mínimo y calcular la gestión se toman de todas sus localidades; el local asignado actúa únicamente como condición de cumplimiento local.

3. **Vendedores sin meta**
   - No se crea `commission.result` para vendedores sin meta activa en el período.
   - Por ello no aparecen en pantalla ni en el PDF consolidado.
   - Un administrador también debe tener una meta activa si se desea que tenga una fila propia de liquidación y reciba en ella su comisión de gestión.

4. **PDF de liquidación total**
   - A4 horizontal.
   - Incluye ventas, meta, cumplimiento, comisión propia, proyectos, gestión, bono de liquidación y total por vendedor.
   - Solo lista resultados efectivamente liquidados, es decir, vendedores con meta activa.

5. **PDF individual**
   - A4 vertical.
   - Resume la liquidación del vendedor y muestra el detalle de auditoría del cálculo.

## Ejemplo de gestión administrativa

Meta propia del vendedor: 10.000

Regla administrativa:

- Tipo de mínimo: `% de la meta del vendedor`
- Mínimo: 80%
- Mínimo administrativo efectivo: 8.000
- Comisión de gestión del administrador: 0,75%
- Local para validar meta: SDO

Si el vendedor vende 8.500 en el período y SDO cumple su meta, el administrador gana:

`8.500 x 0,75% = 63,75`

La comisión personal del vendedor se calcula por sus propios rangos de cumplimiento y no por esta regla administrativa.

## Instalación

1. Mantener instalado `transcash_commission`.
2. Copiar la carpeta `transcash_commission_goal_rules` al path de addons.
3. Actualizar la lista de aplicaciones.
4. Instalar **Transcash Commissions - Metas y Liquidaciones**.

El módulo antiguo `commission.manager.rule` permanece físicamente en el módulo base para no alterar datos ni código original, pero esta extensión oculta su menú y reemplaza su uso en el cálculo por la nueva regla específica por vendedor.
