# Changelog

## 18.0.4.0.0
- Dashboard ejecutivo ampliado con margen por SIM, comisión por SIM, recuperación, maduración y capital sin recuperar.
- KPI "Pendiente potencial de Claro" sin compensar faltantes con sobrepagos de otras líneas.
- KPI territorial: zona que más genera, zona que menos genera y zona con mayor ROI.
- Participación de la zona líder y concentración Top 3 de zonas.
- Cobertura de mapeo territorial: SIM sin zona y porcentaje con zona asignada.
- Parámetro configurable por operador para días de madurez de SIM (90 por defecto para Claro).
- Base de costo de ROI configurable: costo, costo neto de descuento o costo neto + impuesto; recalculable sin reimportar.
- Región fuente de Claro usada como respaldo cuando el ICC aún no tiene región de Telecity mapeada.
- Reporte Región/Zona enriquecido con participación, comisión/margen por SIM, improductividad y capital maduro sin recuperar.
- Nueva vista gráfica de comisión recibida por zona y filtros de agrupación territorial.
- Accesos directos desde dashboard a rendimiento por zona y líneas con pendiente potencial.
- Cobertura de reglas y cantidad de líneas con diferencia para no interpretar un esperado incompleto como conciliación correcta.
- Índices compuestos para acelerar dashboard, recuperación y filtros de conciliación con volúmenes altos.
- Aplicación de mapeos Bodega/Zona procesada por ventanas de 5.000 registros para limitar memoria.
- Revalidación de columna `Valor` en P1/P2/P3: total fuente corregido/documentado a USD 113.021,18 aprox.

## 18.0.3.0.0
- Corrige instalación Odoo 18: botón del dashboard ya no llama `_compute` (método privado).
- Dashboard con método RPC público `action_refresh` y filtro por operador.
- ICC normalizable por longitud configurable de operador (Claro = 18).
- Operador agregado a lotes de compra y maestro de SIM.
- Mapeo Bodega -> Región/Zona reaplicable después de la carga.
- Porcentaje fuente y porcentaje normalizado separados.
- Recalculo masivo de liquidaciones mediante SQL por bloque.
- KPIs de SIM almacenados y refrescados masivamente.
- Patrón de producto y límites inclusivos/exclusivos parametrizables.
- Prevención de esquemas activos con vigencias superpuestas.
- Vistas de análisis, filtros de conciliación y trazabilidad ampliadas.
- Pruebas de lectura y cruce repetidas con los 4 archivos reales suministrados.
