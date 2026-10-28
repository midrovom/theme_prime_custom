# Control de Presupuesto de Gastos — Odoo 18

Módulo técnico: **`expense_budget_control`**. Versión: `18.0.1.4.79`.

## Funciones

- Catálogo de **rubros** y **cuentas controladas**, separado por empresa.
- Un presupuesto por **empresa, año y rubro**, con importes **proyectados por cuenta y mes**. En el mismo año se admiten varios rubros distintos.
- Gastos reales manuales, importados desde **Excel/CSV** o recibidos de **API Administrator**.
- Comparación de presupuesto frente al real: consumido, disponible y porcentaje de ejecución.
- Vistas tipo lista, gráfica de barras y tabla dinámica, con filtros por rubro, cuenta, mes y presupuesto.
- **PDF anual imprimible** desde cada presupuesto, agrupado por rubro y cuenta, con columnas mensuales de presupuesto, gasto y ejecución %.
- Registro de sincronizaciones, idempotencia por clave externa y reconciliación de gastos sin línea presupuestaria.
- Roles de consulta, registro, aprobación y administrador; reglas de acceso multiempresa.

## Instalación

1. Copie la carpeta `expense_budget_control` a un directorio dentro de `addons_path` de Odoo 18.
2. Confirme que `api_administrator` está instalado y tiene configuradas las APIs GET activas. La integración soporta instalaciones **sin** método `call_api`: realiza GET con la URL y las credenciales ya guardadas en `api.administrator`.
3. Instale `openpyxl` en el **Python que ejecuta Odoo**: `pip install openpyxl`.
4. Reinicie Odoo, actualice la lista de aplicaciones e instale **Control de Presupuesto de Gastos**.
5. En Ajustes → Usuarios, asigne el rol adecuado: **Consulta de presupuestos** (solo lectura), **Registro de presupuestos** (crear y editar borradores, importar proyecciones y registrar/corregir gastos reales manualmente), **Aprobador de presupuestos** (aprobar presupuestos pendientes sin editar valores) o **Administrador de presupuestos** (gestión completa, incluyendo API). Los permisos para gestionar `api.administrator` se configuran en el módulo externo `api_administrator`.

**Flujo de aprobación:** el usuario de Registro guarda el presupuesto y sus líneas en estado **Borrador**. El usuario de Registro pulsa **Enviar a aprobar** y otro usuario con rol Aprobador pulsa **Aprobar**; ese rol no puede registrar ni modificar importes. El Administrador puede registrar, aprobar o volver a borrador presupuestos. Registro no puede aprobar ni reabrir; el Aprobador tampoco puede reabrir. El importador Excel sigue disponible para el Administrador en sus tres modalidades; Registro únicamente puede importar **Proyecciones mensuales**; puede registrar y corregir gastos reales desde **Control de Gastos → Gastos reales**, sin eliminarlos, pero no puede importar gastos desde Excel ni modificar rubros o cuentas.

> **Compatibilidad:** código orientado a Odoo 18. Se comprobaron sintaxis y referencias estáticas, pero es obligatorio hacer una prueba de instalación en una base de datos Odoo 18 con la versión concreta de su módulo `api_administrator`. No se proporcionó el código completo ni las vistas originales de esa dependencia.

## Primer uso

1. Vaya a **Control de Gastos → Importar Excel/CSV**, elija **Cuentas y rubros**, seleccione la empresa e importe la hoja **Cuentas** del libro de ejemplo.
2. Vaya a **Presupuestos** y cree, por ejemplo, `Servicios básicos 2026`, seleccionando **empresa, año y rubro**. Para otro rubro puede crear otro presupuesto del mismo año, aunque el primero siga en borrador.
3. En **Importar Excel/CSV**, seleccione **Proyecciones mensuales**, el presupuesto y la hoja **Proyecciones**. También puede editar las doce proyecciones por cuenta en el propio formulario.
4. Registre gastos reales a mano o importe la hoja **Gastos** con tipo **Gastos reales**.
5. En **Proyectado vs. real** vea las desviaciones por rubro, cuenta y mes. Un saldo negativo identifica exceso presupuestario.
6. Envíe cada presupuesto a aprobación cuando esté listo. Puede registrar en paralelo presupuestos de otros rubros para la misma empresa y año, pero nunca un segundo presupuesto del mismo rubro (incluso si el primero está aprobado o rechazado).

