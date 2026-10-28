# Transcash Guías API v2.29 — destinos y dirección de entrega

## Objetivo
- En sincronización getguiaslogistica, actualizar automáticamente los campos
  `destino`, `destino_codigo`, `destino_ciudad`, `destino_id` y
  `direccion_destino_erp` de `transcash.guia` **solo si no tiene ruta ni embarque**
  y permanece registrada/sin aprobación.
- Guardar `ruta.direccion_destino` de manera independiente de
  `ruta.destino_codigo` (código ERP) y `ruta.destino_ciudad` (ciudad).
- Si el ERP no envía dirección en una sincronización parcial y el código ERP
  no cambia, conservar la dirección anterior. Si cambia el código y no llega
  una dirección nueva, no arrastrar la dirección del destino anterior.
- Para guías ya asignadas, no modificar la dirección existente; solo completar
  un valor vacío cuando el código ERP coincide con la ruta confirmada.
- `Actualizar destinos ERP` también completa la dirección en guías libres con
  datos ya disponibles en `tc.guide`, sin consultar el ERP.

## Contrato JSON
```json
{"ruta":{"destino_codigo":"NAJ","destino_ciudad":"NARCISA DE JESUS", "direccion_destino":"KM 16.5 VIA DAULE MZ 66 S 3"}}
```

| Modelo | Campo | Ejemplo |
| --- | --- | --- |
| `tc.guide` | `destination_code_erp` | NAJ |
| `tc.guide` | `destination_city` | NARCISA DE JESUS |
| `tc.guide` | `destination_address` | KM 16.5 VIA DAULE MZ 66 S 3 |
| `transcash.guia` | `destino` / `destino_codigo` | NAJ |
| `transcash.guia` | `destino_ciudad` | NARCISA DE JESUS |
| `transcash.guia` | `direccion_destino_erp` | KM 16.5 VIA DAULE MZ 66 S 3 |

`transcash.destino` continúa identificándose por código y compañía. No se
crea un destino nuevo por cada dirección; la dirección pertenece a la guía.

## Actualizar en Odoo 18
1. Realizar respaldo de la BD y carpeta `transcash_guias_api`.
2. Sustituir la carpeta por este paquete v2.29, reiniciar Odoo y **actualizar**
   el módulo (necesario para crear columna `direccion_destino_erp`).
3. Ejecutar `Actualizar destinos ERP` para reparar guías libres existentes.
4. Sincronizar `getguiaslogistica` desde API Administrator/PWA.
5. Verificar en `Guías para rutas y seguimiento` las columnas Código, Ciudad y
   Dirección de entrega. La PWA mantiene comparación por código ERP y no por dirección.

### Consulta técnica posterior a la actualización
```sql
SELECT id, name, destino, destino_codigo, destino_ciudad, direccion_destino_erp,
       hoja_ruta_id, embarque_id
  FROM transcash_guia
 WHERE external_id_erp IS NOT NULL
 ORDER BY id DESC LIMIT 30;
```

No cambia roles, liquidaciones, asignaciones de transporte ni procesos de entrega.
