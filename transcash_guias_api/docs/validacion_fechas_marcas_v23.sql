-- CONSULTAS DE SOLO LECTURA PARA LA v2.3.
-- Realizar DESPUES de actualizar transcash_guias_api; el nuevo campo operacional
-- en tabla privada no existira antes de la migracion.

-- 1) Guías importadas vs operativas: fechas originales y publicadas.
SELECT e.external_id, e.name AS guia,
       e.erp_start_date, e.erp_end_date, e.erp_planned_date,
       o.fecha_inicio_traslado, o.fecha_fin_traslado, o.fecha_prevista,
       o.state, o.hoja_ruta_id, o.embarque_id
FROM tc_guide e
LEFT JOIN transcash_guia o
       ON o.company_id=e.company_id AND o.external_id_erp=e.external_id
ORDER BY e.id DESC LIMIT 100;

-- 2) Marcas/proveedores vinculados a la línea operativa de la guía.
SELECT g.name AS guia, ol.codigo AS sku,
       p.brand_code_raw, p.brand_name_raw, b.code AS marca_maestro,
       p.supplier_code_raw, p.supplier_name_raw, s.external_code AS proveedor_maestro,
       p.operational_line_id
FROM tc_guide_line_private p
JOIN tc_guide_line el ON el.id=p.line_id
JOIN tc_guide e ON e.id=el.guide_id
LEFT JOIN transcash_guia_linea ol ON ol.id=p.operational_line_id
LEFT JOIN transcash_guia g ON g.id=ol.guia_id
LEFT JOIN tc_product_brand b ON b.id=p.brand_id
LEFT JOIN tc_product_supplier s ON s.id=p.supplier_id
ORDER BY p.id DESC LIMIT 100;

-- 3) Fichas comerciales que aun necesitan reconciliarse.
SELECT e.external_id, el.external_line_id, el.sku,
       p.brand_code_raw, p.supplier_code_raw
FROM tc_guide_line_private p
JOIN tc_guide_line el ON el.id=p.line_id
JOIN tc_guide e ON e.id=el.guide_id
WHERE p.operational_line_id IS NULL
ORDER BY e.id DESC LIMIT 100;
