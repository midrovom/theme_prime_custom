# Integración de Inventario Inteligente con API Administrator (Odoo 18)

Este módulo **no configura URLs, usuarios, contraseñas ni tokens**. Esos valores se
mantienen exclusivamente en el módulo existente `api.administrator`.

Contrato de invocación que ya utiliza Logística Transcash:

```python
env['api.administrator'].call_api('getproductosinvt', method='get', company_id=env.company.id)
```

La misma llamada se realiza con los cuatro nombres indicados abajo. Si la firma
real de `call_api` difiere, se debe adaptar `services/api_import.py` después de
inspeccionar el código de API Administrator de **esta instalación**.

## Endpoints necesarios

| Nombre en API Administrator | Función | Granularidad esperada |
|---|---|---|
| `getproductosinvt` | Catálogo maestro | Una fila por SKU |
| `getventasinvt` | Ventas netas y costo de ventas | Una fila por SKU/mes o más detalle (se consolida) |
| `getcomprasinvt` | Compras y proveedor real | Una fila por SKU/mes/proveedor o más detalle |
| `getstockinvt` | Existencia física por ubicación | Una fila por SKU/bodega |

Respuestas válidas: arreglo de objetos JSON, o envoltura `{"data": [...]}`,
`{"result":{"rows":[...]}}` o `{"items":[...]}`.

**Los nombres sugeridos a continuación representan el contrato que el adaptador
acepta**. No se afirma que los endpoints existentes ya devuelvan esos campos.
Se debe comparar con una muestra real de respuesta de los cuatro endpoints.

### GET getproductosinvt

```json
{
  "data": [
    {"sku":"CERFIORMED","name":"CERAMICA FIORANNO MEDEL (45*45) 2.00 M2",
     "category":"CERAMICA","brand":"CECAFI","format":"45*45",
     "supplier":"CERAMICA CARMELO FIOR LTDA", "cost":8.00,"price":11.00}
  ]
}
```

Campos mínimos: `sku`, `name`; recomendados: `category`, `brand`, `format`,
`supplier`, `cost`, `price`. Código único por empresa. `format` se conserva sin
inferir. Si faltan costo y precio el módulo los registra como cero, con la
limitación financiera correspondiente.

### GET getventasinvt

```json
{"data":[{"sku":"CERFIORMED","periodo":"2026-09",
           "quantity":13,"net_sales":140,"cogs":100}]}
```

Campos obligatorios: SKU, año/mes (o fecha YYYY-MM), cantidad vendida, venta
**neta** y **costo de ventas**. Los importes deben tener el mismo tratamiento
de descuentos, devoluciones e IVA que en el Excel original.

### GET getcomprasinvt

```json
{"data":[{"sku":"CERFIORMED","periodo":"2026-09",
           "quantity":10,"purchase_total":80,"supplier":"PROVEEDOR REAL"}]}
```

Campos obligatorios: SKU, período, cantidad y monto total de compra (o costo
unitario). `supplier` es el proveedor **real del movimiento**, distinto del
proveedor habitual del catálogo.

### GET getstockinvt

```json
{"data":[{"sku":"CERFIORMED","warehouse":"BODEGA PRINCIPAL",
           "on_hand":4}]}
```

Campos obligatorios: SKU y stock; recomendado: bodega. No enviar stock en
cajas si ventas están en m² sin identificar la unidad y conversión. Para un
stock real a fecha de corte, el endpoint debe devolver el estado completo del
inventario, no únicamente movimientos recientes.

## Sincronización manual inicial

1. Configurar y validar las cuatro definiciones GET en **API Administrator** para
   la empresa correcta (URL, credenciales y endpoint real allí).
2. Actualizar `transcash_inventory`, abrir **Inventario Inteligente → Sincronización API**
   con usuario Administrador Odoo.
3. Indicar opcionalmente `Mes de corte` en formato `YYYY-MM` y pulsar
   **Sincronizar desde API Administrator**.
4. Solo si se reciben y validan los cuatro conjuntos se crea una nueva versión;
   se generan de inmediato las tablas relacionales Odoo para el motor SQL seguro.
5. Verificar los totales del Dashboard con los totales informados por el ERP.

Los datos antiguos continúan disponibles en Historial de cargas. Las consultas
ChatGPT y las exportaciones Excel leen la versión activa en Odoo. No se llama
al ERP externo durante cada pregunta: solo durante la sincronización.

### Limitaciones de esta versión

- La invocación y los cálculos están implementados, pero **no se han probado
  con una conexión real a API Administrator en el servidor del usuario**.
- Sin conocer el código concreto de `call_api` ni el JSON de sus cuatro nuevas
  rutas, puede necesitarse ajustar los alias de campos o el envoltorio HTTP.
- Esta versión sincroniza manualmente en una transacción; para cargas de gran
  volumen o tiempos altos deberá agregarse una tarea de Odoo que procese lotes,
  paginación e idempotencia, de acuerdo con las capacidades reales del API.
- No se modifican el ERP origen, sus credenciales ni la configuración de API
  Administrator desde este módulo.
