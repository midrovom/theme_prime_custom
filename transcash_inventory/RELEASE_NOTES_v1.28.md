# Inventario Inteligente 18.0.1.28.0 — Multiempresa

## Cambios
- Iframes vinculados a la compañía principal activa del selector de Odoo; se recargan ante cambio de empresa.
- Todas las rutas y peticiones AJAX de este módulo se validan contra la empresa autorizada; se rechazan iframes obsoletos.
- Reglas globales de snapshots, SQL facts, fotos, cargas y bitácora limitadas a **la compañía seleccionada** (no a todas las activadas).
- API Administrator continúa usando `call_api(endpoint, method='get', company_id=env.company.id)` y versiones vigentes separadas por empresa.
- API Key, activación y modelo OpenAI independientes por compañía.
- Se conserva una migración segura de configuración antigua únicamente si una sola compañía tiene snapshots. Si varias ya tienen datos, cada compañía requiere configurar su propia clave.
- Miniaturas vinculadas por empresa y SKU; URL de fotografía incluye el ID de empresa.
- Validación ORM automática para impedir relaciones de ventas/stock con productos de otras empresas.
- Sin cambios en cálculos ABC/XYZ, filtrado, fotos, consultas SQL, exportación, ni importación API.

## Prueba de aceptación imprescindible en Odoo real
1. Asignar usuario a las empresas A y B, activar A, importar API para A.
2. Cambiar a B y sincronizar datos B (con SKU idéntico pero stock y ventas diferentes).
3. Abrir dashboards en ambas y comprobar cifras, fotos, proveedores, bitácora y exportaciones distintas.
4. Cambiar de A a B con dashboard abierto: el iframe debe recargarse automáticamente y no conservar datos de A.
5. Intentar `company_id` de compañía no autorizada: HTTP 403. Probar `snapshot_id` y `request_id` de A desde B: denegado.
6. Configurar ChatGPT solo en A: B debe mostrarse sin configurar hasta guardar sus propios parámetros.
7. Comprobar Datos importados, fotos y API Administrator para cada compañía, sin mezcla.
8. No instalar en producción sin probar primero en copia de la base, el filestore y los permisos multiempresa.
