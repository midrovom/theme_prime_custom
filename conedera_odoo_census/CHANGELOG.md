# Changelog

## 18.0.1.0.2

- Corrige el problema de esquema `UndefinedColumn` en `res_partner.census_visit_count`.
- `census_visit_count`, `census_quotation_count` y `census_last_visit_datetime` vuelven a ser métricas calculadas no almacenadas.
- La lista de clientes ya no ordena por un campo calculado; usa `write_date desc, id desc`.
- No requiere crear columnas SQL para las métricas del catastro.
- Conserva las correcciones GPS/OWL, auditoría y seguridad de 18.0.1.0.1.
- ZIP corregido con `conedera_odoo_census/` como carpeta raíz.

