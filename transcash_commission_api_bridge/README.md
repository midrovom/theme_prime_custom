# Transcash Commissions - API Administrator Bridge

Versión: **18.0.1.1.0**

Addon puente entre `transcash_commission` y `api_administrator` para consumir la API configurada como `comisiones_transcash_retail`.

## URL esperada

En `api.administrator` puede configurarse:

- URL: `http://conexion.callphoneecuador.com:9280/appSymfony/web/app_dev.php`
- Endpoint: `inventory_odoo/consulta_odoo/ventas_comisiones/2/`

Para un período 2026-08-01 a 2026-08-31 el bridge consulta:

`http://conexion.callphoneecuador.com:9280/appSymfony/web/app_dev.php/inventory_odoo/consulta_odoo/ventas_comisiones/2/'2026.08.01'/'2026.08.31'`

## Deduplicación idempotente

Desde 18.0.1.1.0, volver a sincronizar el mismo período no vuelve a crear las mismas ventas.

La clave de deduplicación:

- normaliza espacios y texto;
- normaliza fechas (`2026.08.01`, `2026-08-01`, etc.);
- normaliza números (`12`, `12.0`, `12.0000`);
- conserva ocurrencias cuando la API realmente devuelve dos líneas idénticas;
- realiza una búsqueda masiva de claves existentes en vez de consultar PostgreSQL fila por fila.

La primera sincronización después de actualizar también reconoce registros importados con la versión 1.0.x mediante su `raw_payload`. No elimina automáticamente duplicados históricos ya existentes; evita crear nuevos.

## Dependencias

- `transcash_commission`
- `api_administrator`
- Python `requests`

No modifica ninguno de esos módulos.
