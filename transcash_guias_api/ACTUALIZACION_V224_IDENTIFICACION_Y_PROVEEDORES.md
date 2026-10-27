# Transcash Guías API v2.24 — Contactos por documento sin duplicados

## Alcance

Esta versión SOLO cambia la identificación y creación de contactos durante la sincronización de `getguiaslogistica` desde `api.administrator`, más la normalización del maestro auxiliar de choferes. No modifica el módulo `logistica_transcash`, PWA, rutas, dashboard, liquidaciones ni precios.

- **Proveedor de transporte al que se paga** (`res.partner`, asignado a `tc.guide.transport_partner_id` y, en la publicación, a `transcash.guia.proveedor_id`): se busca por identificación normalizada global, incluyendo archivados y contactos de otras compañías. Un contacto restringido a otra compañía o archivado se marca pendiente y **no se duplica**.
- 13 dígitos: se intenta registrar con tipo **RUC**; si falla la validación de Odoo, se vuelve a intentar **Identificación extranjera**, manteniendo exactamente el mismo número. No se elude la validación fiscal de Odoo.
- Otros formatos explícitamente proporcionados en `transportista.ruc` (p. ej. 11 dígitos): se registran como **Identificación extranjera**, si el tipo está configurado.
- Si existe un transportista con el mismo nombre, activo y sin documento y es una coincidencia inequívoca, se completa su documento y se reutiliza el registro. Nunca se sustituye un documento distinto.
- `supplier_rank` se activa cuando lo proporciona el módulo de contabilidad; no se crean cuentas Portal de transportistas automáticamente.
- **Chofer**: se busca también por cédula normalizada; no se crean contactos ni maestros auxiliares repetidos por guiones o espacios. Para 10 dígitos se intenta Cédula; para otros formatos, identificación extranjera. El flujo de acceso Portal permanece como estaba.
- Las referencias ERP de **proveedor de producto** siguen en los modelos comerciales privados. No se usan como RUC del transportista a pagar.

## Requisitos / limitaciones fiscales

Para etiquetar una identificación como extranjera, Odoo debe disponer del campo `res.partner.l10n_latam_identification_type_id` y del catálogo de Ecuador con un tipo de identificación extranjera. El complemento **no instala fiscalidad nueva automáticamente**. Si falta ese tipo, informa la incidencia en la sincronización y no crea un contacto con clasificación incorrecta. Revise Contabilidad > Configuración > Tipos de identificación.

La clasificación como identificación extranjera permite conservar el documento para la operación, pero **no equivale a un RUC validado por el SRI** ni garantiza que ese contacto esté apto para facturación electrónica o retenciones. Contabilidad debe revisar el documento antes de facturar o pagar.

## Instalación

1. Respalde PostgreSQL y la carpeta `transcash_guias_api`.
2. Reemplace la carpeta por la del ZIP v2.24.
3. Reinicie Odoo y actualice `transcash_guias_api`.
4. Sincronice dos veces `getguiaslogistica` y confirme que no aumenta el número de contactos con el mismo documento.
5. Ejecute `docs/revision_contactos_v224.sql` en PostgreSQL para detectar duplicados históricos. Use la opción ya existente de **Revisar terceros duplicados** para inspeccionar contactos; no haga eliminaciones automáticas con relaciones contables.

## Pruebas

`python tests/test_fiscal_v224.py` ejecuta casos sin base Odoo (RUC correcto, RUC rechazado, identificación extranjera, chofer/cédula, normalización y ausencia del tipo fiscal).

**Importante:** la instalación y validación con datos reales deben realizarse primero en una copia de la base de producción.
