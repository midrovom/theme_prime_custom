# Corrección de compilación de estilos · 18.0.1.5.1

## Causa reproducida

La versión 1.5 contenía `width:min(420px,80vw)` en el selector de bodegas de `static/src/dashboard.scss`. LibSass interpreta `min()` como una función Sass y no puede comparar píxeles con unidades de ancho de pantalla.

Se reprodujo el fallo exacto del paquete entregado con el binding Python libsass 0.23.0 y LibSass 3.6.6:

```
Internal Error: Incompatible units: 'vw' and 'px'.
```

## Corrección

Se sustituyó esa declaración por dos propiedades CSS equivalentes para este ancho:

```css
width: 420px;
max-width: 80vw;
```

Conserva el límite responsive del selector sin pedir a Sass que compare las unidades. La corrección no cambia la lógica de importación, llaves, toneladas, planificación o favoritos.

## Actualizar

1. Reemplazar la carpeta `transcash_dispatch_analysis` con la de este paquete, conservando el nombre técnico.
2. Reiniciar Odoo.
3. Actualizar el módulo desde Aplicaciones.
4. Recargar el navegador con Ctrl+F5 para cargar los recursos regenerados.

No hace falta volver a importar el Excel. El reinicio y la actualización son necesarios para que Odoo reconstruya el paquete de recursos a partir del estilo corregido.

## Validación

- Se confirmó que el SCSS del ZIP 1.5 falla con LibSass.
- Se compiló correctamente el `dashboard.scss` corregido.
- Se compiló correctamente `import_progress.scss`.
- Se compilaron correctamente ambos archivos concatenados, en el orden del manifiesto.
- Se comprobó el manifiesto y que el paquete incluye los estilos corregidos.

Se incluye `tests/check_styles.py` para repetir la comprobación usando el entorno Python de Odoo, donde LibSass ya es una dependencia. La prueba se ejecutó con un compilador real; no se ha accedido al servidor del cliente ni compilado los otros módulos de su base.

Referencia de compatibilidad: https://sass-lang.com/documentation/values/calculations/#min-and-max