### Columnas de Excel

La importación usa la hoja con nombre indicado (si existe) o, en caso contrario, la primera hoja del archivo.

**Cuentas** (rubros y cuentas controladas):

| codigo_rubro | nombre_rubro | codigo_cuenta | nombre_cuenta |
|---|---|---|---|
| ADM | Administración | 600100 | Servicios de oficina |

**Proyecciones** (asociadas al presupuesto seleccionado):

| codigo_cuenta | mes | proyectado |
|---|---|---|
| 600100 | 1 | 1500 |

**Gastos** (moneda de la empresa):

| identificador | fecha | codigo_cuenta | monto | descripcion | referencia |
|---|---|---|---|---|---|
| DOC-0001 | 2026-01-15 | 600100 | 325.50 | Internet | FAC-001 |

El **identificador de gasto es obligatorio y estable**, ya que evita duplicados: volver a importar la misma clave actualiza el movimiento. Las cuentas deben existir antes de importar proyecciones o gastos. Fecha válida: `AAAA-MM-DD` o `DD/MM/AAAA`. Mes: `1`–`12` o nombre en español. Gastos positivos representan consumo; negativos, devolución/reverso. Puede usar CSV UTF-8 con coma o punto y coma. **Guarde los códigos de cuenta como texto en Excel** para conservar ceros iniciales.

El archivo completo debe ser válido; si una fila tiene un error, se revierte la importación entera y se indica el número de fila. Límites: 8 MB y 20.000 filas por archivo.

## Imprimir PDF de presupuesto anual (nuevo)

1. Abra **Control de Gastos → Presupuestos anuales** y seleccione el presupuesto que desea imprimir.
2. Pulse **Imprimir PDF** en la cabecera. Alternativamente, use la opción **Imprimir → Presupuesto anual por rubro y cuenta**.
3. El documento incluye **empresa, presupuesto, año y moneda**, seguido de una tabla agrupada por **rubro** (ej. *Servicios básicos*) y debajo sus **cuentas controladas** (ej. *Luz*, *Agua*).
4. El año se muestra en **una sola tabla de doce meses en A1 horizontal**, con tres columnas por cada mes: **Presupuesto** (valor proyectado), **Gasto** (valor real consumido) y una **columna sin nombre** que presenta el valor del campo **Ejecución (%)**. La columna final muestra el **porcentaje de ejecución anual** por rubro, cuenta y total general; también hay subtotales por rubro y totales mensuales. La tabla es desplazable horizontalmente en la vista HTML cuando la pantalla es estrecha.

**Interpretación:** **Ejecución (%) = Gasto / Presupuesto × 100**; 25 % significa que se ha consumido el 25 % del presupuesto, no que quede el 25 %. El saldo disponible continúa consultándose en el campo **Disponible** del presupuesto. Si un mes no tiene una línea de proyección, el PDF muestra «—». Los gastos no conciliados con una línea no se incluyen en el consumo de esa línea hasta vincularlos mediante **Conciliar gastos**.

Al actualizar una instalación anterior, copie la nueva carpeta y ejecute la actualización del módulo (`-u expense_budget_control`) para registrar la acción de reporte y el diseño QWeb. Para generar PDFs en Odoo se necesita que su servidor tenga configurado `wkhtmltopdf` correctamente.

## Integración API Administrator

El módulo **reutiliza las APIs existentes** del modelo `api.administrator`; no crea ni cambia URL, usuario o contraseña. Si `api_administrator` expone `call_api`, se utiliza. Si no lo tiene, Control de Gastos hace GET directamente con `url`, `end_point`, `user_id` y `password` de la API seleccionada, enviando las cabeceras `userid/password` del ERP. Consulte `docs/CONEXION_API_SIN_CALL_API_1476.md`.

**Configuración:**

