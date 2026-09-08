# Transcash Commissions - Metas y Liquidaciones

Extensión para Odoo 18 sobre `transcash_commission`.

Este módulo concentra los cambios funcionales de metas, gestión de administradores y reportes, sin modificar el modelo de ventas ni la sincronización del módulo base.

## 1. Metas de vendedores

- La meta del vendedor es global para el período.
- La meta no depende de localidad.
- Todas las ventas del vendedor dentro del período participan en su cumplimiento.
- Solo puede existir una meta activa por vendedor y período.
- Un vendedor sin meta activa no genera resultado en la liquidación y no aparece en los PDF de liquidación.

## 2. Gestión de comisiones de administradores

La configuración se realiza en un solo registro por:

- Período
- Administrador
- Local cuya meta debe cumplirse

En la parte inferior del formulario existe un detalle **Vendedores a cargo**. Cada línea contiene:

- Vendedor
- Tipo de mínimo
- Mínimo de venta fijo o porcentaje de la meta del vendedor
- Meta del vendedor como referencia
- Mínimo efectivo calculado
- Porcentaje específico de comisión del administrador
- Base de cálculo
- Activo

Ejemplo:

| Vendedor | Tipo mínimo | Parámetro | Mínimo efectivo | % Admin |
|---|---|---:|---:|---:|
| Vanessa | Monto fijo | 6.000 | 6.000 | 0,75% |
| Pedro | % de meta | 80% | 8.000 | 0,50% |
| José | Monto fijo | 5.000 | 5.000 | 1,00% |

Esto permite administrar todos los vendedores de un administrador desde una sola cabecera.

## 3. Condiciones para pagar gestión

Por cada vendedor se validan de forma independiente:

1. El vendedor alcanza su **mínimo administrativo**.
2. El local configurado en la cabecera cumple su meta local.
3. Si ambas condiciones se cumplen, el administrador recibe el porcentaje definido en la línea del vendedor.

El mínimo administrativo es independiente de la comisión propia del vendedor. Puede expresarse como:

- monto fijo; o
- porcentaje de la meta propia del vendedor.

La meta propia del vendedor se utiliza para calcular la comisión del vendedor. Solo se usa como referencia del mínimo administrativo cuando se selecciona expresamente `% de la meta del vendedor`.

Las ventas utilizadas para validar el mínimo administrativo son todas las ventas del vendedor en el período, sin filtrar por local. El local de la cabecera funciona como condición adicional de cumplimiento.

## 4. Liquidaciones

La liquidación genera filas exclusivamente para vendedores que tengan meta activa en el período. Esto evita mostrar vendedores creados por sincronización que todavía no tienen parametrización de comisiones.

## 5. PDF

Incluye:

- PDF consolidado de liquidación.
- PDF individual por vendedor/administrador.

El PDF consolidado utiliza únicamente los resultados generados en la liquidación, por lo que tampoco muestra vendedores sin meta.

El PDF individual presenta ventas, meta, cumplimiento, comisión propia, proyectos, gestión, bono y detalle de auditoría.

## Instalación

1. Mantener instalado `transcash_commission`.
2. Copiar `transcash_commission_goal_rules` a la ruta de addons.
3. Actualizar la lista de aplicaciones.
4. Instalar o actualizar **Transcash Commissions - Metas y Liquidaciones**.

El módulo técnico es `transcash_commission_goal_rules`.
