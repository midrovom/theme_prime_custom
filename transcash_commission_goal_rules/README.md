# Transcash Commission Goal Rules — 18.0.1.13.0

Extensión de `transcash_commission` para metas, proyectos, gestión administrativa, promociones, exclusiones, liquidaciones, PDF y dashboard.

## Cambios 1.13.0

### 1. Vendedores que no suman a la meta de la localidad

En **Período → Metas locales** se agrega el parámetro **Vendedores que no suman a meta local**.

Las ventas de esos vendedores:

- siguen contando para su meta global/rangos y su comisión propia o de proyecto;
- siguen pudiendo intervenir en su mínimo administrativo individual;
- **no** se suman al cumplimiento de la meta del local donde se registraron;
- por lo tanto tampoco pueden hacer que un administrador cobre gestión únicamente gracias a esas ventas cuando la regla exige meta del local.

El parámetro se copia automáticamente al duplicar el período.

El dashboard incorpora **Ventas para meta local** y la marca **Excluido de meta local** para auditoría.

### 2. Vendedores de proyectos: % propio por origen ajustado por cumplimiento global

La interpretación anterior se corrige: **Local, Importado, Nacional, etc. no comparten la misma tasa**. Cada origen tiene su porcentaje completo propio, por ejemplo:

- Local → 1,00%
- Importado → 2,00%

El vendedor conserva una meta global. Los rangos monetarios de la meta se mantienen como condición de entrada: por debajo del primer rango no se paga comisión de proyecto. Una vez alcanzado ese mínimo, la tasa efectiva de cada origen se obtiene con el cumplimiento real global:

```text
factor_global = min(ventas_globales / meta_global, 1.00)
tasa_efectiva_origen = tasa_origen_al_100% × factor_global
comisión_origen = base_comisionable_origen × tasa_efectiva_origen
```

Ejemplo: meta global 40.000; ventas globales 32.000 = 80%. Si Local está configurado a 1% e Importado a 2%:

- Local → 1,00% × 0,80 = 0,80% efectivo
- Importado → 2,00% × 0,80 = 1,60% efectivo

Al alcanzar 100% o más, se pagan los porcentajes completos: Local 1% e Importado 2%. El porcentaje guardado en los rangos de la meta del vendedor **no se reutiliza como tasa de origen**. La comisión estándar del vendedor no se paga adicionalmente sobre las mismas ventas de proyecto.

Se conserva el modo **% fijo por origen (sin ajuste)** para excepciones históricas.

### 3. Proyectos corporativos

El maestro `commission.seller` incorpora **Proyecto corporativo**.

Un vendedor marcado como proyecto corporativo:

- funciona como vendedor normal;
- usa su meta global y rangos monetarios;
- cobra comisión estándar sobre su base comisionable;
- no cobra simultáneamente la comisión de proyecto por origen;
- aparece en una sección independiente del PDF consolidado.

Esto permite conservar el rol existente del vendedor sin duplicar maestros.

### 4. PDF consolidado por secciones

El PDF total ahora presenta cuatro bloques independientes, cada uno con subtotal:

1. Vendedores retail.
2. Vendedores de proyectos.
3. Proyectos corporativos.
4. Administradores.

El PDF individual también muestra el **Grupo de liquidación** y usa la etiqueta **Meta global / referencial**.

## Funcionalidad preservada

Se mantienen:

- rangos por monto de ventas sin proporcionalidad entre escalones para vendedores retail y proyectos corporativos; para proyectos por origen, los rangos conservan el mínimo global y el porcentaje del origen se ajusta por el cumplimiento global real;
- clientes seleccionables y exclusiones por período;
- opción para que un cliente excluido cuente o no para metas/mínimos;
- gestión de administradores con mínimo individual por vendedor y meta local;
- promociones por archivo y coincidencia normalizada de nombre;
- bono por m²;
- reducción de tasa en puntos porcentuales cuando no se cumple liquidación;
- vendedores exentos de esa reducción;
- duplicación integral del período;
- PDF total e individual;
- dashboard interactivo Pivot/Graph/List.

## Dependencias

```python
"depends": ["transcash_commission", "web"]
```

No se incorporan módulos Odoo adicionales ni dependencias Python nuevas.

## Rendimiento

La excepción de meta local se resuelve con un `set` de IDs precargado y se aplica durante la única pasada de clasificación por localidad. No agrega búsquedas ORM por línea de venta.

La meta global de proyectos reutiliza las ventas ya agrupadas por vendedor y las reglas precargadas por origen. El dashboard continúa generándose agregado por dimensiones.

## Instalación / actualización

1. Reemplazar completamente la carpeta `transcash_commission_goal_rules`.
2. Reiniciar Odoo.
3. Actualizar la lista de aplicaciones si corresponde.
4. Ejecutar **Actualizar** sobre `Transcash Commissions - Metas y Liquidaciones`.
5. No ejecutar SQL manual.

La versión fue preparada para actualizar desde 18.0.1.12.0 sin cambios de dependencias. Las reglas de proyecto existentes en modo global deben tener configurado el nuevo significado de `Comisión del origen al 100% (%)`; si está en 0 y existen ventas de ese origen, el cálculo muestra un error de configuración en lugar de liquidar silenciosamente en cero.