1. Cree primero la API en su módulo **API Administrator**, con método `get`, estado `A` y la empresa correspondiente.
2. Abra **Control de Gastos → Configuración → Configuración API de gastos**.
3. Seleccione la **Empresa** y elija en **API existente** la API que ya creó (una selección por empresa); guarde.
4. Pulse **Sincronizar gastos** desde la configuración, o **Sincronizar API** desde un presupuesto de esa empresa.
5. Consulte los resultados en **Configuración → Historial API**.

**Al actualizar desde la versión 1.2:** entre en **Configuración API de gastos** y seleccione la API existente. El indicador `is_expense_budget_sync` de la versión anterior ya no se utiliza para decidir qué API consume el módulo. No se modifica la configuración original de su API.

**Ejemplo de respuesta JSON**:

```json
{
  "success": true,
  "data": [
    {"id": "G-0001", "codigo_cuenta": "600100", "fecha": "2026-01-15",
     "monto": 325.50, "descripcion": "Internet", "referencia": "FAC-001"},
    {"id": "G-0002", "codigo_cuenta": "600200", "fecha": "2026-01-20",
     "monto": 900, "descripcion": "Suministros", "referencia": "FAC-002"}
  ]
}
```

También se admite una lista directa, o el arreglo `items` en lugar de `data`. Variantes de campos admitidas: `id/identificador/external_id/id_movimiento`, `codigo_cuenta/cuenta/codigo/account_code`, `fecha/date`, `monto/importe/valor/amount`, `descripcion/detalle/concepto/description`, `referencia/documento/reference`.

**Notas importantes:**

- Cada movimiento API se identifica de forma única por **empresa + ID de API Administrator + identificador**, de modo que otra ejecución lo actualiza si cambió, sin duplicarlo.
- Los gastos sin presupuesto o sin proyección para su mes/cuenta se guardan **sin asignar**; cuando se cree una proyección compatible se vincularán. Puede usar el botón **Conciliar gastos** de un presupuesto.
- Cada API se procesa en una transacción parcial independiente: si hay registros inválidos, **se revierte esa API** y se registra un error, sin conservar un lote incompleto.
- La tarea programada `Presupuestos: importar gastos desde API` está **desactivada por defecto**. Active en Ajustes → Técnico → Automatización → Acciones planificadas una vez comprobado el endpoint.
- El endpoint debe entregar importes en la **moneda base de la empresa**. El módulo **no realiza conversión** de moneda ni deduce impuestos.
- El módulo registra movimientos externos como gastos de control presupuestario; **no crea facturas ni asientos contables** y no sincroniza automáticamente `account.move.line`. La carga desde la contabilidad Odoo sería una extensión posterior.
- Las llamadas API admiten `call_api` si existe y tienen un transporte GET propio como alternativa; ambos utilizan la API elegida en `api_administrator`. No se guardan duplicados de credenciales en el módulo presupuestario.

## Verificación y pruebas

Comandos de ejemplo en una instalación con PostgreSQL y Odoo 18:

```bash
./odoo-bin -d BASE_PRUEBAS -i expense_budget_control --stop-after-init
./odoo-bin -d BASE_PRUEBAS -u expense_budget_control --test-enable --test-tags /expense_budget_control --stop-after-init
```

Los tests (`tests/test_budget.py`) validan cálculo del saldo, vínculo de gastos anteriores al presupuesto, importación idempotente y bloqueo de proyecciones aprobadas.

## Estructura

```
expense_budget_control/
├── __manifest__.py
├── models/                  # rubros, cuentas, presupuestos, gastos y API
├── report/                  # informe PDF anual QWeb, plantilla y formato A1 apaisado
├── wizard/                  # importador XLSX/CSV
├── security/                # ACL y reglas multiempresa
├── views/                   # listas, formularios, pivote y gráficos
├── data/                    # tarea programada opcional
├── tests/                   # pruebas Odoo
└── docs/plantilla_importacion.xlsx
```

**Estados de presupuestos:** Borrador → Pendiente de aprobación → Aprobado o Rechazado. Una misma empresa y año pueden tener varios presupuestos de rubros **diferentes**, en cualquier estado, pero solo uno por rubro. Las líneas deben usar cuentas del rubro seleccionado en la cabecera. Los presupuestos históricos con varios rubros conservan sus líneas para revisión. Véase `docs/UN_PRESUPUESTO_POR_RUBRO_1479.md`.

