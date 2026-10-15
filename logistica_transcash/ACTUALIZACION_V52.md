# Transcash V5.2 — Agregar guías a un embarque y bloqueo de viajes simultáneos

**Para Odoo 18; actualización compatible con Transcash V5.1.** Nombre técnico del addon: `logistica_transcash`. Versión del manifiesto: `18.0.5.2.0`.

## 1. Qué cambió

### Guías tardías

Después de crear un embarque, pueden entrar nuevas guías por la API del ERP de origen. Mientras el embarque esté en **Preparación**, el chofer podrá abrir **Mis embarques → Embarque actual** y usar el bloque **«Agregar guías a este embarque»**. Allí pulsa **«Actualizar lista de guías»** para ver las recién sincronizadas, marca una o varias y pulsa **«Agregar guías seleccionadas»**.

El sistema conserva las guías que ya están registradas, en carga o cargadas, junto con sus observaciones, roturas, fotos y videos. Las guías nuevas se incorporan en estado **Registrada**, listas para empezar la carga individualmente.

**Condiciones para agregar:**

1. El embarque está en **Preparación** (no se permiten nuevas guías cuando está Embarcado, En ruta o Entregado).
2. La cuenta que hace la acción es el **chofer** asignado al embarque y tiene habilitado el grupo Chofer WebApp.
3. Las guías están en estado **Registrada**, sin embarque anterior y asignadas exactamente a ese usuario chofer.
4. Deben pertenecer a la **misma compañía**, a la **misma empresa de transporte** y tener la **misma placa** (ignorando espacios exteriores y mayúsculas).
5. Límite operativo de esta versión: máximo **100 guías por embarque**.
6. Para añadir se necesita conexión; la evidencia por guía conserva la cola offline previa.

Una guía no puede pertenecer a dos embarques ni reiniciar una carga al agregarla.

### Solo un embarque activo por chofer

Se considera activo cualquier embarque con estado **Preparación**, **Embarcado** o **En ruta**. Un chofer solo puede tener uno en esos estados, **sin importar cuántas guías diferentes seleccione**. La condición se verifica en el servidor al crear, al modificar estados y al añadir guías.

Si existe uno activo, **Mis embarques** oculta el formulario de creación, presenta **«Ya tienes un embarque en curso»** y ofrece **«Continuar mi embarque»**. Incluso si se intenta crear otro desde otra pestaña, la solicitud es rechazada.

El bloqueo desaparece al terminar el embarque en estado **Entregado**, después de la entrega de todas sus guías; también deja de contar uno en estado Cancelado, si el personal autorizado gestiona ese caso. Marcar **Embarcado** o iniciar la ruta **no** libera el bloqueo.

**Protección frente a simultaneidad:** las operaciones del mismo conductor se serializan mediante un bloqueo transaccional `pg_advisory_xact_lock` de PostgreSQL. La incorporación de guías bloquea asimismo el embarque y las guías seleccionadas. La verificación no depende de botones ocultos en la interfaz.

## 2. Instalación / actualización en tu VPS

1. **Haz copia de seguridad comprobada de la base de datos, filestore y directorio del addon.** Prueba preferentemente sobre un clon de producción.
2. Descomprime `logistica_transcash_odoo18_v5_2_embarques_dinamicos.zip`. Reemplaza la carpeta **`logistica_transcash`** del directorio configurado en `addons_path` por el contenido del ZIP. No instales las dos versiones a la vez.
3. Reinicia tu servicio de Odoo. Por ejemplo, si se llama `odoo18`:
   ```bash
   sudo systemctl restart odoo18
   ```
   Si usas Docker u otro nombre de servicio, cambia el comando.
4. En el Odoo de prueba, habilita modo desarrollador, entra a **Aplicaciones**, actualiza lista de aplicaciones si es necesario y pulsa **Actualizar** para `Transcash - Seguimiento de Guías`. **No desinstales** el addon.
5. Entra como chofer en `/transcash/embarques`. Con el teléfono conectado, vuelve a abrir la PWA para que descargue los recursos de la versión nueva. **No borres los datos del navegador** mientras haya fotos o videos pendientes de sincronizar.

### Acceso y API

El chofer continúa usando el acceso web `https://TU-DOMINIO/transcash/embarques` con su usuario de Portal habilitado como chofer. La configuración de API permanece en **Logística Transcash → Configuración API / ERP**. No cambian los tokens ni los endpoints de V5.1. Si llega una guía nueva, debe estar correctamente sincronizada desde el ERP y tener `chofer_login`, empresa de transporte y placa compatibles con el embarque actual. Reabre la pantalla del embarque o usa **Actualizar lista** para visualizarla.

## 3. Casos de prueba recomendados

| Caso | Resultado esperado |
|---|---|
| Chofer A crea el embarque E1 con guía G1 | Se crea E1 en Preparación. |
| ERP importa G2 con chofer A, mismo proveedor y placa | G2 aparece en **Agregar guías**, tras actualizar la página. |
| Chofer agrega G2 a E1 | G2 queda vinculada a E1 y en Registrada; G1 conserva sus evidencias y estado. |
| Chofer intenta volver a agregar G2 | Se rechaza: ya está asignada a un embarque. |
| ERP importa G3 para chofer B | Chofer A no ve G3 entre sus opciones. |
| ERP importa G4 con placa o empresa diferente | No aparece entre las elegibles; el servidor también la rechaza si se envía manualmente. |
| Chofer intenta crear E2 cuando E1 está en Preparación | Se bloquea y se le dirige a E1. |
| Chofer intenta crear E2 cuando E1 está Embarcado o En ruta | Se bloquea igualmente. |
| Chofer abre dos pestañas y pulsa Crear simultáneamente | Solo una solicitud puede crear un embarque activo. |
| Chofer marca E1 como Embarcado | No puede seguir agregando guías a E1. |
| Se entregan todas las guías y E1 queda Entregado | El chofer puede crear otro embarque. |
| Cliente destinatario abre su portal | Solo ve sus propias guías; no recibe formulario para agregar guías al embarque. |

## 4. Validación del paquete y limitaciones

Se comprobaron la sintaxis de los archivos Python, XML, JS y la integridad del ZIP; se agregaron pruebas automatizadas en `tests/test_embarque.py` para ejecutar con `--test-enable` en una instalación real de Odoo 18.

**No se ha instalado ni ejecutado en el VPS del usuario ni en una instancia de Odoo 18 de este entorno.** Antes de producción se requiere validar permisos, flujo de estados, sincronización API y los escenarios de concurrencia mediante dos sesiones reales.

Si ya había **varios embarques activos históricos para el mismo chofer** antes de actualizar, la versión nueva bloqueará otros embarques hasta que el personal responsable cierre o regularice esos registros. No cambia automáticamente los estados históricos ni elimina datos.
