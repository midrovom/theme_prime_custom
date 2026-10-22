-- SOLO LECTURA: contactos de empresas duplicados por RUC normalizado.
WITH claves AS (
  SELECT id, name, active, vat, company_id,
         UPPER(REGEXP_REPLACE(COALESCE(vat, ''), '[^A-Za-z0-9]', '', 'g')) AS ruc_raw
    FROM res_partner
   WHERE is_company IS TRUE
), normalizados AS (
  SELECT *, CASE WHEN LEFT(ruc_raw, 2) = 'EC' AND LENGTH(ruc_raw) IN (12,15)
                 THEN SUBSTRING(ruc_raw FROM 3) ELSE ruc_raw END AS ruc_normalizado
  FROM claves
)
SELECT ruc_normalizado, COUNT(*) AS contactos,
       ARRAY_AGG(id ORDER BY id) AS ids_contactos,
       ARRAY_AGG(name ORDER BY id) AS nombres
FROM normalizados
WHERE active IS TRUE AND ruc_normalizado ~ '^[0-9]+$'
  AND LENGTH(ruc_normalizado) IN (10,13)
GROUP BY ruc_normalizado
HAVING COUNT(*) > 1
ORDER BY contactos DESC, ruc_normalizado;

-- SOLO LECTURA: maestros auxiliares de transportistas con RUC duplicado
WITH t AS (
 SELECT id, company_id, name, ruc,
        UPPER(REGEXP_REPLACE(COALESCE(ruc, ''), '[^A-Za-z0-9]', '', 'g')) AS ruc_normalizado
 FROM tc_transport
)
SELECT company_id, ruc_normalizado, COUNT(*) AS cantidad, ARRAY_AGG(id ORDER BY id) AS ids
FROM t
WHERE LENGTH(ruc_normalizado) IN (10,13)
GROUP BY company_id, ruc_normalizado
HAVING COUNT(*) > 1
ORDER BY cantidad DESC;
