# Transcash Commissions - Metas y Liquidaciones

## Corrección 1.8.1: rangos estrictamente escalonados

La comisión de vendedor se determina por el **último umbral de venta alcanzado** y ese porcentaje se aplica a **toda la base de ventas**. No existe interpolación proporcional entre rangos ni cálculo marginal por tramos.

Ejemplo: 32.000 = 0,8%; 34.000 = 0,8%; 39.999 = 0,8%; 40.000 = 1,0%. Con 34.000 la comisión antes de cualquier ajuste de liquidación es 34.000 x 0,8% = 272.

La versión fuerza todas las metas de vendedor al modo `sales_tier` para impedir que configuraciones legadas proporcionales vuelvan a intervenir en el cálculo.

Versión: **18.0.1.8.0**  
Dependencia: `transcash_commission`

## Cambio principal 1.6.0: metas de vendedores por rangos de venta

La comisión propia del vendedor se calcula ahora por **escalones de monto vendido**. Cada meta de vendedor conserva una **meta referencial** para mostrar el porcentaje de cumplimiento y para reglas administrativas que usen "% de la meta", pero el porcentaje de comisión se selecciona exclusivamente por los rangos configurados.

Ejemplo de rangos:

| Venta mínima del rango | Comisión |
| ---: | ---: |
| 10.000 | 1,00% |
| 15.000 | 1,50% |
| 25.000 | 2,00% |

Resultado:

- ventas de 9.999: 0%;
- ventas de 10.000 a 14.999,99: 1%;
- ventas de 15.000 a 24.999,99: 1,5%;
- ventas desde 25.000: 2%.

El porcentaje del rango alcanzado se aplica sobre **toda la base de ventas** definida en la meta (`Total neto`, `Total precio` o `Utilidad`). No es un cálculo marginal por tramo.

El mínimo para empezar a comisionar queda determinado naturalmente por el primer rango. Si el primer rango es 10.000, cualquier venta inferior a 10.000 paga 0.

## Meta referencial

El campo `Meta referencial` se mantiene porque se utiliza para:

- mostrar el porcentaje de cumplimiento en la liquidación y PDF;
- calcular un mínimo administrativo cuando una línea de gestión está configurada como `% de la meta del vendedor`.

La meta referencial **no selecciona el porcentaje de comisión propia**; esa selección la hacen los rangos por monto de ventas.

## Configuración mensual unificada

El período continúa siendo el registro principal y agrupa:

- metas de vendedores y sus rangos;
- proyectos por origen;
- metas locales;
- gestión de administradores y vendedores a cargo;
- bono de liquidación;
- notas.

`Duplicar período y configuración` copia la parametrización al siguiente período sin copiar resultados ni liquidaciones calculadas.

## Vendedores de proyectos

Un vendedor con una regla activa de proyecto/origen puede aparecer en la liquidación aunque no tenga meta retail. Un vendedor sin ninguna parametrización aplicable permanece fuera de la liquidación.

## Gestión de administradores

Cada cabecera contiene administrador + período + local. Debajo se parametrizan sus vendedores a cargo con:

- mínimo fijo o mínimo como porcentaje de la meta referencial del vendedor;
- porcentaje específico que gana el administrador;
- base de cálculo.

El vendedor debe superar su mínimo administrativo y el local asignado debe cumplir su meta.

## Reportes

Se mantienen:

- PDF consolidado de liquidación;
- PDF individual por vendedor;
- detalle auditable del porcentaje aplicado.

## Actualización desde 1.5.0 o anterior

La versión incluye una migración `post` que transforma configuraciones anteriores a rangos por monto:

- rangos por porcentaje de cumplimiento se convierten a umbrales monetarios usando `meta x porcentaje / 100`;
- metas proporcionales sin rangos reciben escalones iniciales en el mínimo anterior y en el 100% de la meta;
- todas las metas quedan en modo `Por rangos de venta`.

Después de actualizar es recomendable revisar los rangos de vendedores para ajustarlos a la nueva política comercial exacta.

No ejecutar SQL manual para la actualización.


## Corrección 18.0.1.6.1

