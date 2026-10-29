# Transcash · Análisis de despachos para Odoo 18

Versión 18.0.1.5.0 del módulo, con importación del exportador Excel y recepción de datos por la API externa autenticada de Odoo. Compatible por diseño con Odoo 18 Community y Enterprise en servidor propio u Odoo.sh. Requiere validación de instalación en la base de destino. Odoo Online no admite este módulo Python.

## Registros únicos y bodegas múltiples 1.5

La llave comercial es **TipoFactura + NumeroFactura** por compañía. Una sola versión vigente entra en los totales, incluso con dos cargas del mismo Excel o fuentes superpuestas. Se conservan las versiones históricas separadas. El selector admite varias bodegas y recalcula sus toneladas y pendientes; la contratación usa únicamente el saldo pendiente. Se añaden toneladas despachadas y facturadas conocidas, resumen de vehículos por destino y un análisis nativo de bodegas con Favoritos de Odoo. La actualización completa los datos existentes; no requiere subir el archivo otra vez. Consultar `docs/UNICOS_BODEGAS_V1_5.md` y ejecutar **Validar / consolidar duplicados** para revisar la base instalada.

## Cumplimiento, toneladas y vehículos 1.4

El tablero muestra el cumplimiento del rango de fechas aplicado y las toneladas pendientes. El plan por ciudad y bodega de origen estima viajes, días de trabajo, tipos de vehículo, flota requerida y contratación adicional. Se pueden editar las capacidades, utilización, plazo objetivo, vehículos asignados y viajes completos por día, tanto en general como por destino. El plan comienza en Entrega Transcash y señala datos sin peso válido. Ver `docs/PLANIFICACION_V1_4.md` para fórmulas, actualización y supuestos. Las capacidades iniciales son ejemplos editables; no representan la flota real.

## Corrección de importación 1.2

Esta versión abre una pantalla que procesa los bloques y muestra su avance, sin depender del cron mientras esté abierta. Para continuar un Excel ya cargado, ir a Importaciones e histórico → Procesar / ver progreso. Ver `docs/CORRECCION_IMPORTACION_V1_2.md` para la actualización y recuperación de cargas en cola.

## Ciudades y plazos automáticos 1.3

Al importar por Excel o API se crean los plazos de las ciudades detectadas: **9 días calendario para todas y 3 para Guayaquil**. Los valores iniciales se aplican desde esa misma importación. Se pueden editar en **Configuración → Plazos por ciudad**; nuevas importaciones y actualizaciones del módulo conservan los cambios. Al actualizar también se completan las ciudades de las facturas ya importadas. Para recalcular un corte terminado, usar **Aplicar parámetros** y mantener abierta la pantalla de progreso. Ver `docs/CIUDADES_AUTOMATICAS_V1_3.md`.

## Funcionalidad

- Tablero de facturas únicas: pendientes, parciales, vencidas, cumplimiento exigible, cumplimiento de despachadas, promedio, mediana y P90.
- Ciudades creadas al importar, con plazos iniciales editables: 9 días calendario; Guayaquil, 3. Plazos por ciudad y condición de entrega, en días calendario o hábiles. Vigencia por fecha de factura y feriados configurables por compañía.
- Antigüedad de pendientes, peso, cajas y pallets pendientes. Priorización de vencidas y detalle por factura/bodega, con SKU si lo proporciona la fuente.
- Toneladas pendientes como KPI y medida de análisis; planificación por destino con capacidades y ciclos configurables.
- Constructor de visuales de barras, líneas, distribución circular y tablas. Tableros personales o compartidos con la compañía y orden configurable.
- Tabla dinámica, gráficos, filtros favoritos y exportación estándar de Odoo.
- Importación XLSX por bloques con progreso en pantalla, respaldo por cron, cortes históricos y activación del nuevo corte solo al terminar todos sus bloques.
- API por bloques con identificadores de lote y reintentos idempotentes.
- Perfiles Consulta, Operador y Responsable; reglas de acceso por compañía y tableros privados.

Las alertas son reglas de operación calculadas con los datos. El constructor ofrece indicadores y dimensiones definidos para despachos. No incluye DAX, relaciones entre fuentes arbitrarias, lenguaje natural ni el conjunto completo de funciones de Power BI.

## Base de esta entrega actualizada

Se usa exclusivamente `Analisis Despachos Trasncash(1).xlsx`: 54.392 registros por factura/bodega y 44.989 facturas distintas. El archivo no tiene SKU. La importación admite este consolidado y también el formato por producto/bodega cuando la fuente lo incluya.

Este archivo corrige las fechas: existen 17.743 registros con último despacho en un día distinto de la factura. El tiempo promedio observado es 1,65 días calendario para todas las modalidades y 9,28 días para Entrega Transcash. Estos promedios excluyen ajustes/devoluciones y observaciones de calidad. Ver el informe incluido para población, denominadores y límites.

Los plazos iniciales siguen la instrucción de negocio: 9 días calendario y 3 para Guayaquil. El cumplimiento se calcula con esos plazos, salvo donde existan reglas personalizadas, datos no evaluables o vigencias que no cubran la factura.

## Instalación

