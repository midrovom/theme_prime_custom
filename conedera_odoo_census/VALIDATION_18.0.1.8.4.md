# Validación estática — 18.0.1.8.4

Checks OK: 12
Errores: 0

## OK
- Manifest 18.0.1.8.4 and all data/assets paths
- 48 Python files compile
- 20 XML files parse; 127 explicit IDs unique
- census_company_id field exists
- census team does not use check_company
- company/team constraint exists
- mobile team uses selection widget
- visit inherits census company
- quote validates census company
- partner rules filter census company
- lookup activates census company
- 1.8.4 migration is additive / non-destructive by static token check

## Alcance
- Validación estática de sintaxis, XML, manifiesto, rutas, migración y coherencia multiempresa.
- No sustituye una instalación/upgrade real en Odoo 18 + PostgreSQL.