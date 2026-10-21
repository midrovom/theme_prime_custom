-- TRANSCASH BI · VERIFICACIÓN INDEPENDIENTE CON DATOS REALES
-- Ajusta 2026-10-01 y 2026-10-21 y company_id = 1 a tu empresa / periodo.
-- Lectura exclusivamente. No modifica datos.

-- 1. Guías registradas en el periodo
SELECT count(*) AS guias
FROM transcash_guia g
WHERE g.company_id = 1
  AND g.create_date >= '2026-10-01'::timestamp
  AND g.create_date <  '2026-10-21'::timestamp;

-- 2. Incidencias y roturas: conteos distintos
WITH guia_danos AS (
    SELECT g.id, g.proveedor_id, g.chofer_usuario_id,
           COALESCE(g.destino_codigo, g.destino_ciudad, g.destino, 'Sin destino') AS destino,
           g.incidencia_estado, g.resultado_recepcion,
           count(r.id) AS reportes,
           count(r.id) FILTER (WHERE r.estado = 'pendiente') AS pendientes,
           count(r.id) FILTER (WHERE r.estado = 'aprobada') AS aprobadas,
           coalesce(sum(r.cantidad) FILTER (WHERE l.unidad = 'm2'), 0) AS m2_danados,
           coalesce(sum(r.cantidad) FILTER (WHERE l.unidad = 'unidad'), 0) AS unidades_danadas
    FROM transcash_guia g
    LEFT JOIN transcash_rotura r ON r.guia_id = g.id AND r.estado <> 'rechazada'
    LEFT JOIN transcash_guia_linea l ON l.id = r.linea_id
    WHERE g.company_id = 1
      AND g.create_date >= '2026-10-01'::timestamp
      AND g.create_date <  '2026-10-21'::timestamp
    GROUP BY g.id, g.proveedor_id, g.chofer_usuario_id,
             g.destino_codigo, g.destino_ciudad, g.destino,
             g.incidencia_estado, g.resultado_recepcion
)
SELECT count(*) AS guias,
       count(*) FILTER (WHERE reportes > 0) AS guias_con_roturas,
       sum(reportes) AS reportes_rotura,
       sum(pendientes) AS reportes_pendientes,
       sum(aprobadas) AS reportes_aprobados,
       count(*) FILTER (WHERE incidencia_estado <> 'ninguna'
                      OR resultado_recepcion = 'con_novedades'
                      OR reportes > 0) AS guias_con_incidencias,
       sum(m2_danados) AS m2_danados,
       sum(unidades_danadas) AS unidades_danadas
FROM guia_danos;

-- 3. Roturas e incidencias por transportista
WITH hechos AS (
    SELECT g.id AS guia_id, g.proveedor_id,
           g.incidencia_estado, g.resultado_recepcion,
           count(r.id) AS reportes
    FROM transcash_guia g
    LEFT JOIN transcash_rotura r ON r.guia_id = g.id AND r.estado <> 'rechazada'
    WHERE g.company_id = 1
      AND g.create_date >= '2026-10-01'::timestamp
      AND g.create_date <  '2026-10-21'::timestamp
    GROUP BY g.id
)
SELECT coalesce(p.name::text, 'Sin transportista') AS transportista,
       count(*) AS guias,
       sum(h.reportes) AS reportes_rotura,
       count(*) FILTER (WHERE h.incidencia_estado <> 'ninguna'
                      OR h.resultado_recepcion = 'con_novedades'
                      OR h.reportes > 0) AS guias_con_incidencia
FROM hechos h
LEFT JOIN res_partner p ON p.id = h.proveedor_id
GROUP BY p.id, p.name
ORDER BY reportes_rotura DESC, guias DESC;