1. Copiar la carpeta `transcash_dispatch_analysis` a una ruta de addons de Odoo 18. No cambiar el nombre técnico de la carpeta.
2. Reiniciar Odoo, actualizar la lista de aplicaciones e instalar **Transcash · Análisis de despachos**.
3. Asignar el perfil del módulo a los usuarios. El administrador de Odoo recibe Responsable al instalar.
4. Revisar Configuración → Fuentes y API. La fuente inicial `TRANSCASH` pertenece a la compañía principal; crear otra fuente para otra compañía cuando corresponda.
5. Revisar Plazos por ciudad: Guayaquil inicia con 3 días y las otras ciudades se crearán con 9 al importar. Se pueden modificar días, calendario y vigencias. Una ciudad vacía representa la regla general; modalidad vacía representa todas las modalidades. Los feriados se configuran si se opta por días hábiles.
6. Importar el Excel completo e indicar la fecha de extracción del exportador. Para el archivo recibido, el corte analizado es **29/10/2026**.
7. Mantener abierta la pantalla de progreso hasta que termine. Para retomar una carga anterior, usar Importaciones e histórico → Procesar / ver progreso. El cron es un respaldo; la pantalla procesa los bloques aunque el cron no esté habilitado.
8. Si se cambian plazos después de importar, pulsar **Aplicar parámetros**. Se prepara otro corte con las reglas actuales y se mantiene el anterior como histórico.

Ejemplo desde una instalación con `odoo-bin`:

```bash
./odoo-bin -d base_prueba --addons-path=/ruta/odoo/addons,/ruta/custom_addons -i transcash_dispatch_analysis --stop-after-init
```

Después de reemplazar una versión ya instalada, reiniciar Odoo, actualizar el módulo desde Aplicaciones y recargar el navegador con Ctrl+F5.

No requiere paquetes Python adicionales. El lector XLSX usa la biblioteca estándar. Admite una hoja visible, archivos de hasta 40 MiB, contenido expandido de hasta 300 MiB y 500.000 líneas. El archivo recibido tiene 8,16 MiB y 54.392 registros. El proxy HTTP debe permitir una carga de al menos 64 MiB para cubrir la representación base64 del tamaño máximo admitido.

## Primera revisión del tablero

El filtro inicial incluye todas las condiciones de entrega. Seleccionar **Entrega Transcash** para analizar exclusivamente esa modalidad. Los retiros de clientes siguen visibles y se pueden analizar por separado.

Una factura pendiente tiene al menos una línea con `Pendiente > 0,000001`. Una línea con saldo negativo no compensa el pendiente de otra línea. Se identifica por `TipoFactura + NumeroFactura` dentro de la compañía, conservando todas sus bodegas y productos distintos como detalle. Establecimiento y la columna Factura son descriptivos. Las fuentes y cortes conservan versiones; solo la observación vigente más reciente de esa llave entra en la operación.

Las facturas con registros de más de una bodega se agrupan en **VARIAS BODEGAS** para no duplicarlas. Las bodegas originales se conservan en el detalle de origen. No se suman cantidades heterogéneas de productos para fabricar un porcentaje de despacho.

El archivo actualizado está consolidado por bodega. Los cierres se evalúan al nivel recibido; no se puede demostrar cobertura de cada SKU ni reconstruir saldos positivos que ya se hayan compensado dentro del consolidado. Para ese control, la API debe proporcionar el detalle por producto.

## API

Leer `docs/CONTRATO_API.md`. El archivo `examples/push_api.py` envía un exportador JSON/JSONL mediante XML-RPC autenticado con API key. Las credenciales se leen de variables de entorno.

La primera versión recibe **cortes completos**, no eventos incrementales. Una carga parcial de la fuente no se debe finalizar como si fuera un corte completo. El conector que lea tu API origen y su programación se debe adaptar con su documentación, identificadores, ejemplo de respuesta y frecuencia de actualización. No hay un conector específico a tu ERP conectado todavía.

Cada corte conserva facturas, líneas y archivo original. Los bloques preparados temporales se eliminan tras la activación. Si se requiere actualización de alta frecuencia, definir con el conector la retención y/o la sincronización incremental antes de programar cargas recurrentes.

## Pruebas

Las pruebas de cálculos se pueden ejecutar sin Odoo:

```bash
python3 -m unittest discover -s transcash_dispatch_analysis/tests -p '*standalone.py'
```

Para las pruebas de integración incluidas, ejecutar en una base de prueba Odoo 18:

```bash
./odoo-bin -d base_prueba --addons-path=/ruta/odoo/addons,/ruta/custom_addons -i transcash_dispatch_analysis --test-enable --test-tags /transcash_dispatch_analysis --stop-after-init
```

La entrega no implica que se haya instalado el módulo en un servidor Odoo. Ver `docs/VALIDACION.md` para los controles realizados y pendientes.

## Referencias técnicas oficiales

- [Acciones de cliente Odoo 18](https://www.odoo.com/documentation/18.0/developer/howtos/javascript_client_action.html)
- [ORM Odoo 18](https://www.odoo.com/documentation/18.0/developer/reference/backend/orm.html)
- [Acciones programadas y procesamiento por bloques](https://www.odoo.com/documentation/18.0/developer/reference/backend/actions.html)
- [Seguridad de Odoo 18](https://www.odoo.com/documentation/18.0/developer/reference/backend/security.html)
- [API externa y API keys](https://www.odoo.com/documentation/18.0/developer/reference/external_api.html)
- [Restricciones de módulos Python en Odoo Online](https://www.odoo.com/documentation/18.0/developer/howtos/upgrade_custom_db.html)
