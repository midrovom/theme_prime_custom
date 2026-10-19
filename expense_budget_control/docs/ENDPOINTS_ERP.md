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
