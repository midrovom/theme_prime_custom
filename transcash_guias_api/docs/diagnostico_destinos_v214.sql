-- Solo lectura: comprueba los CÓDIGOS detrás del nombre visible.
-- Ajustar nombre/documento si se consulta otra guía.
SELECT
    g.id AS guia_id, g.name AS numero_guia, g.numero_documento,
    g.destino AS texto_guia, g.destino_codigo AS codigo_guardado_guia,
    g.destino_id, d.name AS nombre_catalogo_guia,
    d.codigo AS codigo_catalogo_guia,
    g.hoja_ruta_id, r.name AS nombre_hoja,
    r.destino_id AS destino_hoja_id,
    dr.name AS nombre_destino_hoja,
    dr.codigo AS codigo_destino_hoja
FROM transcash_guia g
LEFT JOIN transcash_destino d ON d.id = g.destino_id
LEFT JOIN transcash_hoja_ruta r ON r.id = g.hoja_ruta_id
LEFT JOIN transcash_destino dr ON dr.id = r.destino_id
WHERE g.name = '32799' OR g.numero_documento = 'TR-53965'
ORDER BY g.id;
