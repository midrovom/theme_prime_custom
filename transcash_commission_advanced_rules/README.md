# Transcash Commissions - Reglas Avanzadas

Addon adicional para Odoo 18. No modifica los archivos de `transcash_commission` ni de `transcash_commission_goal_rules`.

## Dependencia

- `transcash_commission_goal_rules` (se recomienda tener instalada la versión 18.0.1.13.0 o posterior).

## 1. Liquidación: tres estados

Cada regla de liquidación incorpora **Mínimo para evitar castigo** además de la meta completa existente.

Ejemplo:

- Mínimo para evitar castigo: 7.000
- Meta completa de liquidación: 10.000
- Bono: 0,20 por m²
- Reducción por incumplimiento: la ya configurada en el período

Resultado:

1. Venta promocional < 7.000: se aplica la reducción/castigo existente y no se paga bono por m².
2. Venta promocional >= 7.000 y < 10.000: no se aplica castigo y no se paga bono por m².
3. Venta promocional >= 10.000: no se aplica castigo y sí se paga el bono por m² existente.

Si el nuevo mínimo se deja en 0, se usa la meta completa como mínimo de protección, conservando el comportamiento anterior.

## 2. Gestión de administradores por rangos

Cada vendedor a cargo puede tener varios rangos para el administrador.

Ejemplo:

- Desde 28.000 -> 2,00%
- Desde 35.000 -> 2,50%
- Desde 45.000 -> 3,00%

Con 34.000 se paga 2,00% sobre toda la base comisionable del vendedor; con 35.000 se paga 2,50%. No hay prorrateo entre rangos.

La meta del local continúa siendo una condición obligatoria. Si el local no cumple, el administrador no cobra aunque el vendedor haya alcanzado un rango.

Al duplicar el período/configuración también se copian los rangos administrativos.

## 3. Proyectos: factor global por rango x porcentaje del origen

Los vendedores de proyectos no corporativos usan sus ventas globales para determinar un rango de la meta del vendedor.

El valor `commission_percent` de ese rango se interpreta como **factor de proyecto**.

Ejemplo de rangos globales:

- Desde 8.000 -> 0,80
- Desde 10.000 -> 1,00

Configuración por origen:

- Local -> 1,00%
- Importado -> 2,00%

Si vende globalmente 8.500:

- Factor global = 0,80
- Local efectivo = 1,00% x 0,80 = 0,80%
- Importado efectivo = 2,00% x 0,80 = 1,60%

Si vende 10.000:

- Factor global = 1,00
- Local = 1,00%
- Importado = 2,00%

No existe interpolación entre rangos. Se utiliza siempre el último rango monetario alcanzado. El porcentaje/factor del rango no reemplaza al porcentaje del origen: lo multiplica.

El modo `% fijo por origen` permanece disponible para excepciones y no utiliza el factor global.

## Instalación

1. Mantener instalados los módulos actuales.
2. Copiar `transcash_commission_advanced_rules` al addons path.
3. Reiniciar Odoo.
4. Actualizar la lista de aplicaciones.
5. Instalar **Transcash Commissions - Reglas Avanzadas**.

No se requiere SQL manual ni actualizar/desinstalar el módulo principal.

## Validación realizada fuera del runtime Odoo

Se valida sintaxis Python, XML, manifest, ACL, ausencia de selectores XPath por `@string` e integridad del ZIP. La prueba final de instalación/cálculo debe ejecutarse en una base de pruebas con el runtime real de Odoo 18 y las versiones instaladas de los módulos dependientes.
