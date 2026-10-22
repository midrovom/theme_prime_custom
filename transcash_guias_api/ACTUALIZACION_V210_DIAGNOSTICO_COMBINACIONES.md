# v2.10 — Filtros combinados en PWA

## Diagnóstico

Los contadores individuales no prueban que exista una guía que satisfaga las tres condiciones a la vez. Si aparecen 51 coincidencias de destino y 51 descartes posteriores por chofer, no existe coincidencia de destino + chofer entre las guías analizadas.

## Cambios

- Agrega totales de las intersecciones destino+chofer, destino+transportista y chofer+transportista.
- Resume, para las guías del destino no pertenecientes al chofer de la ruta, el conductor y proveedor **reales** con ejemplos de guía. El resumen es solo lectura; no habilita selección incompatible.
- Corrige el mensaje incorrecto de "No hay guías disponibles para este destino".
- Prioriza vínculos operativos (`destino_id`, `chofer_usuario_id`) sobre referencias auxiliares desactualizadas; conserva el rechazo de RUC/identificación contradictorios entre la guía y el usuario.
- No cambia el modelo de guías, las reglas de estado, ni embarques, ni usuarios, ni liquidaciones.

## Cómo verificar

1. Actualizar SOLO `transcash_guias_api`.
2. Recargar PWA y abrir la misma hoja de ruta en borrador.
3. Observar la cantidad destino+chofer y la tabla de choferes reales para ese destino.
4. Comparar las guías ejemplo desde «Guías para armar rutas».
5. Si el chofer real difiere, elegir el chofer adecuado al planificar otra hoja o usar el flujo autorizado para modificar la ruta; **no** se reasigna automáticamente.
6. Si el chofer coincide pero la interfaz muestra 0, revisar el documento RUC/cédula y la vinculación Portal y corregir en la conciliación de terceros.

Requiere prueba funcional en la base real de Odoo 18.
