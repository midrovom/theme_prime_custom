# Logística Transcash V5.0 — Manual de actualización y operación

**Compatible previsto:** Odoo 18 en VPS, addon `logistica_transcash`, versión `18.0.5.0.0`.

**Estado:** código actualizado; pasa revisión estática de Python/JavaScript/XML. No se ha ejecutado en una instancia Odoo 18 de este entorno. Antes de producción debe probarse en una **copia de la base de datos y del filestore**.

## Novedad principal

Dos entidades diferentes: **Embarque** (`transcash.embarque`) y **Guía** (`transcash.guia`). El embarque agrupa guías de un mismo chofer, empresa de transporte y placa y administra **una tarifa, una factura de proveedor y un pago**. Cada guía tiene su propio documento comercial, destinatario, productos, carga, evidencia, roturas, recepción y notas de crédito.

## Instalación en el VPS

1. Respaldar **base de datos, filestore y carpeta del addon**. Sincronizar primero las evidencias offline pendientes en teléfonos que usen la V4.2; no borrar los datos locales del navegador.
2. Descomprimir `logistica_transcash_odoo18_v5_embarques.zip` y copiar su carpeta **`logistica_transcash/`** encima de la carpeta del addon instalado. No cambiar el identificador técnico.
3. Confirmar que `/ruta/custom-addons` (la carpeta contenedora) aparece en `addons_path` del archivo de configuración de Odoo.
4. Reiniciar el servicio (`sudo systemctl restart odoo18`, **solo si ese es su nombre real**).
5. Odoo → activar modo desarrollador → **Aplicaciones** → actualizar lista si procede → módulo **Transcash - Seguimiento de Guías** → **Actualizar**. No desinstalar.
6. Abrir `https://TU-DOMINIO/transcash/embarques` con el **usuario chofer Portal**. Para consultar las guías, `https://TU-DOMINIO/transcash/guias`.
7. En backoffice: **Logística Transcash → Embarques / viajes**. Contabilidad: **Logística Transcash → Liquidación por embarque**.

Para actualizar por línea de comandos con el binario de Odoo de tu instalación, ejemplo genérico: `odoo-bin -c /etc/odoo18.conf -d BASE_DE_DATOS -u logistica_transcash --stop-after-init`. Debe adaptarse a las rutas, usuario Linux, servicio y configuración reales del VPS; no ejecutar simultáneamente dos procesos que actualicen la misma base.

## Flujo operativo de la nueva V5

1. El ERP sincroniza las guías y sus productos. Deben tener **chofer (usuario Portal habilitado)**, empresa de transporte y placa.
2. El chofer llega a bodega y abre `/transcash/embarques`. Selecciona sus guías **Registradas y sin embarque**, que tengan la **misma empresa de transporte, placa y compañía**. Pulsa **Crear embarque**. La creación necesita Internet.
3. Abre el embarque y pulsa **Iniciar carga de esta guía** individualmente. Registra observación de inicio.
4. Abre la guía correspondiente y sube **fotos/videos de carga** (si no hay señal se conservan pendientes en la cola offline de la guía); la evidencia debe confirmarse en Odoo.
5. El usuario de **Bodega** aprueba todas las evidencias de carga de cada guía desde Odoo y resuelve objeciones.
6. El chofer pulsa **Terminar carga** en cada guía. Tras terminar todas, pulsa **Marcar embarque completo**. Estado de embarque: **Embarcado**.
7. **Bodega**, desde el formulario del embarque en Odoo, pulsa **Autorizar salida de todas las guías**. Embarque y sus guías pasan **En ruta**.
8. El chofer llega a cada cliente y registra la llegada y las evidencias de descarga desde la guía. Cada destinatario confirma exclusivamente su guía y registra objeciones/roturas si corresponde.
9. El embarque cambia a **Entregado** automáticamente cuando **todas** sus guías estén entregadas (no cuando llega al primer destino).
10. Administración de Ventas revisa las roturas por producto; Aprobación valida la propuesta de nota de crédito y Crédito y Cobranzas adjunta el comprobante emitido en el ERP, conforme a V4.2.
11. **Contabilidad** configura la **tarifa total** y la cuenta de gasto en el embarque. Con todas las guías aprobadas, incidentes resueltos y notas de crédito confirmadas, autoriza liquidación y crea **una factura proveedor para todo el embarque**. Cuando está pagada, marca pago verificado.

### Estados diferenciados

**Embarque (operación):** `Preparación → Embarcado → En ruta → Entregado`.

**Guía (operación):** `Registrada → En carga → Cargada → En ruta → En destino → Pendiente de recepción → Entregada`. Estados de liquidación antiguos de una guía **sin embarque** se conservan por compatibilidad.

**Embarque (finanzas, independiente):** `No liquidado → Autorizado → Facturado → Pagado`.

## Roles y privacidad

| Perfil | Embarque | Guía |
|---|---|---|
| Chofer Portal habilitado | Crea y gestiona **los suyos**, sin costo | Inicia carga, agrega evidencias, finaliza carga, llega y reporta daños |
| Empresa transportista Portal (nuevo grupo) | Consulta solamente embarques de su empresa, sin importes | Consulta guías vinculadas, sin poder modificar |
| Destinatario Portal | **Sin acceso al embarque** ni al conjunto de guías | Solo sus guías y acciones de recepción |
| Vendedor | Consulta de embarques de su compañía, sin importes | Revisa evidencias y reporta roturas |
| Bodega | Consulta viajes y autoriza salida | Aprueba evidencia de carga |
| Contabilidad | Costo, cuenta, factura de proveedor y pago | Consulta, sin editar operación |
| Ventas admin / Crédito y cobranzas | Consulta de viajes, sin costo | Roles de nota de crédito conservados |

