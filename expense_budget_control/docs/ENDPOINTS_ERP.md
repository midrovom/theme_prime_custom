> **Actualización v18.0.1.4.76 (prevalece sobre las secciones históricas de este documento):** el cron cada 5 horas y el botón «Sincronizar» importan **todos los años** sin filtro; las tres APIs utilizan un transporte GET directo cuando `api.administrator` no incluye `call_api`. Ver `CONEXION_API_SIN_CALL_API_1476.md`.

# Integración ERP única — v1.4.61

## Una sola configuración

En **Control de Gastos → Configuración → Configuración API ERP** aparecen tres campos para seleccionar las APIs GET existentes en `api_administrator`. No se crean endpoints ni credenciales nuevas, y la antigua entrada separada «API de centros de costo» queda oculta. Si los tres registros ya existen, el botón **Sincronizar** también los detecta automáticamente por el campo `end_point`.

- **Cuentas**: `inventory_odoo/consulta_odoo/getctagastos/2`, JSON `data:[{"Codigo":"601010101002","Nombre":"Decimo Tercer Sueldo"}]`.
- **Centros**: `inventory_odoo/consulta_odoo/getcentrocostos/2`, JSON `data:[{"Codigo":"ADM       ","Nombre":"Administración"}]`.
- **Consumos**: `inventory_odoo/consulta_odoo/getconsumosgastos/2`, JSON `data:[{"Codigo":"601010101002","Valor":"161.82","Fecha":"jul 25 2022 12:00:00:000","Centro":"ADM       ","Subcentro":"GDE       "}]`.

Las tres APIs deben ser GET activas y pertenecer a la misma empresa, configuradas con el URL base y la autenticación en API Administrator. La sincronización hace GET y registra cuántas filas llegan de cada endpoint. Ver **Configuración → Historial API** y los mensajes `[PRESUPUESTOS ERP]` en los logs de Odoo. No imprime cabeceras ni contraseñas.

## Año, centro y subcentro

- Si sincroniza desde **Presupuestos → [presupuesto] → Sincronizar API**, importa solo consumos del **año de ese presupuesto** (por ejemplo 2022).
- Si sincroniza desde la configuración única, usa el campo **Año de los consumos** (inicialmente el actual).
- El cron **Presupuestos: cuentas, centros y consumos ERP (5 horas)** ejecuta cada cinco horas la importación de consumos del **año calendario actual**. Descubre empresas tanto por su configuración como por sus APIs GET ERP activas.
- Los **catálogos** de cuentas y centros se actualizan independientemente del año. Los **movimientos** fuera del año solicitado se omiten y cuentan en `Omitidas por año`.
- Cada gasto se vincula con la proyección que coincida en empresa + cuenta `Codigo` + centro `Centro` + año/mes de `Fecha` + `Subcentro` (si la proyección especifica uno). Una línea sin subcentro absorbe gastos de subcentros sin línea específica, para compatibilidad con presupuestos previos.
- `Valor` se almacena en gasto real y se computa automáticamente como **Consumido** de la línea presupuestaria asociada. No sobrescribe **Proyectado** ni ajustes manuales.
- Cuentas o centros con movimientos pero ausentes de sus respectivos catálogos se crean temporalmente con nombre «pendiente de catálogo» y se actualizan cuando llega el catálogo.

## Diagnóstico

El botón muestra el número de APIs, nuevos, actualizados y errores. **Historial API** guarda una fila por endpoint y ejecución con el nombre/ruta consultada, filas recibidas, creadas, modificadas, omitidas por año, vinculadas al presupuesto y sin línea presupuestaria, así como el error si lo hay. Si un gasto figura como **Sin línea presupuestaria**, verifique `Codigo`, `Centro`, `Subcentro`, `Fecha`, compañía, y que exista una proyección mensual para ese período.

No se contactaron los endpoints reales durante el desarrollo local. Para probar en su instancia, ejecute Sincronizar, compruebe el historial y después valide el presupuesto del mismo año. Use una base de pruebas para actualizar desde v1.4.60, ya que se amplía el índice único de las líneas mensuales a la dimensión Subcentro.

**Limitación del origen:** sin `id` de movimiento, el identificador se infiere de Código+Centro+Subcentro+Fecha+Valor+ordinal; si el origen corrige cualquiera de esos datos el cambio puede crear otro movimiento. Enviar `id` estable permite actualizaciones inequívocas.

