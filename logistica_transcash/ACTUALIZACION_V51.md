# Transcash V5.1 — Menú Odoo, carga autónoma y API configurable

## Novedades

1. Clic en **Logística Transcash** (menú raíz) abre el listado administrativo de guías en Odoo. El enlace **WebApp / acceso opcional** queda separado al final del menú; `/transcash/guias` y `/transcash/embarques` siguen disponibles para el chofer.
2. **Logística Transcash → Choferes y acceso móvil → [abrir chofer] → Carga autónoma**. Solo el **Administrador de Logística** puede marcar esta opción, por chofer. Por defecto está desactivada.
3. En la ficha de la guía del chofer hay botones grandes de **Iniciar carga**, **Foto/video**, **Reportar rotura** y **Terminar carga**. Solo aparecen si el estado y la asignación lo permiten.
4. **Logística Transcash → Configuración API / ERP** contiene parámetros de conexión, botones de prueba y sincronización y configuración del intervalo automático. Se requieren permisos de Administrador de Logística.

## Políticas de carga autónoma

- Si el permiso está apagado, la carga solo se cierra si hay evidencia de carga y **todas las evidencias han sido aprobadas por Bodega**.
- Si está encendido para el usuario chofer asignado, permite cerrar la guía con **al menos una foto o video de carga ya recibido por Odoo**, aunque la evidencia continúe pendiente. No permite cerrar si alguna evidencia de carga fue **objetada**.
- Se registra en la guía **Carga cerrada con permiso autónomo**, usuario y fecha. **No se inventa una aprobación de Bodega** y se conserva el estado original de cada evidencia.
- Las evidencias capturadas *offline* cuentan solo después de sincronizarse con el servidor.
- Una vez cargadas todas las guías el chofer puede marcar el embarque completo como **Embarcado**. **La salida a ruta todavía requiere aprobación de Bodega** en el embarque; es un control diferente.

## Configuración API

En **Logística Transcash → Configuración API / ERP**:

| Campo | Uso |
|---|---|
| URL HTTPS para consultar guías | GET del ERP que devuelve `{"guias":[...]}` o una lista de guías. |
| Token para consultar al ERP | Header `Authorization: Bearer` usado por Transcash en consultas salientes. |
| URL de recepción de guías | Endpoint de Transcash, generado automáticamente, `POST /api/transcash/v1/guias`. |
| Token para recibir guías desde ERP | Token que se envía desde el ERP en el POST a Transcash. Puede generarse desde la pantalla. |
| Sincronización automática activada | Activa o desactiva la tarea cron que consulta guías al ERP. |
| Frecuencia (minutos) | Intervalo de 5 a 1440 minutos, predeterminado 15. |
| URL para solicitar notas de crédito | Endpoint externo HTTPS, independiente del transporte. |
| URL de callback de notas de crédito | Endpoint `POST /api/transcash/v1/notas-credito/estado` para confirmar la emisión desde ERP. |

**Probar conexión:** ejecuta únicamente un GET de consulta y valida si la respuesta es JSON con una lista. No importa registros. **Guardar configuración:** almacena credenciales de integración y actualiza el cron. **Sincronizar guías ahora:** guarda y ejecuta la importación manual. El cron hace lo mismo automáticamente.

### POST desde ERP hacia Transcash

```bash
curl -X POST 'https://TU-ODOO/api/transcash/v1/guias' \
  -H 'Authorization: Bearer TU_TOKEN_ENTRANTE' \
  -H 'Content-Type: application/json' \
  -d @guias.json
```

Archivo `guias.json` de ejemplo con referencias ya registradas en Odoo (campo **Referencia interna** en Contactos):

```json
{
  "guias": [
    {
      "id_externo": "ERP-10001",
      "numero_guia": "G-10001",
      "tipo_documento": "Factura",
      "numero_documento": "001-002-000123456",
      "chofer_login": "chofer1@transporte.example",
      "ruc_chofer": "0999999999001",
      "empresa_transporte_codigo": "TRANS-001",
      "destinatario_codigo": "CLI-001",
      "placa": "GYE-1234",
      "direccion_origen": "Bodega Guayaquil",
      "direccion_destino": "Cliente Quito",
      "fecha_inicio_traslado": "2026-10-15T08:00:00-05:00",
      "fecha_fin_traslado": "2026-10-17T18:00:00-05:00",
      "productos": [
        {"id_linea":"L1","sku":"SKU-123","descripcion":"Porcelanato","unidad":"m2","cantidad":50,"peso_kg":775,"pallets":1,"cajas":20,"precio_unitario":12.5},
        {"id_linea":"L2","sku":"SKU-124","descripcion":"Accesorio","unidad":"unidad","cantidad":8,"peso_kg":13,"pallets":0,"cajas":2,"precio_unitario":10}
      ]
    }
  ]
}
```

**Reglas importantes:** el API identifica de forma idempotente por `id_externo` + compañía. Los contactos remitente/destinatario/transportista deben tener la referencia correcta en Odoo y el `chofer_login` debe corresponder a un usuario existente. No se actualizan estados locales, evidencias ni aprobaciones desde el ERP. Cantidades y unidades se sincronizan por `id_linea`; no se pueden modificar cantidades si existen roturas aprobadas o pendientes que dependen de ellas.

## Actualización en VPS desde V5.0

1. Crear respaldo comprobado de **base de datos + filestore + carpeta del addon**. Probar idealmente en un clon de producción.
2. Reemplazar solo la carpeta `logistica_transcash` con la incluida en V5.1, respetando la ruta del `addons_path`.
3. Reiniciar el servicio Odoo correspondiente (`systemctl` o contenedor Docker).
4. En Odoo, modo desarrollador → **Aplicaciones** → actualizar **Transcash - Seguimiento de Guías**. No desinstalar ni crear una base nueva.
5. Comprobar el menú Odoo, permisos de chofer, guía en carga, evidencia subida, cierre autónomo y configuración de API.
6. Abrir la WebApp con conexión una vez para que actualice recursos del Service Worker. Si hay evidencias pendientes en el teléfono **no borres el caché ni los datos locales**, sincroniza primero.

La revisión incluida cubre sintaxis Python/JS, XML, referencias y pruebas Odoo automatizadas adjuntas. **No se ha validado el funcionamiento real en tu VPS/Odoo**; desplegar primero en pruebas.