## Navegación por roles (v1.4.5)

- **Consulta:** Presupuestos, Proyectado vs. real y Gastos reales (solo lectura).
- **Registro de presupuestos:** exclusivamente los menús **Presupuestos** e **Importar Excel/CSV**. Conserva la edición de consumido en proyecciones, el envío a aprobar y Sincronizar API desde los presupuestos.
- **Aprobador de presupuestos:** **Aprobación de presupuestos** (solo pendientes de aprobación y aprobados; nunca borradores), **Proyectado vs. real** y **Gastos reales** (lectura).
- **Administrador de presupuestos:** todos los menús, incluyendo Presupuestos, Aprobación, Proyectado vs. real, Gastos reales, Configuración e Importar Excel/CSV.

La visibilidad de menús no cambia el cálculo presupuestario ni la API. Al actualizar desde versiones anteriores se limpia la pertenencia heredada al grupo Consulta para usuarios de Registro, Aprobador o Administrador; el acceso de lectura continúa gracias a un grupo técnico interno.


**Visibilidad del aprobador (v1.4.6):** tanto en la pestaña Aprobación de presupuestos como en Proyectado vs. real, solo puede consultar presupuestos y proyecciones en estado Pendiente de aprobación o Aprobado. La restricción también se aplica a accesos directos; el Administrador conserva todos los estados.


## Imprimir PDF desde Proyectado vs. real (v1.4.11)

1. Abra **Control de Gastos → Proyectado vs. real** (vista de lista).
2. Pulse **Imprimir PDF**. No necesita seleccionar filas: el asistente requiere **Empresa**, **Año**, **Rubro** y **Centro de costo**; la selección de **Meses** y **Cuentas controladas** es opcional.
3. Pulse **Imprimir PDF** en el asistente. El reporte A4 horizontal muestra los rubros, sus cuentas y las columnas **Proyectado**, **Gasto real**, **Disponible** y **Ejecución (%)**, con subtotales y total general.

El porcentaje se calcula como consumido total / proyectado total x 100, no como promedio de porcentajes mensuales. No se duplican gastos de API o Excel: se utilizan exclusivamente los totales de las líneas mensuales. Los usuarios Aprobador solo podrán imprimir las líneas de presupuestos pendientes de aprobación o aprobados que ya pueden consultar; los demás roles conservan sus permisos. El PDF anual existente (12 meses) no se altera.


## Dashboard interactivo (v1.4.46)

En **Control de Gastos → Dashboard de gastos**, los usuarios de Consulta,
Aprobación y Administración pueden elegir Empresa, Año, Rubro y Cuenta
controlada. El gráfico de barras muestra el consumo mensual total del filtro
y permite pulsar un mes para examinar sus cuentas; el pastel presenta el
reparto anual del consumo por cuenta. Al pulsar una cuenta, el gráfico de
barras se filtra para ver en qué meses tuvo mayores gastos.

El dashboard usa `expense.budget.line.actual_amount`, incluyendo gastos
registrados/importados y ajustes ya incluidos en ese campo. Se respetan
las reglas existentes de visibilidad por estado y empresa (sin `sudo`).

En el PDF de Proyectado vs. real se oculta **Consumo inicial**, pero se
conserva en el cálculo del **Consumo actual**. Se incorpora la columna
**Total proyectado = Consumo actual + Saldo disponible**, ubicada antes de
Consumo actual. **Consumo corte** y los saldos no modifican sus fórmulas.

### v1.4.63 — ERP: catálogos completos y consumo al guardar

- **Sincronizar** importa por separado el catálogo completo de cuentas
  (`getctagastos/2`), el catálogo completo de centros (`getcentrocostos/2`)
  y los consumos correspondientes al año seleccionado (`getconsumosgastos/2`).
- La carga de catálogos reutiliza registros existentes por empresa y código,
  incluso si están inactivos o tenían espacios en el código. Un bloqueo por
  empresa impide que cron y sincronización manual inserten duplicados en paralelo.
