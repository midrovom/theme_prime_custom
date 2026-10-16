# Logística Transcash V5.9 — Hojas de ruta, videos, aceptación y tarifario

## Objetivo

Actualización incremental del addon `logistica_transcash` para Odoo 18. Se conservan las guías recibidas por la API `/api/transcash/v1/guias`, sus productos, historial, incidencias, roturas, notas de crédito, liquidaciones, pagos y analítica. **No se conecta con `account.move` ni crea pagos en Contabilidad nativa de Odoo.**

## Flujo y actores

1. **Operador de Logística:** entra a **Logística Transcash → Tarifario por destino y vehículo**. Registra una tarifa activa para cada combinación de compañía, vehículo (`mula`, `camion`, `camioneta`, `furgon` u `otro`) y `destino_codigo`. El valor es referencial en moneda de la compañía; debe ser positivo.
2. **Operador de Logística:** abre **Hojas de ruta → Nuevo**; elige chofer, empresa de transporte, placa, tipo de vehículo, destino y guías con ese destino. Guarda y pulsa **Confirmar ruta**. Se inmoviliza la asignación de guías. Una guía no puede pertenecer a dos rutas.
3. **Operador de Logística:** abre **Armar embarque desde rutas**, escoge una o varias hojas de ruta del mismo chofer, transportista, vehículo/placa y compañía. Obtiene un EMB. Su costo inicial sugerido es la suma del tarifario de las rutas. Para añadir una nueva hoja antes de salir utiliza **Embarques / viajes → Agregar hojas de ruta**. Para cerrar la preparación, en cada hoja adjunta el **video de carga**, guarda y pulsa **Validar video** (MP4, WebM o MOV; máximo 75 MB por video). Cada ruta requiere video, no solo el embarque general.
4. **Operador de Logística:** desde el embarque pulsa **Liberar carga para aceptación**. No se permite liberar sin rutas y videos validados.
5. **Chofer:** entra a `/transcash/embarques`, abre su embarque, revisa los videos de cada ruta y pulsa **Aceptar carga e iniciar traslado**. Se registra el responsable y la fecha. Si detecta diferencia, utiliza **Encontré una diferencia en la carga**; Logística puede devolver el embarque a preparación y revalidar las evidencias. El chofer **no puede crear embarques, cambiar rutas ni subir evidencia de carga**, incluso mediante las rutas antiguas.
6. **Chofer en destino:** entra a cada guía, pulsa **Llegué al destino**, toma foto/video de descarga, introduce obligatoriamente el nombre completo de quien recibe, obtiene su firma en pantalla y pulsa **Terminar entrega y continuar**. La foto/video debe haber sido recibida por Odoo para cerrar. La firma es necesaria para **las guías bajo el nuevo modelo de hojas de ruta**. La recepción del cliente se confirma o se objeta con posterioridad sin detener al chofer.
7. **Cliente:** conserva su portal limitado a sus guías; puede revisar estados, comentar y reportar daños de su recepción, pero no modificar rutas/embarques. Por privacidad, un video de ruta compartido entre varias guías no se publica automáticamente al cliente: podría revelar guías ajenas.
8. **Jefe de Logística:** revisa el flete y puede ajustar el valor negociado desde el embarque antes de aprobarlo. El tarifario queda registrado como referencia de cada ruta. Las liquidaciones existentes siguen siendo por embarque y el proveedor conserva su acceso a consulta de viajes/pagos.

## Perfiles

- `Operador Logística: planificar rutas y registrar carga`: usuario interno; crea hojas de ruta y embarques, graba evidencias y libera carga.
- `Administrador de logística`: hereda el perfil anterior, administra tarifas y fletes.
- `Chofer - WebApp móvil`: usuario Portal, visualiza **solo sus embarques** y acepta carga, registra llegada y entrega.
- Destinatario, Transportista, Ventas, Crédito y Cobranzas, Contabilidad y Analítica: permanecen con sus permisos actuales.

