# Transcash Guías API v2.25 — Transportista extranjero sin duplicados

## Problema

Guía ERP `009-001-000005202` / 5202, documento DS-400471:
- Nombre: `TRANSPORTE PROPORCIONADO POR CLIENTE`
- Identificación: `123456789` (9 dígitos)
- En la versión anterior la ficha `Transportista Odoo` podía quedar vacía.

Causa: si ya había un `res.partner` con el mismo nombre y otra identificación, el importador detenía la creación aunque el documento fuera distinto. Ese nombre es genérico y puede repetirse legítimamente con varios números de identificación. Se corrigió también la importación de `ValidationError` en `partner_link.py`, necesaria para el reintento del documento fiscal.

## Nueva regla

1. Buscar `res.partner` por documento normalizado (`vat`), incluyendo contactos inactivos, antes de crear.
2. Si ya existe, reutilizar; si está archivado o pertenece privadamente a otra empresa, **no** crear duplicado: dejar incidencia para revisión.
3. Documentos de 13 dígitos: intentar RUC y usar identificación extranjera si la validación fiscal falla.
4. Documentos de otros tamaños, como `123456789`: crear como **Identificación extranjera** si Odoo tiene configurado ese tipo.
5. Un contacto con igual nombre pero documento diferente **no** impide crear el contacto del nuevo documento ni se reutiliza por error.
6. Si el nombre es `TRANSPORTE PROPORCIONADO POR CLIENTE`, no completar automáticamente el documento de otro contacto homónimo que tenga `vat` vacío.
7. La sincronización sigue asociando el contacto resuelto al `transport_partner_id` de `tc.guide` y al `proveedor_id` de `transcash.guia` cuando la guía permite actualizar su asignación, respetando los embarques existentes.

## Cómo corregir guías ya importadas

Actualizar el complemento. Después abrir **Guías importadas ERP → 5202 → Conciliar terceros y portales**, o ejecutar la sincronización `getguiaslogistica` (que también concilia y publica). Verificar `Transportista Odoo`.

Si permanece vacío, revisar **Pendientes / observaciones de accesos** y **Publicación**. La localización fiscal debe disponer de **Identificación extranjera**; de lo contrario Odoo impedirá crear un contacto con clasificación fiscal correcta.

## Verificación en PostgreSQL

Ejecutar `docs/diagnostico_transportista_5202_v225.sql` (solo lectura). Dos sincronizaciones seguidas deben devolver el mismo `res.partner.id` sin generar otro contacto con documento `123456789`.

## Límites

No modifica ni fusiona contactos históricos, no crea cuentas Portal del transportista, no cambia proveedores ya asignados a rutas o embarques cerrados y no toca `logistica_transcash`, la PWA o el dashboard.
