# Actualización a 18.0.1.8.4

1. Haga backup de base y filestore. No desinstale el módulo.
2. Detenga Odoo, reemplace la carpeta y ejecute `-u conedera_odoo_census --stop-after-init --no-http`.
3. Inicie Odoo y configure cada Equipo comercial con una empresa específica.
4. En Catastro, `Empresa del Catastro` es la empresa operativa; `res.partner.company_id` puede seguir vacío/compartido.
5. En móvil, Equipo comercial debe mostrarse como selector simple y no abrir tarjetas/gráficos.
