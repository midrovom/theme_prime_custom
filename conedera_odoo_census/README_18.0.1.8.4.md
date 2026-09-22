# Conedera Catastro Comercial — Odoo 18 Community 18.0.1.8.4

## Cambios clave

- Selector móvil de Equipo comercial como lista simple; no abre dashboards/gráficos de `crm.team`.
- Nueva **Empresa del Catastro** (`census_company_id`) separada de `res.partner.company_id`.
- El contacto puede seguir compartido entre compañías; el Catastro pertenece a una empresa operativa concreta.
- Equipo, visitas, proformas, bitácora y reportes se validan por esa empresa.
- Los equipos habilitados para Catastro deben pertenecer a una empresa específica.
- La actualización migra catastros existentes de forma aditiva y conserva historial.

## Regla multiempresa

Un Catastro pertenece a una sola empresa operativa. El RUC/cédula sigue siendo único globalmente para evitar catastros duplicados. Si el mismo cliente debe ser gestionado por otra empresa, se debe definir un flujo de transferencia/compartición posterior, no duplicar el cliente.
