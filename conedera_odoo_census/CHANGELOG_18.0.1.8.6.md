# Cambios 18.0.1.8.6

## Correcciones de interfaz móvil
- Se eliminó la duplicación visual de **Empresa del Catastro**. La ficha ahora contiene una sola instancia de Vendedor, Empresa y Equipo comercial.
- Se conserva la arquitectura multiempresa introducida en 1.8.4: `census_company_id` sigue siendo la empresa operativa del Catastro y no se modifica `res.partner.company_id`.
- El selector de Equipo comercial continúa como lista simple y sigue filtrado por Empresa del Catastro y vendedor.

## Horario de atención
- Se añadió `opening_hours_summary_html`, un resumen visual calculado a partir de las líneas de horario existentes.
- En móvil, al guardar/proteger, ya no se depende de la representación readonly del One2many que podía mostrar solo el contador (por ejemplo `1`).
- El horario se muestra por día y franja (`09:00 – 13:00`, `14:00 – 18:00`).
- Las líneas originales de `conedera.partner.opening.hour` se conservan sin migración ni transformación.
- Cuando la ficha está editable, el editor estructurado Día/Desde/Hasta permanece disponible debajo del resumen.

## Protección de datos
- La actualización no elimina ni transforma catastros, visitas, horarios, fotografías, relaciones de negocio/marcas ni proformas.
- Se añadió Data Guard 18.0.1.8.6 para abortar el upgrade si disminuye alguno de los conjuntos históricos protegidos.
