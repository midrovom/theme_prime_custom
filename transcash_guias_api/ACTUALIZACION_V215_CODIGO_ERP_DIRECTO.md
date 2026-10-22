# v2.15 - Comparación directa de código de destino ERP

- `source.destination_id.external_code` (tc.guide / tc.address) se compara exclusivamente con `ruta.destino_id.codigo`.
- Sin guías staging, se consulta `transcash.guia.destino_codigo` (campo ERP histórico).
- Se normalizan espacios, guiones, puntos y caracteres invisibles; no se comparan nombres, IDs ni equivalencias.
- Sin código en el ERP, no se acepta la guía y se informa el bloqueo.
- En publicación, `transcash.guia.destino_codigo` conserva el código ERP sin reemplazarlo por el código del catálogo.
- El menú de equivalencias manuales se desactiva al actualizar. El modelo histórico permanece por compatibilidad de datos, pero ya no participa en la selección.
- El resto de filtros de chofer, transportista y disponibilidad se mantiene.

Validación sugerida: buscar una guía en la PWA. Comparar "código ERP guía" con "código de ruta". Ambos códigos deben coincidir normalizados. Después guardar y confirmar una ruta de prueba.
