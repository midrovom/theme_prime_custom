# 18.0.1.8.4

- Selector móvil de Equipo comercial cambiado a lista simple (`widget=selection`), sin abrir kanban/gráficos de `crm.team`.
- Nueva `Empresa del Catastro` (`census_company_id`) independiente de `res.partner.company_id`.
- Todo Catastro queda ligado a una empresa operativa; equipo, visitas y proformas deben usar la misma empresa.
- Los equipos habilitados para Catastro deben tener empresa específica.
- Migración no destructiva que asigna empresa a catastros existentes y limpia equipos incompatibles sin borrar historial.
- Dominios de seguridad reforzados por empresa permitida.
