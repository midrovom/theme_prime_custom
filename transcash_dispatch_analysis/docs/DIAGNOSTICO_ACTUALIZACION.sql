-- Solo lectura. Ejecutar en la base correcta con un usuario administrador.
-- La version persistida por Odoo se guarda en latest_version.
SELECT name, state, latest_version AS version_instalada
FROM ir_module_module
WHERE name = 'transcash_dispatch_analysis';

-- El cron del modulo solo toma queued/loading; ready/archived son cortes terminados.
SELECT state, count(*) AS cortes
FROM dispatch_snapshot
GROUP BY state
ORDER BY state;

-- Consultas activas, tiempo de transaccion y bloqueadores. No cancela sesiones.
SELECT pid, state,
       now() - xact_start AS tiempo_transaccion,
       now() - query_start AS tiempo_consulta,
       wait_event_type, wait_event,
       pg_blocking_pids(pid) AS bloqueadores,
       left(query, 500) AS consulta
FROM pg_stat_activity
WHERE datname = current_database()
  AND pid <> pg_backend_pid()
  AND state <> 'idle'
ORDER BY query_start
LIMIT 20;
