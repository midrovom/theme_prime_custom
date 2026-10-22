-- DIAGNOSTICO PWA v2.7: SOLO LECTURA, sin modificar movimientos.
-- Sustituir los identificadores reales de compañía/hoja de ruta al consultar.
-- Guías operativas con relación a su fuente de importación ERP.
SELECT g.id, g.name AS guia, g.company_id, g.state,
       g.hoja_ruta_id, g.embarque_id,
       g.chofer_usuario_id, g.chofer_contacto_id, g.ruc_chofer,
       g.proveedor_id, rp.vat AS ruc_transportista_odoo,
       g.destino_id, g.destino_codigo, g.destino_ciudad,
       s.id AS guia_erp_id, s.transport_name,
       s.transport_tax_raw, s.driver_partner_id, s.driver_user_id,
       s.destination_city, s.destination_address
FROM transcash_guia g
LEFT JOIN tc_guide s ON s.company_id = g.company_id
                    AND (s.operational_guide_id = g.id OR
                         (s.operational_guide_id IS NULL AND s.external_id = g.external_id_erp))
LEFT JOIN res_partner rp ON rp.id = g.proveedor_id
ORDER BY g.id DESC
LIMIT 200;

-- Resumen por compañía para encontrar el filtro que reduce la lista.
SELECT company_id,
       COUNT(*) AS total_guias,
       COUNT(*) FILTER (WHERE state='registrada' AND hoja_ruta_id IS NULL AND embarque_id IS NULL) AS libres,
       COUNT(*) FILTER (WHERE state='registrada' AND hoja_ruta_id IS NULL AND embarque_id IS NULL AND chofer_usuario_id IS NULL) AS libres_sin_usuario_chofer,
       COUNT(*) FILTER (WHERE state='registrada' AND hoja_ruta_id IS NULL AND embarque_id IS NULL AND proveedor_id IS NULL) AS libres_sin_transportista,
       COUNT(*) FILTER (WHERE state='registrada' AND hoja_ruta_id IS NULL AND embarque_id IS NULL AND destino_id IS NULL) AS libres_sin_destino_maestro
FROM transcash_guia
GROUP BY company_id ORDER BY company_id;
