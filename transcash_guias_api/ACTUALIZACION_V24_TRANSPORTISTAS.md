# Transcash Guías API 2.4 — Identidad de transportistas y limpieza segura

## Causa comprobada en el código 2.3

Se utilizaban **dos modelos** de transportistas:

- `tc.transport`: maestro auxiliar de la importación ERP, vinculado a `tc.guide`.
- `res.partner`: tercero operativo, usado en `transcash.guia.proveedor_id`, rutas, embarques, portal de transportistas y liquidaciones.

El código de sincronización no garantizaba una única identidad fiscal **global** en `res.partner` cuando existían registros de otra empresa, formatos diferentes o contactos antiguos sin RUC. Los datos originales contienen además la columna `proveedor` con identificaciones variables según producto; **esa columna no debe utilizarse como RUC del transportista**. Utilice exclusivamente `transportista.ruc` del JSON, cuyo origen ERP debe identificar realmente a la empresa transportista.

## Cambios

1. RUC del transportista normalizado (10 o 13 dígitos ecuatorianos, con o sin separadores o prefijo EC), sin crearlo desde `proveedor` ni desde el nombre.
2. Buscar en `res.partner` globalmente, activos y archivados; respetar contactos restringidos por compañía, bloquear insertos simultáneos por RUC mediante advisory lock.
3. Si existe el RUC, reutilizar el contacto activo; si hay varios se utiliza uno y se informa la anomalía.
4. Si el RUC no existe pero se encuentra exactamente **un** contacto de empresa con ese nombre y sin VAT, completar ese RUC y reutilizar el contacto. Cuando la identidad es ambigua, bloquear el alta y dejar observación, no crear más clones.
5. Si el JSON no tiene RUC, **no se crea un transportista**: solo puede reutilizarse uno existente cuando el nombre coincida de forma inequívoca.
6. `tc.transport` también utiliza RUC normalizado y bloqueo de importación por compañía.
7. Menú de limpieza en **Logística Transcash → Operación logística → Depurar transportistas (RUC)**: primero *Analizar transportistas por RUC* (sin modificaciones), luego opcionalmente *Depurar transportistas sin uso*.
8. La limpieza **archiva**, nunca elimina físicamente, contactos repetidos de `res.partner` SIN referencias. Registros con usuarios, guías, pagos, embarques, portal u otros vínculos quedan como incidencias para fusión administrativa. Los maestros auxiliares `tc.transport` duplicados y totalmente sin referencias se pueden eliminar.
9. Los nombres idénticos sin RUC se analizan de manera separada; únicamente se archivan contactos completamente sin uso y sin conflicto de código ERP. No se concluye identidad fiscal por nombre.

## Instalación

1. Respalde la base de datos y los addons instalados.
2. Actualice **solo** `transcash_guias_api` a 18.0.2.4.0, conservando `logistica_transcash` y su información operativa.
3. Reinicie Odoo y actualice Aplicaciones → `transcash_guias_api`.
4. Abra *Depurar transportistas (RUC)* y pulse *Analizar transportistas por RUC*. Revise los IDs y documentos reportados.
5. Si lo confirma, utilice *Depurar transportistas sin uso*; **no realiza fusión de historiales**.
6. Sincronice `getguiaslogistica` desde API Administrator dos veces y confirme que el conteo de `res.partner` por RUC normalizado permanece estable.
7. Revise las guías `tc.guide` con `master_link_note` pendiente: si falta `transportista.ruc`, corrija la salida del ERP antes de forzar relaciones.

## Alcance de la seguridad

La limpieza no altera el `proveedor_id` de guías, rutas, embarques o liquidaciones. Un duplicado con referencias se señala para fusión supervisada: archivarlo o eliminarlo sin reasignar correctamente las dependencias puede afectar al portal y a los pagos.

## Limitaciones

No es posible comprobar la cantidad real de duplicados ni qué contacto debe quedar como principal sin acceso a la base de datos. Los valores internacionales de identificación fiscal distintos de 10/13 dígitos requieren un campo/tipo de documento explícito y homologación manual; no se tratan automáticamente como RUC ecuatoriano.
