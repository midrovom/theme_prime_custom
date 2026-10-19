# API de cuentas, centros de costo y consumos — v1.4.60

**Configuración previa:** en el módulo instalado `api_administrator`, registrar (o reutilizar) tres APIs `GET` activas de la empresa con sus credenciales y los endpoints siguientes (el prefijo URL pertenece a su servidor):

| Campo en Configuración API de gastos | `end_point` en API Administrator |
| --- | --- |
| API de cuentas de gastos | `inventory_odoo/consulta_odoo/getctagastos/2` |
| API de centros de costo (ERP) | `inventory_odoo/consulta_odoo/getcentrocostos/2` |
| API de consumos de gastos (ERP) | `inventory_odoo/consulta_odoo/getconsumosgastos/2` |

1. En **Control de Gastos → Configuración → Configuración API de gastos**, seleccione Empresa y las tres APIs ya creadas. No se crea ni se modifica ninguna credencial ni API desde este módulo.
2. Pulse **Sincronizar** en esta configuración o en el formulario de presupuesto (Registro y Administrador). Orden: cuentas → centros → consumos. El historial informa los resultados por endpoint.
3. Hay un cron activo **Presupuestos: cuentas, centros y consumos ERP (5 horas)**. Sincroniza exclusivamente las empresas que tengan APIs seleccionadas; el cron antiguo de sincronización diaria permanece desactivado. Para detener la sincronización automática, desactive el nuevo cron desde Ajustes → Técnico → Automatización → Acciones planificadas.

### Formatos recibidos

- Cuentas: `{"data":[{"Codigo":"601010101001","Nombre":"Sueldos y Salarios"}]}`.
- Centros: `{"data":[{"Codigo":"MAT       ","Nombre":"MAT- ALB - NEXUS "}]}`.
- Consumos: `{"data":[{"Codigo":"601010101001","Valor":"2431.03","Fecha":"mar 25 2020 12:00:00:000","Centro":"ALM       ","Subcentro":"GDE       "}]}`.

Se eliminan espacios laterales de códigos y nombres. Los movimientos se registran en **Gastos reales**, con empresa, cuenta, fecha, código de centro y subcentro y `amount = Valor`. Los centros no presentes en el catálogo se identifican temporalmente por código como **pendiente de catálogo** y se completan con su nombre oficial en la próxima sincronización del catálogo.

El campo **Consumido** de una proyección se calcula desde los gastos reales vinculados a esa misma **empresa + cuenta + centro + mes + año**. Si todavía no existe una proyección con esos datos, el consumo queda guardado como gasto real sin línea asignada hasta que se registre la proyección correspondiente. Nunca se altera directamente `actual_amount` ni el proyectado.

### Una cuenta, varios centros

`getctagastos` solo envía cuenta y descripción: **no** envía centro de costo. La relación **cuenta ↔ centro** se obtiene de los movimientos de `getconsumosgastos` (campos `Codigo` y `Centro`). Una misma cuenta puede tener varios centros. Al crear un rubro, la pantalla muestra los centros detectados de sus cuentas, pero **no inventa un centro único**: el responsable debe elegir el centro para cada proyección mensual. Si hay uno solo, el formulario puede proponerlo automáticamente.

### Idempotencia y limitaciones

El JSON de consumos mostrado no contiene ID inmutable por transacción. Para evitar duplicados al ejecutar el cron varias veces, el importador usa una huella criptográfica de `Codigo + Fecha + Valor + Centro + Subcentro`, distinguiendo filas idénticas repetidas mediante un ordinal. **Si cambia alguno de esos campos en el origen, no se puede saber si fue una corrección o un movimiento nuevo; podría importarse otro consumo.** Para actualización inequívoca por movimiento se necesita que el ERP envíe `id` o `external_id` estable. La sincronización no borra automáticamente consumos que ya no aparecen en el endpoint, porque la respuesta podría estar paginada o limitada.

La empresa se toma de la configuración seleccionada en Odoo. El sufijo `/2` del endpoint es el proporcionado por el ERP; el módulo no supone que el código `2` sea el ID de compañía de Odoo. No se prueba la conexión real en el desarrollo local: debe validarse contra el servidor y su versión de `api_administrator`.
