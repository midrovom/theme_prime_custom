# Validación estática — 18.0.1.8.6

## Resultado
- Errores encontrados al cierre: **0**
- Esta validación es estática; la prueba definitiva continúa siendo el `-u` en Odoo 18 + PostgreSQL del servidor.

## Comprobaciones realizadas
- Manifest en versión `18.0.1.8.6` y rutas de data/assets existentes.
- 51 archivos Python compilan antes de limpiar cachés.
- 20 XML parsean correctamente; 127 IDs XML explícitos sin duplicados.
- `__init__.py` raíz conserva `from . import models`.
- La vista móvil contiene **una sola** instancia visible de `census_company_id` en el formulario de Catastro.
- La página Cliente contiene un solo selector de `census_team_id` y un solo `user_id` para la asignación comercial.
- `opening_hours_summary_html` existe una sola vez en la página Ubicación y horario.
- Cuando el Catastro está protegido para el usuario, el editor One2many se oculta y queda visible el resumen legible del horario.
- El resumen calcula día y franjas con formato `HH:MM – HH:MM` a partir de las líneas existentes; no crea una segunda tabla ni migra datos.
- Estilos responsive del horario presentes para móvil.
- Migraciones Data Guard 18.0.1.8.6 presentes.
- La migración nueva no contiene `DELETE FROM`, `TRUNCATE`, `DROP TABLE` ni `DROP COLUMN`.
- Prueba de regresión incluida para verificar que un horario guardado renderice `Lunes`, `09:00` y `18:00`.
- 3 archivos JavaScript pasan `node --check`.

## Alcance deliberado del cambio
La 18.0.1.8.6 no modifica la arquitectura de seguridad, reasignación, bitácora, visitas, proformas, productos, fotos ni multiempresa de 1.8.5. Solo corrige la duplicación visual de Empresa/Equipo/Vendedor en la sección de asignación y la representación móvil del horario, más un Data Guard de protección durante el upgrade.
