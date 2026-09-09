# Transcash Commissions - Metas y Liquidaciones

Extensión para `transcash_commission` que concentra la configuración mensual de metas y liquidaciones.

## Versión 18.0.1.6.0

### Comisión de vendedor proporcional

La comisión propia del vendedor se paga proporcionalmente una vez alcanzado el cumplimiento mínimo.

Fórmula:

```
cumplimiento = ventas / meta * 100
tasa_efectiva = comisión_al_100 * min(cumplimiento, 100) / 100
comisión = ventas * tasa_efectiva / 100
```

Si el cumplimiento es menor al mínimo configurado, la comisión es cero.

Ejemplo con meta 35.000, ventas 32.700,47 y comisión al 100% de 1%:

- cumplimiento: 93,4299%
- tasa efectiva: 0,934299%
- comisión: 305,52

Las configuraciones históricas por rangos también se interpretan proporcionalmente. Durante el upgrade se convierten a modo proporcional tomando:

- el primer rango con comisión positiva como cumplimiento mínimo;
- el porcentaje aplicable al 100% como comisión completa.

Los rangos históricos no se eliminan.

### Bono de liquidación sin localidad

La localidad ya no interviene en el bono de liquidación. Para cada vendedor se consideran conjuntamente todas sus ventas del período con `Indica_Precio = 3` (o el indicador parametrizado), se valida el mínimo global y se pagan los m² globales.

El campo localidad se oculta de las pantallas de bono. En bases antiguas donde existan filas por localidad, el cálculo ignora esa localidad y selecciona una sola regla aplicable para evitar doble pago.

### Funcionalidades que se mantienen

- meta de vendedor independiente de localidad;
- vendedores de proyectos liquidables por reglas de origen aunque no tengan meta retail;
- vendedores sin parametrización fuera de la liquidación;
- gestión de administradores con cabecera y vendedores a cargo;
- mínimo administrativo fijo o como porcentaje de meta;
- meta del local como condición exclusiva de la gestión administrativa;
- período como registro maestro de metas, proyectos, locales, administradores y bono;
- duplicación mensual de toda la configuración;
- PDF consolidado e individual.

## Actualización

1. Reemplazar la carpeta `transcash_commission_goal_rules` por esta versión.
2. Reiniciar Odoo.
3. Actualizar la lista de aplicaciones si corresponde.
4. Ejecutar **Actualizar** sobre el módulo.
5. Recalcular la liquidación del período para regenerar los valores con la fórmula proporcional.

No ejecutar SQL manual.