La empresa transportista necesita una cuenta Portal cuyo contacto pertenezca a la empresa (`res.partner.commercial_partner_id`), y además el grupo **Empresa transportista: consulta de embarques (Portal)**. Este rol es **solo lectura**. El acceso se valida también en los controladores, no solo al ocultar botones. Nunca asignar este grupo a un destinatario si no debe consultar operaciones de transporte.

## Datos de la API

El endpoint entrante no cambia: `POST /api/transcash/v1/guias`. Token Bearer configurado como en V4.2. Ejemplo de payload:

```json
{
  "guias": [
    {
      "id_externo": "ERP-G-9001",
      "numero_guia": "G-9001",
      "tipo_documento": "Factura",
      "numero_documento": "001-001-000459874",
      "chofer_login": "chofer@example.com",
      "ruc_chofer": "0912345678001",
      "empresa_transporte_codigo": "TR-001",
      "fecha_inicio_traslado": "2026-10-16T08:00:00-05:00",
      "fecha_fin_traslado": "2026-10-16T18:00:00-05:00",
      "placa": "GYE-1234",
      "direccion_origen": "Bodega central, Guayaquil",
      "direccion_destino": "Av. Principal 100, Cuenca",
      "destinatario_codigo": "CLI-001",
      "productos": [
        {
          "id_linea": "1",
          "sku": "CER-60X60",
          "descripcion": "Porcelanato gris",
          "cantidad": 120.5,
          "unidad": "m2",
          "peso_kg": 2160.0,
          "pallets": 2.5,
          "cajas": 68,
          "precio_unitario": 12.75
        },
        {
          "id_linea": "2",
          "sku": "ACC-100",
          "descripcion": "Accesorio",
          "cantidad": 10,
          "unidad": "unidad",
          "peso_kg": 8,
          "pallets": 0,
          "cajas": 1
        }
      ]
    }
  ]
}
```

**Antes de importar:** crear los contactos ERP en Odoo con `res.partner.ref` correspondiente a `empresa_transporte_codigo` y `destinatario_codigo`; crear y habilitar el usuario chofer con su `login`. Para altas el ERP **debe aportar `id_externo`, `numero_guia`, detalle con `id_linea` y SKU/descripción**, y los códigos de relaciones existentes.

**Unidades de cantidad:** `m2`, `metro` (metros lineales), `unidad`; se conservan `kg`, `pallet`, `caja` por compatibilidad con V4.2. **`peso_kg`, `pallets`, `cajas` por línea son campos informativos**, no se suman a cantidad ni se convierten otra vez. Las roturas usan la **unidad de cantidad del propio producto**.

**Fechas:** son instantes ISO 8601 con zona horaria explícita para evitar desajustes. Las fechas reales de salida/entrega se guardan separadas por el módulo. `tipo_documento_transporte`, `numero_documento_transporte`, `placa_vehiculo`, `identificacion_chofer` se admiten como alias. Para la línea del producto también se admite `codigo` como alias del campo `sku`.

**Idempotencia:** las guías se identifican por `(id_externo, company_id)`, las líneas por `(guia_id, id_linea)`; la sincronización ERP no cambia los estados locales ni puede reasignar silenciosamente chofer, proveedor o placa después de asociar una guía a un embarque. Las incidencias se atienden manualmente. Las conversiones y las cantidades no deben recalcularse en Odoo.

## Consideraciones de versiones anteriores

- **No migrar automáticamente** las guías de V4.2 que ya estaban en carga, ruta, recepción o liquidación a nuevos embarques. Conservan su proceso anterior para no alterar evidencia ni pagos.
- Las guías **registradas y sin embarque** sí se pueden agrupar en nuevos embarques.
- La tarifa antigua por guía no se borra ni se suma automáticamente. El nuevo costo es **por embarque**, registrado desde Contabilidad, separado de cualquier importe histórico.
- La WebApp sigue permitiendo evidencias offline de las guías y subidas reanudables de videos de V4.2. **Crear un embarque, terminar carga y cambiar estados requiere conexión y confirmación del servidor**.
- El módulo mantiene el mismo nombre técnico `logistica_transcash` y las tablas preexistentes; no desinstalar ni borrar registros.

## Lista de pruebas obligatorias antes de producción

- Instalar V5 sobre copia de V4.2 con al menos una guía vieja y comprobar que sigue visible y que no cambia su factura.
- Importar una guía nueva con documento, transportista, chofer, placa y producto; comprobar todos los campos.
- Chofer crea embarque con dos guías; comprobar que no puede repetir una guía ni agrupar empresa/placa distinta.
- Iniciar una guía, intentar finalizar **sin** aprobación de bodega (debe bloquear); aprobar evidencia y finalizar.
- Intentar marcar embarque como Embarcado sin todas las guías cargadas (debe bloquear).
- Bodega autoriza salida del embarque completo; ambas guías entran a ruta.
- Entregar solo una guía: embarque permanece En ruta. Entregar la segunda: pasa a Entregado.
- Cliente A no puede abrir ni consultar la guía del cliente B ni `/transcash/embarques`.
- Transportista A ve solo embarques de su empresa y no edita evidencia ni tarifas.
- Contabilidad intenta liquidar con una rotura pendiente (se bloquea); tras las aprobaciones procede a una factura por viaje.
- Capturar evidencia sin señal, reconectar y confirmar que se guarda una sola vez.
- Ejecutar tests de Odoo con `--test-enable` en una base de prueba y revisar logs: `logistica_transcash/tests/test_embarque.py`.

**Advertencia:** en este entorno no tengo la instalación de Odoo ni conexión a tu VPS; validé la sintaxis, los archivos XML, rutas y referencias, no la ejecución real.
