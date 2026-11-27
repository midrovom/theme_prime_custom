-- PostgreSQL / Odoo: diagnóstico de lectura para el módulo 18.0.1.5.0.
-- No elimina ni modifica información. Cada compañía tiene su propio universo.

SELECT company_id,
       count(*) FILTER (WHERE is_current) AS facturas_vigentes,
       count(*) FILTER (WHERE snapshot_state='archived') AS versiones_historicas,
       count(*) AS versiones_almacenadas
FROM dispatch_invoice
GROUP BY company_id;

-- Este resultado debe estar vacío para los datos vigentes.
SELECT company_id, invoice_type, internal_number, count(*) AS repeticiones
FROM dispatch_invoice
WHERE is_current
GROUP BY company_id, invoice_type, internal_number
HAVING count(*) > 1;

-- Una factura puede tener varias versiones históricas legítimas.
SELECT s.id, s.name, s.file_name, s.state, s.cutoff_date,
       count(i.id) AS facturas_del_corte,
       count(i.id) FILTER (WHERE i.is_current) AS facturas_vigentes_de_ese_corte
FROM dispatch_snapshot s
LEFT JOIN dispatch_invoice i ON i.snapshot_id=s.id
GROUP BY s.id,s.name,s.file_name,s.state,s.cutoff_date
ORDER BY s.cutoff_date DESC,s.id DESC;

SELECT i.company_id,
       sum(i.pending_weight) FILTER (WHERE i.pending) / 1000.0 AS toneladas_pendientes,
       sum(i.dispatched_weight) / 1000.0 AS toneladas_despachadas,
       sum(i.invoiced_weight) / 1000.0 AS toneladas_facturadas_conocidas,
       sum(i.invoiced_weight_missing_rows) AS renglones_sin_peso_facturado_completo
FROM dispatch_invoice i
WHERE i.is_current
GROUP BY i.company_id;
