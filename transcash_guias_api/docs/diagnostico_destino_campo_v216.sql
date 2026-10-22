-- Consultas de solo lectura para verificar la v2.16.
-- Comparar el campo destino literal de la guía con el código ERP del destino elegido en la ruta.
SELECT g.id, g.name AS numero_guia,
       g.destino AS destino_operativo_guia,
       g.destino_codigo AS destino_codigo_historico_no_usado,
       dg.codigo AS codigo_maestro_vinculado_no_usado,
       g.state AS estado_guia,
       g.hoja_ruta_id, g.embarque_id
FROM transcash_guia AS g
LEFT JOIN transcash_destino AS dg ON dg.id = g.destino_id
WHERE g.name = '32799';

-- Cambia 'ID_RUTA' por el id numérico de la hoja de ruta en Odoo.
-- SELECT r.id, r.name, d.codigo AS codigo_erp_destino_ruta
-- FROM transcash_hoja_ruta AS r
-- JOIN transcash_destino AS d ON d.id = r.destino_id
-- WHERE r.id = ID_RUTA;
-- Regla del filtro: normalizar(g.destino) = normalizar(d.codigo).
