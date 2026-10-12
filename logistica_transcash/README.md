# Logística Transcash — Odoo 18

Módulo **MVP de integración y seguimiento de guías**. Interfaz de backoffice, portal móvil autenticado, integración ERP de entrada y consulta periódica, bitácora, evidencias fotográficas, validación de bodega/destinatario, objeciones, incidencias, y creación de borrador de factura del proveedor de transporte.

> Estado del paquete: código fuente estáticamente validado (Python y XML); **no se ha instalado ni ejecutado en una instancia real de Odoo 18**. Se requiere prueba funcional e integración antes de usar en producción.

## Instalación

1. Instalar Odoo **18.0**, con módulos base, web, website, portal, mail y account disponibles. Funciona como addon personalizado; requiere despliegue que permita módulos propios (Odoo.sh o servidor propio, no Odoo Online estándar).
2. Copiar la carpeta `logistica_transcash` al directorio `custom_addons` y agregar esa ruta en `addons_path`.
3. Reiniciar servicio Odoo, activar modo desarrollador, actualizar la lista de aplicaciones e instalar **Transcash - Seguimiento de Guias**.
4. Dar grupo **Administrador de logística** al personal de operaciones/contabilidad y **Responsable de bodega** al responsable de despacho. Asignar `bodega_usuario_id` en las guías.
5. Crear usuarios **portal** para cada chofer y destinatario, con credenciales individuales, y asignar chofer en `chofer_usuario_id` y destinatario en `destinatario_id`.
6. Registrar previamente clientes, transportistas y proveedores en **Contactos**, con un identificador externo único en el campo **Referencia interna (`res.partner.ref`)**.
7. Configurar URL y tokens en **Ajustes → Logística Transcash**. Requiere URL saliente HTTPS y publicar el Odoo con HTTPS para la API entrante. Ejecutar **Logística Transcash → Sincronizar ERP** o dejar correr el cron cada 15 minutos.
8. Abrir `https://<servidor-odoo>/transcash/guias` desde el móvil del chofer/destinatario luego de ingresar con su usuario.
9. Configurar la **Cuenta de gasto** en cada guía antes de generar la factura de transporte. Antes de producción revisar normativa fiscal, impuestos y cuenta por pagar apropiados para la empresa.

## Circuito operativo

| Estado de la guía | Actor y acción | Precondición |
|---|---|---|
| Registrada | ERP importa la guía; bodega inicia embarque | Guía existente; bodega asignada |
| En embarque | Chofer agrega 1+ fotos; bodega aprueba u objeta | Chofer asignado |
| En ruta | Bodega autoriza salida | Todas las fotos de carga aprobadas |
| En destino | Chofer confirma llegada | Guía previamente en ruta |
| Pendiente de recepción | Chofer sube evidencia de llegada; destinatario acepta/objeta | Arribo registrado |
| Entregada | Destinatario registra receptor y confirma | Todas las evidencias de llegada revisadas; admite entrega con observaciones |
| Lista para pago | Administrador autoriza liquidación | Sin incidencias abiertas y proveedor asignado |
| Factura proveedor creada | Administrador crea borrador de `account.move` (`in_invoice`) | Tarifa > 0; cuenta gasto; compañía y moneda válidas |
| Pagada | Administrador comprueba pago contabilizado | `account.move.payment_state == 'paid'` |

**Incidencias:** una rotura, faltante, otra novedad, o objeción abre incidencia. La entrega física puede cerrarse con incidencias abiertas, pero **no** se puede autorizar el pago hasta que administración documente resolución. La respuesta del chofer no borra la objeción anterior. Historial técnico en sección `Historial` de la guía.

## API ERP

### 1) ERP → Odoo: PUSH

`POST /api/transcash/v1/guias`

- Header: `Authorization: Bearer <token_entrante>`
- Header: `Content-Type: application/json`
- Respuesta `200` exitosa, `207` con errores por fila (procesamiento parcial), `401` no autorizado, `400` payload incorrecto.
- Límite de lote: 500 guías; máximo de body: 2 MB.
- Identificador: combinación de compañía Odoo activa e `id_externo`; se actualizan registros existentes sin duplicar.

```json
{
  "guias": [
    {
      "id_externo": "ERP-12578",
      "numero_guia": "G-2026-012578",
      "estado_erp": "despachada",
      "origen": "Bodega Quito",
      "destino": "Centro de distribución Guayaquil",
      "remitente_codigo": "REMIT-001",
      "destinatario_codigo": "CLI-002",
      "chofer_login": "chofer.001@empresa.com",
      "transportista_codigo": "OPER-003",
      "proveedor_codigo": "PROV-008",
      "placa": "ABC-1234",
      "bultos": 50,
      "peso_kg": 750.5,
      "descripcion_carga": "Mercancía paletizada",
      "fecha_prevista": "2026-10-14T17:00:00-05:00",
      "valor_acordado": 285.00
    }
  ]
}
```

