# Control de Presupuesto de Gastos — Odoo 18

Módulo técnico: **`expense_budget_control`**. Versión: `18.0.1.4.11`.

## Funciones

- Catálogo de **rubros** y **cuentas controladas**, separado por empresa.
- Un presupuesto anual por empresa, con importe **proyectado por cuenta y mes**.
- Gastos reales manuales, importados desde **Excel/CSV** o recibidos de **API Administrator**.
- Comparación de presupuesto frente al real: consumido, disponible y porcentaje de ejecución.
- Vistas tipo lista, gráfica de barras y tabla dinámica, con filtros por rubro, cuenta, mes y presupuesto.
- **PDF anual imprimible** desde cada presupuesto, agrupado por rubro y cuenta, con columnas mensuales de presupuesto, gasto y ejecución %.
- Registro de sincronizaciones, idempotencia por clave externa y reconciliación de gastos sin línea presupuestaria.
- Roles de consulta, registro, aprobación y administrador; reglas de acceso multiempresa.

## Instalación

1. Copie la carpeta `expense_budget_control` a un directorio dentro de `addons_path` de Odoo 18.
2. Confirme que su módulo personalizado se llama **exactamente `api_administrator`**. Debe instalarse y definir el modelo **`api.administrator`**, con método `call_api(api_name, method, company_id, ...)` y `button_run_sync` como en el código de referencia. La dependencia en el manifiesto ya apunta a `api_administrator`.
3. Instale `openpyxl` en el **Python que ejecuta Odoo**: `pip install openpyxl`.
4. Reinicie Odoo, actualice la lista de aplicaciones e instale **Control de Presupuesto de Gastos**.
5. En Ajustes → Usuarios, asigne el rol adecuado: **Consulta de presupuestos** (solo lectura), **Registro de presupuestos** (crear y editar borradores, importar proyecciones y registrar/corregir gastos reales manualmente), **Aprobador de presupuestos** (aprobar presupuestos pendientes sin editar valores) o **Administrador de presupuestos** (gestión completa, incluyendo API). Los permisos para gestionar `api.administrator` se configuran en el módulo externo `api_administrator`.

**Flujo de aprobación:** el usuario de Registro guarda el presupuesto y sus líneas en estado **Borrador**. El usuario de Registro pulsa **Enviar a aprobar** y otro usuario con rol Aprobador pulsa **Aprobar**; ese rol no puede registrar ni modificar importes. El Administrador puede registrar, aprobar o volver a borrador presupuestos. Registro no puede aprobar ni reabrir; el Aprobador tampoco puede reabrir. El importador Excel sigue disponible para el Administrador en sus tres modalidades; Registro únicamente puede importar **Proyecciones mensuales**; puede registrar y corregir gastos reales desde **Control de Gastos → Gastos reales**, sin eliminarlos, pero no puede importar gastos desde Excel ni modificar rubros o cuentas.

> **Compatibilidad:** código orientado a Odoo 18. Se comprobaron sintaxis y referencias estáticas, pero es obligatorio hacer una prueba de instalación en una base de datos Odoo 18 con la versión concreta de su módulo `api_administrator`. No se proporcionó el código completo ni las vistas originales de esa dependencia.

## Primer uso

1. Vaya a **Control de Gastos → Importar Excel/CSV**, elija **Cuentas y rubros**, seleccione la empresa e importe la hoja **Cuentas** del libro de ejemplo.
2. Vaya a **Presupuestos** y cree, por ejemplo, `Presupuesto 2026`, para la misma empresa y año.
3. En **Importar Excel/CSV**, seleccione **Proyecciones mensuales**, el presupuesto y la hoja **Proyecciones**. También puede editar las doce proyecciones por cuenta en el propio formulario.
4. Registre gastos reales a mano o importe la hoja **Gastos** con tipo **Gastos reales**.
5. En **Proyectado vs. real** vea las desviaciones por rubro, cuenta y mes. Un saldo negativo identifica exceso presupuestario.
6. Envíe el presupuesto a aprobación y apruébelo para bloquear los valores proyectados (los gastos reales siguen registrándose). Después puede registrar otro presupuesto para nuevos rubros de la misma empresa y año.

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

El módulo **no sustituye** la autenticación ni el transporte HTTP de `api_administrator`. En **Configuración API de gastos** solo se selecciona una API existente del modelo `api.administrator` mediante el campo **API existente**. No se crean ni se editan URL, usuario o contraseña desde Control de Gastos. La sincronización sigue llamando el método `call_api` existente.

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
- Las llamadas API utilizan la implementación de `call_api` presente en `api_administrator` (en el ejemplo, autenticación por cabeceras `userid/password`). No se almacena una copia de esas credenciales en el módulo presupuestario.

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

**Estados de presupuestos:** Borrador → Pendiente de aprobación → Aprobado. No hay estado Cerrado. Una vez aprobado un presupuesto, puede crearse otro para nuevos rubros de la misma empresa y año; no se admiten dos presupuestos en preparación a la vez para esa empresa y año ni la duplicación de cuenta/mes entre presupuestos. Al actualizar desde una versión anterior, los presupuestos cerrados se conservan como aprobados.

## Navegación por roles (v1.4.5)

- **Consulta:** Presupuestos, Proyectado vs. real y Gastos reales (solo lectura).
- **Registro de presupuestos:** exclusivamente los menús **Presupuestos** e **Importar Excel/CSV**. Conserva la edición de consumido en proyecciones, el envío a aprobar y Sincronizar API desde los presupuestos.
- **Aprobador de presupuestos:** **Aprobación de presupuestos** (solo pendientes de aprobación y aprobados; nunca borradores), **Proyectado vs. real** y **Gastos reales** (lectura).
- **Administrador de presupuestos:** todos los menús, incluyendo Presupuestos, Aprobación, Proyectado vs. real, Gastos reales, Configuración e Importar Excel/CSV.

La visibilidad de menús no cambia el cálculo presupuestario ni la API. Al actualizar desde versiones anteriores se limpia la pertenencia heredada al grupo Consulta para usuarios de Registro, Aprobador o Administrador; el acceso de lectura continúa gracias a un grupo técnico interno.


**Visibilidad del aprobador (v1.4.6):** tanto en la pestaña Aprobación de presupuestos como en Proyectado vs. real, solo puede consultar presupuestos y proyecciones en estado Pendiente de aprobación o Aprobado. La restricción también se aplica a accesos directos; el Administrador conserva todos los estados.


## Imprimir PDF desde Proyectado vs. real (v1.4.11)

1. Abra **Control de Gastos → Proyectado vs. real** (vista de lista).
2. Pulse **Imprimir PDF**. No necesita seleccionar filas: el asistente permite indicar **Empresa**, **Año** y opcionalmente **Rubro** y **Cuenta controlada**.
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
