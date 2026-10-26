# Dashboard BI – Flota contratada (v2.20)

## Origen de los datos

- Modelo: `transcash.embarque` (registro = viaje; se excluyen cancelados).
- Clasificación: `transcash.embarque.tipo_vehiculo` (camión, mula, furgón, camioneta, otro).
- Peso documental: líneas vigentes de `transcash.guia.linea.peso_kg`, con respaldo a `transcash.guia.peso_kg` cuando las líneas no traigan peso, igual que los KPI anteriores.
- Salida real: `transcash.embarque.fecha_salida` informada.
- Filtro de fecha: idéntico al dashboard existente. Con fecha prevista, embarques siguen filtrándose por creación porque el campo previsto es calculado sin almacenamiento. Para medir salidas ocurridas estrictamente dentro del intervalo, seleccionar «Salida real»; con «Registro» se agrupan embarques creados en el intervalo que ya tengan salida registrada, incluso si esta ocurrió después.

## Criterios

- **Viajes contratados:** conteo de embarques no cancelados en el periodo.
- **Viajes realizados:** conteo de los anteriores con fecha real de salida.
- **Kg programados:** kg documentales de guías de los embarques no cancelados, con o sin salida.
- **Kg transportados:** kg documentales de guías de los embarques con salida real. No son pesos certificados por báscula.
- **Kg promedio por salida:** kg transportados / viajes realizados; 0 si no hay salidas.
- **Tipo sin registrar:** embarques históricos sin `tipo_vehiculo` se muestran en un grupo aparte, nunca se inventa una clasificación.

Un embarque con varias hojas de ruta y guías cuenta como un solo viaje; el peso se suma una vez por guía dentro de cada embarque. Si una guía antecede al rango de fechas, su carga sí se incluye cuando el embarque entra en el rango.

## Comprobación funcional en Odoo

1. Actualizar solo `transcash_guias_api` a v2.20, desde una copia de seguridad.
2. Abrir **Logística Transcash > Inteligencia logística** con un usuario interno autorizado.
3. Elegir filtro «Registro en Odoo» y fechas que incluyan embarques conocidos.
4. Revisar la nueva sección «Vehículos contratados · viajes y peso» y entrar a «Tipos de vehículo».
5. Comparar un embarque conocido (tipo, salida y guías) con sus cifras, y exportar «Tipos de vehículo» a Excel.
6. Confirmar que se mantienen «Roturas e incidencias», «Transportistas», «Choferes», «Destinos», y «Liquidaciones» cuando el usuario tenga permisos.

**Nota:** no cambia `logistica_transcash`, los modelos operativos, permisos, ni la sincronización de guías.