### Menú y subcentro (v1.4.62)

Solo se muestra **Configuración → Configuración API ERP** para las 3 conexiones
existentes en `api_administrator`. La entrada antigua de API de centros de costo
está deshabilitada también en Accesos rápidos (móvil/PWA).

En **Presupuestos → Proyecciones mensuales** se muestra **Subcentro**, código libre
del campo `Subcentro` de la API (ej. `GDE`). El importe `Valor` se registra en
Gastos reales y se refleja automáticamente en `Consumido` de la línea cuya
**empresa, cuenta (Codigo), centro (Centro), subcentro (Subcentro), año y mes
(Fecha)** sean compatibles. La asociación también se realiza cuando la línea
se crea **después** de importar el consumo. En una línea sin Subcentro se
agrupan únicamente movimientos sin proyección más específica.

### Corrección de duplicados (v1.4.63)

Si un código ya existe en `expense.budget.account` o
`expense.budget.cost.center` para la misma empresa, **se reutiliza/actualiza**
(en vez de intentar crearlo otra vez). Incluye registros inactivos o
códigos históricos almacenados con espacios; no borra relaciones, consumos
ni presupuestos. En caso de una colisión de INSERT concurrente se revierte
solo el intento, se vuelve a buscar el registro y se continúa. El botón
**Sincronizar** y el cron ERP quedan serializados por empresa mediante un
bloqueo transaccional PostgreSQL. No hay nuevas tablas ni dependencias.

Consultar el log del servidor por `[PRESUPUESTOS ERP]` y el menú
**Historial API**. Si la notificación muestra **Ya existentes > 0** con
**Errores: 0**, es normal: el catálogo ya había sido importado y se confirmó
sin necesidad de insertar filas adicionales. El consumo se sigue importando
solo para el año indicado en la sincronización.


## Consulta de consumos al guardar una proyección (v1.4.63)

El catálogo de **todas** las cuentas y **todos** los centros de costo se importa
con el botón **Sincronizar** de Configuración API ERP o mediante el cron de 5 horas.
La importación es idempotente por empresa + código, incluso ante registros
históricos inactivos o con códigos completados con espacios.

Después de seleccionar una cuenta y centro importados, al guardar una línea de
**Proyecciones mensuales** se llama a `getconsumosgastos/2`. Como el endpoint
proporcionado no tiene parámetros de filtro, se recibe la respuesta y se filtra
localmente por `Codigo`, `Centro`, `Subcentro`, mes y año del presupuesto. Se
suman los `Valor` de **todos** los movimientos coincidentes y se actualiza
`Consumido` a partir de gastos reales, evitando sumar dos veces una respuesta
repetida. Un subcentro específico tiene prioridad sobre la línea genérica.

Ejemplo: `601010101002` + `DIC` + `GDE` + abril de 2020 + `Valor=50.00` se
vincula solo con esa proyección, no con 2026 ni con otro centro.

El botón **Sincronizar API** sigue pudiendo importar catálogos y consumos de
todo el año presupuestado, y deja un resultado detallado en **Historial API**.
Si el endpoint falla mientras se guarda una proyección, el presupuesto se
conserva y el error se registra en el historial; el consumido se actualizará
cuando la API vuelva a responder y se sincronice de nuevo.


## Desde v1.4.65 — subcentro automático y periodos exactos

- El catálogo de cuentas `getctagastos/2` se une por `Codigo`; el de centros `getcentrocostos/2` por `Codigo`.
- El consumo `getconsumosgastos/2` se filtra usando simultáneamente cuenta `Codigo`, `Centro` normalizado, **año y mes exactos extraídos de `Fecha`**. Por ejemplo, `abr 25 2026` solo corresponde a abril de 2026.
- El campo visible **Subcentro (API)** es de solo lectura: muestra el valor recibido en `Subcentro` de los gastos reales vinculados. Si hay varios subcentros para ese mes, lista todos (p. ej. `GDE, VTA`) y el Consumido suma sus movimientos sin duplicarlos.
- `subcenter_code` se conserva únicamente para líneas históricas que filtraban por subcentro. Esto preserva su conciliación y evita mezclar sus importes con líneas generales.
- Al guardar proyecciones se revisan vínculos anteriores y se reasignan gastos si su fecha/cuenta/centro no corresponde a la línea original. La consulta al ERP no elimina movimientos históricos.
