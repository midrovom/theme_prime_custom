# Transcash V5.10 — Valor visible al registrar embarque

## Cambio solicitado

Al abrir **Logística Transcash → Armar embarque desde rutas**, seleccionar las hojas de ruta muestra **en ese momento**:

- Valor de las rutas seleccionadas (suma de las tarifas capturadas en cada hoja).
- Valor de rutas existentes, si se está ampliando un embarque en preparación.
- **Valor referencial total del embarque**, antes de presionar *Registrar embarque con este valor*.

Al confirmar, la ficha abre el embarque y muestra arriba **Valor del embarque**, con la tarifa referencial y, para Jefe de Logística / Contabilidad, el **valor acordado**. Ambos valores también aparecen en el listado de embarques. El operador de rutas consulta el referencial, pero **no puede negociar ni aprobar** importes.

**Fórmula:** Valor referencial del embarque = suma de `tarifa_referencial` de sus hojas de ruta. El valor se guarda como referencia de cada hoja al planificarla, por lo que cambiar el maestro de tarifas después no modifica el historial.

Si el jefe de Logística negocia un importe diferente, el **valor acordado** permanece distinto del referencial; agregar nuevas rutas no sobrescribe una negociación manual. Debe verificarse el valor acordado antes de aprobar el flete.

## Actualizar desde V5.9 en VPS

1. Respalda PostgreSQL, filestore y addon original.
2. Sustituye la carpeta `logistica_transcash` por la de V5.10, sin desinstalar.
3. Reinicia el servicio Odoo correspondiente.
4. Desde **Aplicaciones**, actualiza *Transcash - Seguimiento de Guías*.
5. Prueba con 2 rutas con tarifas diferentes y confirma que el valor calculado equivale a la suma.
6. Con un usuario de **Operador Logística**, verifica que ve el valor referencial pero no puede negociar el monto; con el **Jefe de Logística**, verifica que puede cambiar el acordado y aprobar después.

**Nota:** La actualización requiere pruebas en Odoo 18 real. Se validó estáticamente la estructura; no se ejecutaron pruebas de integración en el VPS.