- Al **guardar** una proyección se vuelve a consultar `getconsumosgastos/2` y
  se filtra por código de cuenta, centro, subcentro, mes y año del presupuesto.
  `Consumido` suma los `Valor` correspondientes; los restantes no se asignan
  a esa línea. Los errores de consulta se registran en **Historial API** sin
  descartar el presupuesto que se está guardando.
- No se crean conexiones ni credenciales adicionales. Se reutilizan las tres
  APIs GET existentes en `api_administrator` desde una sola configuración ERP.


## Ajustes v1.4.66 (API, subcentros y PWA)

- **Configuración API ERP** conserva los tres selectores de `api_administrator`; el campo
  Año no se presenta en esta pantalla. La sincronización desde esta pantalla
  y el cron usan el año actual, mientras que al guardar una proyección se consulta
  el año/mes definidos en el presupuesto y la línea.
- Cuando el ERP devuelve `Centro` y `Subcentro`, se crea o recupera un subcentro
  seleccionable *dentro del centro correspondiente*; el catálogo se descubre
  incluso si los consumos pertenecen a años anteriores.
- **Proyecciones mensuales → Subcentro** es un selector de los códigos importados
  por `getconsumosgastos/2`, no un campo de texto libre. Dejarlo vacío mantiene
  el comportamiento histórico de sumar todos los subcentros del mismo centro;
  al seleccionarlo el consumo queda restringido a ese subcentro, código de cuenta,
  centro, año y mes.
- **Rubro** usa el diálogo nativo Crear y editar y permite abrir uno existente
  para agregar o quitar cuentas; se elimina el botón de gestión de rubros de
  Proyecciones.
- **Gastos reales** está en Configuración. En la PWA móvil se navega con una
  tarjeta Configuración que abre los accesos de gestión autorizados.
- Ante SQLSTATE `40001` (actualización concurrente) o `40P01`, no se oculta
  el error como tres endpoints fallidos: se deja que el manejador de transacciones
  de Odoo reintente toda la operación. Después de los reintentos fallidos,
  el administrador debe consultar el registro del servidor.


## Requisito de filtros para imprimir comparativo (v18.0.1.4.79)

Para imprimir el PDF **Proyectado vs. real** deben seleccionarse **Año, Rubro y Centro de costo**.
El asistente ya no establece automáticamente el año actual, para que el operador seleccione el período explícitamente.
El formulario marca los tres campos como obligatorios y el servidor valida los valores tanto desde el botón
**Imprimir PDF** como al renderizar el reporte directamente; el mensaje detalla los campos pendientes.

**Meses** y **Cuentas controladas** siguen siendo filtros opcionales. Si no se seleccionan meses,
se imprimen los 12 meses; si no se seleccionan cuentas, se consideran todas las cuentas del rubro
con líneas presupuestarias para ese centro de costo.
Las operaciones de cron, conexión ERP y cálculos del reporte no se modifican con este cambio.

## Presupuesto anual por cuenta y centro de costo (18.0.1.4.84)

En las líneas de proyección se incorpora el campo **Presupuesto anual**. Al ingresar un monto mayor que cero, el sistema calcula **Proyectado = Presupuesto anual / 12**, redondeado a la moneda de la empresa. Por ejemplo, un presupuesto anual de USD 1.200 genera una proyección mensual de USD 100.

El monto anual se comparte entre los meses pendientes de la misma cuenta controlada, centro de costo, empresa y año. Al añadir un nuevo mes para esa combinación, el módulo reutiliza el monto anual guardado y calcula el proyectado mensual. Otra cuenta o centro de costo mantiene su propio presupuesto anual.

Los importes anuales y mensuales de líneas ya aprobadas no se modifican. Una vez que la combinación cuenta/centro tiene un objetivo anual aprobado, ese objetivo queda bloqueado para las nuevas líneas; los nuevos meses conservan la distribución mensual calculada. Para líneas históricas aprobadas antes de incorporar este campo, el monto anual permanece vacío/cero hasta que se defina para los meses futuros; no se infiere automáticamente para evitar alterar la planificación histórica.
