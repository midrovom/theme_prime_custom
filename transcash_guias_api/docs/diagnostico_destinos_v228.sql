-- Consulta SOLO LECTURA. Cambia la compañía (1) por la correcta.
-- 1. Duplicados físicos o normalizados en transcash.destino.
SELECT company_id,
       regexp_replace(upper(coalesce(codigo, '')), '[^A-Z0-9]', '', 'g') AS codigo_comparable,
       COUNT(*) AS fichas,
       array_agg(id ORDER BY id) AS ids,
       array_agg(codigo ORDER BY id) AS codigos
FROM transcash_destino
WHERE company_id = 1
GROUP BY company_id, regexp_replace(upper(coalesce(codigo, '')), '[^A-Z0-9]', '', 'g')
HAVING COUNT(*) > 1;

-- 2. Código/ciudad del ERP y vínculo con la guía operativa.
SELECT s.external_id, s.name AS guia, s.destination_code_erp,
       s.destination_city, d.codigo AS codigo_maestro, d.name AS destino,
       d.ciudad AS ciudad_maestro, g.destino AS destino_en_guia,
       g.destino_codigo AS codigo_en_guia, g.destino_ciudad AS ciudad_en_guia,
       g.hoja_ruta_id, g.embarque_id
FROM tc_guide s
LEFT JOIN transcash_guia g ON g.company_id=s.company_id AND g.external_id_erp=s.external_id
LEFT JOIN transcash_destino d ON d.id=g.destino_id
WHERE s.company_id = 1
ORDER BY s.id DESC LIMIT 100;

-- 3. Guías libres cuyo código difiere de su ficha de destino.
SELECT g.name, g.external_id_erp, g.destino, g.destino_codigo,
       d.codigo AS codigo_catalogo
FROM transcash_guia g
LEFT JOIN transcash_destino d ON d.id=g.destino_id
WHERE g.company_id = 1 AND g.state='registrada'
  AND g.hoja_ruta_id IS NULL AND g.embarque_id IS NULL
  AND g.destino IS DISTINCT FROM g.destino_codigo
ORDER BY g.id DESC LIMIT 100;
