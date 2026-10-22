# Transcash Guías API v2.16 – comparación correcta del destino en la PWA

## Criterio único

`NORMALIZAR(transcash.guia.destino) == NORMALIZAR(transcash.hoja.ruta.destino_id.codigo)`.

- **Guía:** utilizar exclusivamente el campo Char `destino` de `transcash.guia`.
- **Hoja de ruta:** `destino_id.codigo` del maestro `transcash.destino`.
- Se ignoran espacios, puntos, guiones, mayúsculas y caracteres invisibles.
- No se utiliza `destino_codigo`, ni el código auxiliar de `tc.guide`, ni `destino_id` de la guía para validar la coincidencia.
- Si alguno está vacío, la guía no se puede seleccionar.
- La PWA comprueba el criterio tanto al listar como al guardar.
- Solo después de validar se puede enlazar `guia.destino_id` con el destino seleccionado, para cumplir el flujo de confirmación existente.
- La importación ahora prioriza el código ERP para llenar `transcash.guia.destino`; si la nueva carga viene sin código, conserva `destino` existente en vez de sobrescribirlo con una dirección.

## Validación manual

1. Abrir guía `32799` y comprobar campo `Destino` (por ejemplo `NAJ`).
2. Abrir hoja y comprobar `Destino > Código ERP` (`NAJ`).
3. Ambos deben coincidir tras normalizar: `NAJ` == `NAJ`.
4. Buscar la guía por número en la PWA y verificar sus otras condiciones: registrada, sin hoja/embarque, mismo chofer y proveedor.
5. Si sigue sin mostrarse, comprobar el diagnóstico individual, que ahora muestra el valor directo del campo `Destino`.

El módulo principal `logistica_transcash` no se modifica. No se realizan fusiones, reasignaciones indiscriminadas ni cambios de viaje.
