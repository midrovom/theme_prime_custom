-- Transcash Guías API v2.24
-- Solo lectura: comprobar contactos duplicados por documento normalizado.
-- Ejecutar en PostgreSQL con la base Odoo correcta.
WITH documentos AS (
  SELECT id, name, active, vat, company_id,
         CASE
           WHEN LEFT(doc, 2) = 'EC' AND SUBSTRING(doc FROM 3) ~ '^[0-9]{10}([0-9]{3})?$'
           THEN SUBSTRING(doc FROM 3)
           ELSE doc
         END AS identificacion
  FROM (
    SELECT id, name, active, vat, company_id,
           UPPER(REGEXP_REPLACE(COALESCE(vat, ''), '[^A-Za-z0-9]', '', 'g')) AS doc
    FROM res_partner
  ) raw
)
SELECT identificacion, COUNT(*) AS contactos,
       STRING_AGG(CONCAT(id, ': ', name, ' (activo=', active, ')'), ' | ' ORDER BY id) AS registros
FROM documentos
WHERE LENGTH(identificacion) >= 5
GROUP BY identificacion
HAVING COUNT(*) > 1
ORDER BY contactos DESC, identificacion;

-- Guías importadas donde aún no se ha podido asociar el transportista a pagar:
SELECT g.external_id, g.name AS numero_guia, g.transport_name,
       g.transport_tax_raw, g.master_link_state, g.master_link_note
FROM tc_guide g
WHERE g.transport_partner_id IS NULL
ORDER BY g.id DESC
LIMIT 100;
