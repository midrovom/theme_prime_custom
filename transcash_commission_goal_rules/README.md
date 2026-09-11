# Transcash Commissions - Metas y Liquidaciones

Versión: **18.0.1.9.0**

Extensión de `transcash_commission` para la parametrización mensual de metas, proyectos, gestión administrativa, promociones y reportes de liquidación.

## Cambio 18.0.1.9.0 - productos promocionales por archivo y nombre

`Indica_Precio` deja de identificar las ventas de liquidación/promoción.

En cada **Período**, pestaña **Bono liquidación**, se carga un archivo con los productos en promoción. Se admiten:

- `.xlsx` sin dependencias Python adicionales;
- `.csv` / `.txt` delimitados por coma, punto y coma, tabulador o `|`;
- `.xls` antiguo solo si el servidor ya tiene instalada la librería `xlrd`.

El importador busca una columna como `nProducto`, `Producto`, `Nombre Producto`, `Descripción Producto`, `Descripción`, `Product Name`, etc. El código se puede conservar como referencia, pero **no forma parte de la comparación**.

### Comparación

La venta se compara contra `commission.sale.product_name` (`nProducto` recibido de la API).

La comparación es exacta por **nombre normalizado**:

- ignora mayúsculas/minúsculas;
- ignora acentos;
- normaliza signos, saltos de línea y espacios repetidos;
- no usa `Codproducto` ni el código del archivo promocional;
- no usa `Indica_Precio`.

Ejemplo:

`CERÁMICA CSL CUBIC GREY C1 (27*45) 1.70 M2`

y

`ceramica  csl cubic grey c1 27 45 1.70 m2`

son la misma clave de comparación.

El sistema **no hace coincidencia difusa/parcial**. El nombre completo normalizado debe coincidir para evitar incluir productos distintos por semejanza textual.

### Efecto en el cálculo

La misma lista promocional se utiliza para:

1. calcular las ventas promocionales que validan el `Monto mínimo de ventas` de la regla de liquidación;
2. sumar `Cantidad` como m² de los productos coincidentes;
3. calcular el bono `m² x valor por m²` cuando se cumple el mínimo;
4. decidir si corresponde la reducción en puntos porcentuales de la comisión propia/proyectos por incumplir la meta de liquidación.

Si un período tiene reglas de liquidación pero no tiene productos promocionales cargados, el cálculo se bloquea con un mensaje claro. Esto evita penalizar vendedores por una lista faltante.

Al reemplazar el archivo se reemplaza la lista completa de productos del período. También se puede editar manualmente la lista después de importarla.

Al duplicar un período, la lista de productos promocionales **sí se copia** como parte de la plantilla mensual, pero el archivo binario original no se arrastra. Puede cargarse un archivo nuevo para reemplazar la lista del mes copiado.

## Rangos de comisión de vendedor

Las metas propias usan rangos por monto vendido. Se toma el último umbral alcanzado y su porcentaje se aplica a **toda la base de ventas**.

Ejemplo:

- desde 32.000 -> 0,80%;
- desde 40.000 -> 1,00%.

Entonces 32.000, 34.000 y 39.999 pagan 0,80%; desde 40.000 pagan 1,00%. No hay interpolación proporcional ni cálculo marginal por tramos.

## Restricción por meta de liquidación

Si el vendedor no alcanza el mínimo de ventas promocionales configurado, se pueden restar puntos porcentuales directamente de la tasa ganada.

Ejemplo: 2,00% ganado - 0,50 p.p. = 1,50% efectivo.

Los vendedores seleccionados como exentos conservan la tasa original. La reducción no afecta la comisión de gestión del administrador ni el bono por m².

## Gestión de administradores

La configuración es una cabecera por administrador/período/local con detalle de vendedores a cargo. Cada vendedor puede tener un mínimo administrativo fijo o un porcentaje de su meta, además de un porcentaje específico de comisión para el administrador. El local de la cabecera debe cumplir su meta.

## Período como configuración mensual

Dentro del período se administran:

- metas y rangos de vendedores;
- proyectos por origen;
- metas locales;
- gestión de administradores;
- productos promocionales y reglas de liquidación;
- vendedores exentos de restricción.

`Duplicar período y configuración` copia la parametrización al siguiente período sin copiar liquidaciones/resultados calculados.

## Liquidación y PDF

Se mantienen el PDF consolidado y el PDF individual. La auditoría de liquidación registra ventas promocionales, m², mínimo, tasa efectiva y reducción aplicada. Los vendedores sin una parametrización activa de comisión no se muestran; los vendedores de proyectos sí pueden aparecer sin meta retail cuando tienen una regla de proyecto activa.

## Actualización

1. Reemplazar la carpeta `transcash_commission_goal_rules` por esta versión.
2. Reiniciar Odoo.
3. Actualizar el módulo desde Apps.
4. En los períodos que tengan reglas de liquidación, cargar la lista de productos promocionales antes de recalcular.

No se requiere SQL manual.