**Importante**: La aprobación autónoma antigua del chofer ya no interviene en el nuevo proceso, aunque el campo histórico se mantenga para no perder registros previos.

## Campos e integración del ERP

**La API de guías no cambia**. En el `POST /api/transcash/v1/guias` se siguen esperando `id_externo`, `numero_guia`, `chofer_login`, `proveedor_codigo`, `placa`, `destino_codigo`, `destino_ciudad`, `destino_provincia`, `direccion_origen`, `direccion_destino`, `productos`, etc. Reutiliza el contrato completo de la V5.8, `TRANSCASH_V58_API_GUIAS_COMPLETA_EJEMPLO.json` y su esquema. Para asociar una guía a una ruta deben coincidir el código de destino y la compañía. El operador elige chofer, transportista y placa en la hoja, y estos datos pasan a las guías al confirmar. La sincronización posterior desde el ERP no sobrescribe esta asignación operativa. La ruta y el embarque se crean desde Odoo, **no desde el ERP**, para evitar cambios contradictorios después de preparar la carga.

La tarifa corresponde a `tipo_vehiculo` + `destino_codigo` de la hoja, no a `cantidad`, `kilos`, `pallets` ni a una factura contable. Se puede ampliar el tarifario por peso, tramo o transportista en otro ciclo si existen reglas comerciales distintas.

## Migración desde V5.8

1. En una **base de pruebas**, crear respaldos íntegros: PostgreSQL, filestore y carpeta `logistica_transcash`.
2. Sustituir el addon por `logistica_transcash` de V5.9, reiniciar servicio y **Actualizar** en Aplicaciones; **no desinstalar**.
3. La migración V5.9 agrupa guías de los embarques antiguos **en preparación** en rutas provisionales por destino, sin duplicar guías. El operador debe grabar/validar video para liberar esas rutas. Embarques antiguos **en ruta** y sus entregas no se alteran.
4. Asignar el nuevo grupo a operadores. Cargar tarifas de prueba para destinos reales. Probar crear dos hojas de ruta, ensamblar embarque, videos, aceptación, entrega y firma.
5. Configurar `client_max_body_size` de Nginx (p. ej. más de 75 MB) y `proxy_read_timeout` razonable si se subirán videos grandes. Mantener HTTPS. Para celular, el navegador necesita estar conectado al finalizar aceptación y entrega; las evidencias de descarga pueden quedar en cola offline hasta sincronizarse.
6. No borrar datos locales de la PWA si existen evidencias pendientes. Recargar recursos y verificar actualización en Android/iOS.

## Reglas y excepciones

- Un solo embarque activo por chofer; hojas sin embarque pueden planificarse, pero solo se enlazan cuando está disponible.
- El chofer nunca crea rutas ni embarques. La creación antigua por portal y los endpoints de iniciar/finalizar carga devuelven error de autorización.
- Los nuevos embarques requieren al menos una ruta y cada ruta un video validado antes de aceptar/salir.
- No se agrega ninguna ruta después de liberar el embarque al chofer. Si el chofer observa diferencia, Logística devuelve a preparación para subsanar y volver a liberar.
- El video se guarda como evidencia privada de la ruta; reproducción mediante un endpoint autenticado y autorizado. No habilitar acceso público a esos adjuntos.
- La firma solo documenta quién firmó en el dispositivo del chofer; la conformidad final del cliente es una decisión independiente. Se conserva la fecha del cierre operativo y quién realizó la acción.
- Los guías con un embarque anterior en preparación se convierten en rutas provisionales; si tienen tipos de vehículo o precios especiales, Logística debe revisarlos antes de liberar.

## Verificaciones

Comprobación estática de Python, estructura XML, JavaScript e integridad del ZIP. Se incluyen pruebas Odoo en `tests/test_rutas_v59.py` pero **deben ejecutarse en una instancia Odoo 18**. No está probado en tu VPS.
