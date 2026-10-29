# Transcash · Análisis de despachos para Odoo 18

Primera versión del módulo, con importación del exportador Excel y recepción de datos por la API externa autenticada de Odoo. Compatible por diseño con Odoo 18 Community y Enterprise en servidor propio u Odoo.sh. Requiere validación de instalación en la base de destino. Odoo Online no admite este módulo Python.

## Funcionalidad

- Tablero de facturas únicas: pendientes, parciales, vencidas, cumplimiento exigible, cumplimiento de despachadas, promedio, mediana y P90.
- Plazos por ciudad y condición de entrega, en días calendario o hábiles. Vigencia por fecha de factura y feriados configurables por compañía.
- Antigüedad de pendientes, peso, cajas y pallets pendientes. Priorización de vencidas y detalle por factura/bodega, con SKU si lo proporciona la fuente.
- Constructor de visuales de barras, líneas, distribución circular y tablas. Tableros personales o compartidos con la compañía y orden configurable.
- Tabla dinámica, gráficos, filtros favoritos y exportación estándar de Odoo.
- Importación XLSX en segundo plano, cortes históricos y activación del nuevo corte solo al terminar todos sus bloques.
- API por bloques con identificadores de lote y reintentos idempotentes.
- Perfiles Consulta, Operador y Responsable; reglas de acceso por compañía y tableros privados.

Las alertas son reglas de operación calculadas con los datos. El constructor ofrece indicadores y dimensiones definidos para despachos. No incluye DAX, relaciones entre fuentes arbitrarias, lenguaje natural ni el conjunto completo de funciones de Power BI.

## Base de esta entrega actualizada

Se usa exclusivamente `Analisis Despachos Trasncash(1).xlsx`: 54.392 registros por factura/bodega y 44.989 facturas distintas. El archivo no tiene SKU. La importación admite este consolidado y también el formato por producto/bodega cuando la fuente lo incluya.

Este archivo corrige las fechas: existen 17.743 registros con último despacho en un día distinto de la factura. El tiempo promedio observado es 1,65 días calendario para todas las modalidades y 9,28 días para Entrega Transcash. Estos promedios excluyen ajustes/devoluciones y observaciones de calidad. Ver el informe incluido para población, denominadores y límites.

No se han inventado plazos ni fechas. Inicialmente el cumplimiento aparece como **Sin medición** hasta configurar plazos.

## Instalación

1. Copiar la carpeta `transcash_dispatch_analysis` a una ruta de addons de Odoo 18. No cambiar el nombre técnico de la carpeta.
2. Reiniciar Odoo, actualizar la lista de aplicaciones e instalar **Transcash · Análisis de despachos**.
3. Asignar el perfil del módulo a los usuarios. El administrador de Odoo recibe Responsable al instalar.
4. Revisar Configuración → Fuentes y API. La fuente inicial `TRANSCASH` pertenece a la compañía principal; crear otra fuente para otra compañía cuando corresponda.
5. Configurar Plazos por ciudad y Feriados. Una ciudad vacía representa la regla general; modalidad vacía representa todas las modalidades.
6. Importar el Excel completo e indicar la fecha de extracción del exportador. Para el archivo recibido, el corte analizado es **29/10/2026**.
7. Consultar Importaciones e histórico hasta que el corte quede vigente. Los procesos cron de Odoo deben estar habilitados.
8. Si se cambian plazos después de importar, pulsar **Aplicar parámetros**. Se prepara otro corte con las reglas actuales y se mantiene el anterior como histórico.

Ejemplo desde una instalación con `odoo-bin`:

```bash
./odoo-bin -d base_prueba --addons-path=/ruta/odoo/addons,/ruta/custom_addons -i transcash_dispatch_analysis --stop-after-init
```

No requiere paquetes Python adicionales. El lector XLSX usa la biblioteca estándar. Admite una hoja visible, archivos de hasta 40 MiB, contenido expandido de hasta 300 MiB y 500.000 líneas. El archivo recibido tiene 8,16 MiB y 54.392 registros. El proxy HTTP debe permitir una carga de al menos 64 MiB para cubrir la representación base64 del tamaño máximo admitido.

## Primera revisión del tablero

El filtro inicial incluye todas las condiciones de entrega. Seleccionar **Entrega Transcash** para analizar exclusivamente esa modalidad. Los retiros de clientes siguen visibles y se pueden analizar por separado.

Una factura pendiente tiene al menos una línea con `Pendiente > 0,000001`. Una línea con saldo negativo no compensa el pendiente de otra línea. Se agrupa por `TipoFactura + NumeroFactura + Establecimiento` dentro de cada fuente/corte/compañía. Se conserva también la columna `Factura`; ambos identificadores se muestran para resolver su significado comercial con el sistema de origen.

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