**IMPORTANTE:** `remitente_codigo`, `destinatario_codigo`, `transportista_codigo` y `proveedor_codigo` se resuelven por `res.partner.ref`; `chofer_login` por `res.users.login`. El módulo **no crea contactos ni usuarios automáticamente**. Si no existen, esa fila da error sin afectar las demás. La moneda se hereda de la compañía; el MVP no admite facturar moneda distinta a la moneda contable de la compañía.

### 2) Odoo → ERP: PULL

- `GET <URL configurada en Ajustes>`, header `Authorization: Bearer <token_saliente>`.
- Responde el mismo JSON de arriba, o una lista plana de guías.
- Se invoca mediante menú **Sincronizar ERP**, o cron cada 15 minutos (por defecto), modificable en `Ajustes → Técnico → Acciones planificadas`.
- URL saliente exige HTTPS, certificado verificado, timeout 25 segundos, 5 MB máximo de respuesta, hasta 500 guías por invocación. **No implementa paginación** en esta primera versión; implementar cursores/lotes si se esperan más de 500 cambios por ciclo.
- Una actualización del ERP no cambia el estado operativo validado por Odoo, ni borra evidencias o resoluciones. Después de generar factura, no modifica proveedor ni tarifa de transporte.

### 3) Diferenciar fuentes de verdad

- ERP origen: número de guía, carga, ruta, destinatario, chofer, transportista, proveedor, valor acordado y llegada prevista.
- Odoo: estados operativos, autorizaciones, archivos, objeciones, incidencia, firma/aceptación electrónica en portal, liquidación y factura del proveedor.
- Si se requiere reportar estados a ERP, implementar **webhook de salida** o endpoint de consulta autenticado; *no incluido en MVP*.

## Acceso y seguridad

- **Administrador:** backoffice, guías, incidencias y liquidación.
- **Bodega:** backoffice de todas las guías, permisos de sólo lectura a nivel ORM y botones protegidos para iniciar embarque, validar evidencia de carga y autorizar salida de guías de su despacho.
- **Chofer:** usuario portal autenticado, limitado a guías en que `chofer_usuario_id = usuario actual`; puede subir carga, novedades, llegada y responder objeción.
- **Destinatario:** portal autenticado asociado al socio comercial del contacto, limitado a guías de su compañía; puede subir evidencia, aceptar/objetar llegada y confirmar recepción.
- Los usuarios portal **no** reciben permisos generales de acceso a los modelos. Las rutas validan el acceso cada vez y sólo luego usan `sudo()`.
- Adjuntos permitidos: JPG/PNG/WEBP/PDF, máximo 10 MB, sin SVG ni archivos arbitrarios; descarga a través de una ruta que revalida el acceso.
- Las peticiones web de formularios tienen CSRF. El endpoint M2M no usa CSRF (token Bearer obligatorio con comparación temporal constante); se debe proteger con HTTPS, rate limiting en proxy, rotación de tokens y registros de acceso.

## Límites / fase siguiente

1. **Pruebas reales:** instalar en un Odoo 18 con datos de prueba, probar permisos, fiscalidad, flujos de bodega, chofer y receptor y corregir particularidades de localización.
2. **Firma electrónica de recepción**, DNI/cédula, geolocalización verificada, sello de hora de servidor y evidencia de precintos antes/después.
3. **Notificaciones y SLA**, recordatorios, alertas ETA y escalamiento de objeciones.
4. **Repartos parciales**, multi-parada, transbordos, sustitución de chofer/vehículo, multi-guía por viaje, entregas fallidas y devoluciones.
5. **Flujo formal de reclamos:** informe de daños, costo de reclamo, aseguradora, responsable económico, indemnización y resolución documentada.
6. **Integración financiera real** con facturas electrónicas del proveedor, impuestos, retenciones, conciliación y pagos agrupados; la factura actual es un **borrador**, no un pago ni un comprobante fiscal válido automáticamente.
7. **Escalabilidad:** procesamiento asíncrono de API, paginación, reintentos, cola de errores, hashes de adjuntos, cuotas/retención de archivos, privacidad y auditoría de integraciones.
8. **Múltiples compañías:** asignar compañía de cada guía desde ERP y aislar datos por empresa en portal/operaciones, con pruebas multiempresa.
9. **PWA con sincronización sin conexión** para conductores en zonas sin cobertura. La versión actual requiere conexión durante el envío.

