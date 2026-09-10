# Transcash Commissions - Metas y Liquidaciones

Versión: **18.0.1.6.0**  
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
