# v2.18 — Tarjetas compactas de hoja de ruta (PWA)

- Suprime completamente el bloque **Resultado de filtros para esta ruta**, tablas de diagnóstico, y el panel independiente **Guías del chofer seleccionado**.
- Suprime la tarjeta redundante **Guías disponibles según esta hoja de ruta**.
- Reutiliza el resumen original de la ruta: Chofer, Destino y Transportista. Cada tarjeta muestra su contador debajo del nombre.
- Chofer: guías vinculadas a ese conductor en la empresa, incluidas asignadas (consulta de chofer existente). La consulta de resumen puede estar limitada: se mostrará `Al menos` cuando proceda.
- Destino/Transportista: coincidencias individuales entre guías **libres** según la validación de la PWA; no implica que ambas coincidan a la vez. También se usa `Al menos` si se alcanzó el límite de exploración.
- Los totales de tarjetas no dependen del texto escrito en el buscador de guías.
- No cambia ningún filtro de backend, código ERP del destino, pertenencia a transportista, chofer, selección masiva o seguridad de Portal.
- No cambia `logistica_transcash`.