Se corrige la herencia de la vista de metas de vendedor para Odoo 18.
La versión 18.0.1.6.0 utilizaba `@string` como selector XPath sobre el separador
`Rangos de cumplimiento`; Odoo 18 rechaza ese patrón con
`View inheritance may not use attribute 'string' as a selector`.
Ahora el separador se localiza estructuralmente como el hermano inmediatamente
anterior a `tier_ids`, sin depender de etiquetas traducibles.
## Histórico 18.0.1.7.0: reducción sobre el valor de comisión (reemplazado en 1.8.0)

Esta sección describe el comportamiento anterior y se conserva solo como referencia de actualización. Desde 1.8.0 la reducción ya no se calcula sobre el valor comisionado.

El período incorporaba dos parámetros en la pestaña **Bono liquidación**:

- `Reducción de comisión por no cumplir liquidación (%)`: porcentaje que se descuenta cuando un vendedor no alcanza una meta de liquidación aplicable.
- `Vendedores exentos de restricción`: vendedores a los que no se les aplica la reducción aunque no alcancen la meta.

La meta de liquidación continúa siendo el `Monto mínimo de ventas` configurado en las reglas de bono de liquidación. La regla específica del vendedor prevalece sobre la regla general para la misma localidad, igual que en el cálculo del bono.

Si existen varias metas de liquidación aplicables y al menos una no se cumple, la reducción se aplica **una sola vez**.

La base de reducción es:

`Comisión propia + Comisión de proyectos`

No se reduce la comisión de gestión del administrador. El bono de liquidación ya queda en cero para la regla que no alcanza su mínimo.

Ejemplo:

- comisión propia: 500,00;
- comisión proyectos: 100,00;
- reducción del período: 20%;
- meta de liquidación incumplida;
- vendedor no exento.

Base sujeta a reducción = 600,00. Reducción = 120,00. La liquidación resta esos 120,00 del total.

Si el mismo vendedor está en `Vendedores exentos de restricción`, la reducción es 0,00 y el PDF deja la situación registrada en el detalle de auditoría.

Al duplicar el período se copian tanto el porcentaje de reducción como la lista de vendedores exentos.

Los PDF consolidado e individual muestran el descuento por meta de liquidación y el cálculo queda registrado como una línea de auditoría.


## Corrección 18.0.1.7.1

Los rangos vigentes se configuran por `sales_threshold`, pero el módulo base conserva
`min_achievement` como campo obligatorio. Desde esta versión toda línea nueva de
`commission.seller.target.tier` asigna internamente `min_achievement = 0.0` y
`max_achievement = 0.0`. Esto evita el error de campo obligatorio al crear rangos
por monto desde la interfaz, APIs, duplicación de metas o duplicación del período.


## Cambio 18.0.1.8.0: la liquidación reduce la tasa, no el valor ya comisionado

La restricción por incumplir la meta de liquidación ahora se expresa en **puntos porcentuales (p.p.)** y se resta directamente de la tasa de comisión obtenida por ventas.

Ejemplo:

- rango alcanzado: 2,00%;
- reducción de tasa por liquidación: 0,50 p.p.;
- tasa efectiva: 1,50%;
- ventas base: 32.000,00;
- comisión efectiva: 32.000 x 1,50% = 480,00.

No se calcula `comisión x porcentaje de descuento`. La tasa efectiva nunca puede bajar de 0%.

La misma mecánica aplica a cada línea de comisión de proyectos/origen. La comisión de gestión del administrador y el bono de liquidación no se reducen. Los vendedores incluidos como exentos mantienen sus tasas originales.

Para proteger datos históricos, el parámetro anterior `Reducción sobre comisión (%)` se conserva como campo legado oculto y **no se reutiliza** con la nueva semántica. Debe configurarse el nuevo campo `Reducción de tasa por no cumplir liquidación (p.p.)`. Esto evita interpretar accidentalmente un valor histórico como 20% como una resta de 20 puntos porcentuales.

En la auditoría de la liquidación, las líneas de comisión muestran la tasa efectiva y su descripción registra la tasa original, los puntos restados y la tasa final. El campo de reducción monetaria es informativo; el total no lo vuelve a restar porque la comisión propia/proyecto ya fue recalculada con la tasa efectiva.
