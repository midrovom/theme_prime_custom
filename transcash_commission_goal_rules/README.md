# Transcash Commissions - Metas y Liquidaciones

Extensión de `transcash_commission` para Odoo 18. Versión 18.0.1.4.0.

## Configuración mensual unificada

El registro maestro es `commission.period`. Dentro del formulario del período se administran:

1. Metas de vendedores y rangos de comisión.
2. Proyectos por origen (`commission.project.rule`) específicos del período.
3. Metas de locales.
4. Gestión de administradores, con detalle por vendedor.
5. Bono de liquidación.
6. Notas.

Los menús separados de parámetros mensuales se ocultan para evitar mantener la misma configuración desde varios lugares. Los modelos originales no se eliminan.

## Vendedores de proyectos en liquidación

La liquidación ya no exige exclusivamente una meta retail. Se incluye una persona cuando tiene al menos una parametrización activa aplicable:

- meta de vendedor activa; o
- regla activa de proyecto por origen (del período o general); o
- es administrador con gestión activa; o
- tiene una regla específica de bono de liquidación.

Por tanto, un vendedor de proyectos con reglas `Local`, `Importado`, etc. puede aparecer y cobrar comisión de proyecto aunque no tenga una meta retail. Un vendedor sincronizado desde la API sin ninguna configuración sigue excluido.

## Duplicación mensual

El botón **Duplicar período y configuración** crea el siguiente período disponible y copia:

- metas de vendedores + rangos;
- proyectos/orígenes del período;
- metas locales;
- cabeceras y detalle de gestión administrativa;
- bonos de liquidación.

No copia liquidación, resultados ni estado calculado/aprobado/pagado. El nuevo período queda en borrador.

## Gestión de administradores

Cada cabecera corresponde a Período + Administrador + Local. Debajo están sus vendedores relacionados, con mínimo administrativo (monto fijo o % de la meta propia) y porcentaje específico de gestión. La meta local es una condición independiente para habilitar el pago al administrador.

## Reportes

Se mantienen el PDF consolidado de liquidación y el PDF individual.

## Actualización

Reemplazar la carpeta `transcash_commission_goal_rules`, reiniciar Odoo y actualizar el módulo desde Apps. No ejecutar SQL manual.

## Pago proporcional de metas de vendedores (18.0.1.5.0)

Las metas de vendedores tienen ahora dos modos de cálculo:

- **Por rangos:** conserva el comportamiento anterior mediante los rangos de cumplimiento.
- **Proporcional desde mínimo:** configura un `Cumplimiento mínimo (%)` y una `Comisión al 100% (%)`.

En modo proporcional:

1. Si el vendedor no alcanza el mínimo, la comisión propia es cero.
2. Si alcanza el mínimo pero todavía no llega al 100%, la tasa efectiva se calcula proporcionalmente al cumplimiento.
3. Al alcanzar o superar el 100%, la tasa queda topada en el porcentaje de comisión acordado al 100%.

Fórmula entre el mínimo y el 100%:

`Tasa efectiva = Comisión al 100% × Cumplimiento / 100`

`Comisión = Base de ventas × Tasa efectiva / 100`

Ejemplo: meta 35.000, ventas 32.000, mínimo 80% y comisión al 100% de 2%. El cumplimiento real es 91,4286%, la tasa efectiva es 1,8286% y la comisión sobre 32.000 es 585,14.

La configuración se copia cuando se duplica el período o cuando se usa `Duplicar a otro período` sobre una meta.
