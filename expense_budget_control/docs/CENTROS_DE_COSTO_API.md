# Centros de costo – Odoo 18

## Ejemplo de API existente en `api_administrator`

```json
{
  "data": [
    {"company_id": "Conedera", "code": "CC001", "name": "Administración"},
    {"company_id": "Conedera", "code": "CC002", "name": "Operaciones"}
  ]
}
```

Se aceptan también `codigo` / `nombre` y `cost_center_code` / `cost_center_name`.
El código debe ser único por empresa. Si ya existe, se actualiza su nombre.
**No se crean nuevas API**: el administrador elige una API GET activa existente en
Configuración → API de centros de costo.

## Imputación presupuestaria

Se asigna un Centro de costo opcional a cada línea mensual del presupuesto y a
cada gasto real. Se puede repetir cuenta y mes en distintos centros.
Los gastos de API/Excel podrán incluir `codigo_centro_costo`. Cuando se suministra,
el centro debe existir previamente y se asigna a la línea de la misma cuenta,
año, mes, empresa y centro. Los gastos históricos sin centro mantienen su
imputación a líneas sin centro y no se reasignan automáticamente.

Ejemplo de movimiento con centro de costo:

```json
{"id": "G0001", "codigo_cuenta": "101002", "codigo_centro_costo": "CC002",
 "fecha": "2026-10-19", "monto": 125.5, "descripcion": "Servicio de luz"}
```

### Dashboard y reportes

Proyectado vs. real puede filtrarse por centro de costo. El dashboard también
permite elegirlo. Si no se selecciona, incluye todos los centros y líneas
históricas sin centro. El PDF anual distingue las mismas cuentas por centro.

### Migración

Al actualizar se elimina la antigua unicidad por cuenta/mes dentro del mismo
presupuesto y se reemplaza con cuenta/mes/centro. No se borran datos antiguos.
Se recomienda probar la instalación primero en una copia de la base de datos.
