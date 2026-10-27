-- SOLO LECTURA. Validar guía 5202 y su vinculación al transportista.
SELECT g.id AS id_importador, g.external_id, g.name AS guia,
       g.transport_name, g.transport_tax_raw,
       g.transport_partner_id AS contacto_odoo,
       p.name AS razon_social_contacto, p.vat AS documento_contacto,
       g.master_link_state, g.master_link_note,
       g.publication_state, g.publication_note
FROM tc_guide g
LEFT JOIN res_partner p ON p.id = g.transport_partner_id
WHERE g.external_id = '009-001-000005202' OR g.name = '5202'
ORDER BY g.id DESC;

-- Debe devolver como máximo un registro creado por el importador para ese documento.
SELECT id, name, vat, active, supplier_rank
FROM res_partner
WHERE UPPER(REGEXP_REPLACE(COALESCE(vat,''), '[^A-Za-z0-9]', '', 'g')) = '123456789'
ORDER BY id;

-- Contacto conectado a la guía operativa (solo si la guía ya está publicada).
SELECT g.id, g.name, g.external_id_erp,
       g.proveedor_id, p.name AS proveedor, p.vat AS identificacion
FROM transcash_guia g
LEFT JOIN res_partner p ON p.id = g.proveedor_id
WHERE g.external_id_erp = '009-001-000005202'
ORDER BY g.id DESC;
