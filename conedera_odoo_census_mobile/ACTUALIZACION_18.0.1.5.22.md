# Catastro PWA 18.0.1.5.22 — bodegas, stock por ubicación y Radis

- **Bodegas de cotización por usuario:** Catastro → Configuración → Bodegas para cotizar por usuario. Administrador asigna una fila por usuario/bodega. Usuarios sin asignación NO pueden cotizar hasta que se configuren permisos. Los administradores de sistema pueden trabajar con bodegas de la empresa activa.
- **Tienda:** tarjetas muestran existencias por ubicación interna en toda la empresa activa, exclusivamente informativas. Para guardar cotizaciones solo puede elegir bodegas asignadas.
- **Otros perfiles:** tarjetas muestran únicamente ubicaciones internas de bodegas asignadas. Tampoco se divulga el stock total de la compañía en el diagnóstico.
- **Radis:** todos los usuarios de la PWA con permisos efectivos de edición de cotizaciones pueden usar el botón Enviar a Radis para una proforma guardada, en estado borrador, de su ámbito y bodega autorizada. Ya no requiere el grupo especial del módulo stock_api_assing. El método Radis original y sus validaciones permanecen.
- **Advertencia:** la API Radis actual no envía descuentos por línea; se mantienen los bloqueos a proformas Loyalty con descuentos o líneas promocionales para evitar diferencias económicas.
- El stock mostrado es físico, no reservado. La autorización para cotizar exige empresa/bodega del usuario, aunque Tienda vea otras existencias.
- No se guardan detalles de ubicaciones en IndexedDB; solo se muestran con conexión a Odoo.

## Instalación
1. Haga copia de seguridad y sincronice los pendientes offline.
2. Reemplace `conedera_odoo_census_mobile` sin desinstalar.
3. Reinicie todos los procesos de Odoo y actualice el módulo `-u conedera_odoo_census_mobile` o desde Aplicaciones.
4. **Asigne bodegas a usuarios** desde el nuevo menú antes de iniciar cotizaciones.
5. Abra `/catastro/app?version=18.0.1.5.22`.

## Pruebas obligatorias en Odoo real
- Tienda con permiso solo Bodega A: cotiza en A y ve ubicación de B como consulta; se rechaza guardar en B.
- Comercial con permiso solo A: no recibe ni puede consultar ubicaciones de B.
- Comercial con permisos A y B: ambas seleccionables y sus ubicaciones visibles.
- Usuario sin asignación: no puede guardar proforma ni enviar a Radis.
- Radis desde perfil Tienda: se llama al método original, una sola vez, solo cuando Odoo confirma.
- Promociones y descuentos siguen bloqueados para Radis si el contrato externo no los admite.

**Validación real en servidor:** no realizada en este entorno.
