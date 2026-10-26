# Versión 18.0.1.4.76 — Conexión ERP sin `call_api`

## Corrección

En algunas instalaciones del addon `api_administrator` existe el modelo
`api.administrator` pero no el método `call_api`. Esto provocaba que fallaran
los tres endpoints con: `AttributeError: 'api.administrator' object has no attribute 'call_api'`.

Las tres sincronizaciones (cuentas, centros y consumos) y los flujos secundarios
ahora usan `expense.budget.api.transport`. Este servicio:

1. Reutiliza `api.administrator.call_api` cuando está definido.
2. Si no existe, realiza HTTP GET hacia `url` + `end_point` del registro
   `api.administrator` previamente seleccionado, o la URL completa si
   `end_point` es una URL absoluta.
3. Reutiliza las credenciales existentes `user_id` y `password` como cabeceras
   `userid` y `password`, junto con `Accept: application/json`,
   `version: 1`, `framework: PRUEBAS`, `deviceid: 000000000000000` y
   `sessionid: 0`, de acuerdo con el ejemplo de configuración ERP.
4. Valida empresa, método GET, estado activo, URL HTTP(S) y formato JSON.
5. No crea APIs adicionales y nunca escribe contraseñas en el historial ni logs.

No se modifica el esquema de datos ni la planificación de cinco horas.
El cron y la sincronización desde Configuración API ERP siguen guardando todo
el histórico sin filtro de año y reutilizan las claves externas para evitar
duplicaciones en reejecuciones.

**Nota importante:** sin ID estable de movimiento en `getconsumosgastos/2`,
la huella depende de fecha, cuenta, centro, subcentro e importe; una rectificación
de esos campos puede producir una clave distinta. Para actualizaciones
inequívocas de esos movimientos, el ERP debe devolver un `id` estable.

## Actualización en Odoo

1. Hacer respaldo y sustituir el directorio `expense_budget_control` con la
   carpeta del ZIP. **No instalar el ZIP como un módulo duplicado**.
2. Reiniciar el servidor Odoo (para cargar el modelo de transporte).
3. Actualizar el módulo `expense_budget_control` a la versión `18.0.1.4.76`.
4. Verificar las tres APIs GET activas seleccionadas en Configuración API ERP.
5. Pulsar `Sincronizar` y comprobar que `Errores: 0` y que se registran filas
   en `Gastos reales` para distintos años. Revisar también `Historial API`.

El ZIP pasa pruebas locales de sintaxis y transporte GET simulado; la prueba
real requiere Odoo 18 y conectividad con el ERP de la empresa.
