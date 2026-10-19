# v1.4.67: Guardado de presupuestos más rápido

- La edición exclusiva de **Proyectado** no consulta el ERP.
- Al guardar líneas recién consultadas (hasta 30 minutos), usa consumos locales sin repetir HTTP.
- Si la sincronización completa de consumos del año se ejecutó correctamente durante las 5 horas anteriores, el guardado utiliza los gastos registrados en Odoo.
- Los nuevos períodos/años sin sincronizar todavía consultan `getconsumosgastos/2` en el primer guardado para preservar la recuperación histórica. Su primera consulta depende del tiempo de respuesta de ese endpoint y del tamaño de la respuesta.
- El filtro inicial del historial se hace primero por cuenta y centro, después por mes/año, y la prioridad de subcentro exacto se mantiene.
- Se precargan movimientos por clave externa y se reutilizan los registros de cuenta, centro y línea durante la importación para evitar búsquedas SQL repetidas.
- La sincronización manual y el cron cada 5 horas no cambian. Si se necesita actualización inmediata desde el ERP, usar **Sincronizar**.
- No se cambia la fórmula de Consumido ni se modifica el importe Proyectado.

Pruebas estáticas locales: AST, XML, integridad ZIP. Las pruebas de negocio deben ejecutarse dentro de una instancia Odoo 18.
