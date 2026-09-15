# Transcash Commissions - API Administrator Bridge

Addon independiente para conectar `transcash_commission` con la configuración existente `api.administrator` sin modificar ninguno de los dos módulos.

## Dependencias

- `transcash_commission`
- `api_administrator`
- Python `requests`

No depende de `transcash_commission_goal_rules`, por lo que puede actualizarse de forma independiente.

## Configuración esperada

En `api.administrator` debe existir **una sola** configuración activa por compañía con:

- Nombre: `comisiones_transcash_retail`
- Tipo: `get`
- Estado: `A` (si el modelo tiene campo `status`)
- URL / endpoint / User ID / Password configurados como en las demás APIs Transcash.

El endpoint puede contener el parámetro de empresa que ya utiliza la integración existente.

## Fechas

Las fechas del período se convierten a `AAAA.MM.DD` y se envían como segmentos con comillas simples:

```text
/'2026.08.01'/'2026.08.31'
```

Si la configuración es:

```text
https://servidor/api/ventas?empresa=01
```

la URL final será:

```text
https://servidor/api/ventas/'2026.08.01'/'2026.08.31'?empresa=01
```

Es decir, las fechas se colocan antes de los parámetros query ya configurados.

Si el orden del endpoint necesitara ser distinto, también se soportan los placeholders `{date_from}` y `{date_to}` en `url` o `end_point`; el bridge los reemplaza por las fechas entre comillas.

## Respuesta esperada

Principalmente:

```json
{
  "data": [
    {"Tipo": "FA", "Numero": "..."}
  ]
}
```

También se aceptan `result`, `rows` o una lista JSON directa por compatibilidad.

## Flujo

1. Desde el período de comisiones se ejecuta **Sincronizar ventas**.
2. `transcash_commission` crea `commission.sync` con las fechas del período.
3. Este bridge localiza `api.administrator` con nombre `comisiones_transcash_retail` para la compañía actual.
4. Construye la URL con las fechas del período.
5. Consume la API con los mismos headers de autenticación usados por las integraciones Transcash.
6. Devuelve `data` al importador estándar `commission.sale.import_rows()`.
7. El módulo base conserva toda su lógica de deduplicación y creación de maestros.

## Seguridad y mantenimiento

El bridge no copia credenciales a `commission.sync`; siempre las lee desde `api.administrator`. Tampoco modifica `stock.api.sync`, `api.administrator`, `transcash_commission` ni `transcash_commission_goal_rules`.


## Configuración exacta del endpoint de Transcash Retail

Para el endpoint confirmado:

```text
http://conexion.callphoneecuador.com:9280/appSymfony/web/app_dev.php/inventory_odoo/consulta_odoo/ventas_comisiones/2/'2026.08.01'/'2026.08.31'
```

la configuración recomendada en `api.administrator` es:

```text
Nombre: comisiones_transcash_retail
Tipo: get
URL: http://conexion.callphoneecuador.com:9280/appSymfony/web/app_dev.php
Endpoint: inventory_odoo/consulta_odoo/ventas_comisiones/2/
```

El `2` corresponde a la empresa y permanece configurado en el endpoint. El bridge toma las fechas del período de liquidación y agrega exactamente:

```text
'AAAA.MM.DD'/'AAAA.MM.DD'
```

Por ejemplo, para un período del 1 al 31 de agosto de 2026, la URL final es:

```text
http://conexion.callphoneecuador.com:9280/appSymfony/web/app_dev.php/inventory_odoo/consulta_odoo/ventas_comisiones/2/'2026.08.01'/'2026.08.31'
```

No es necesario incluir las fechas en `api.administrator`; cambian automáticamente con cada período.
