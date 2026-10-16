# Transcash V5.11 — Corrección y auditoría del dashboard (Odoo 18)

## Alcance

Actualización puntual de la V5.10. **No desinstalar** el módulo `logistica_transcash`. La V5.11 conserva los modelos y pantallas de guías, choferes, hojas de ruta, embarques, carga y firma de recepción, incidencias, notas de crédito, proveedores, liquidaciones, pagos, PWA y API.

**Versión técnica:** `18.0.5.11.0`.

## Hallazgo y causa del Server Error

En `models/analitica.py`, dentro de `get_dashboard()`, la función interna `summary(info, key)` reutilizaba el nombre `key` para el identificador de cada agrupación. Después ordenaba con `r[key]`: cuando existía al menos un transportista, chofer o destino, ese `key` era un ID o código de agrupación en vez de la columna (`novedades`, `viajes`, etc.), lo que provocaba `KeyError`. La función se invocaba al calcular rankings del dashboard y también al generar el informe Excel.

Se corrigió cambiando las variables por `group_key` y `sort_field`, y ordenando con `r[sort_field]`. Se añadió una regresión en `tests/test_analitica_v57.py` que consulta los rankings con un embarque registrado.

**Nota:** el diagnóstico se basa en inspección del código que nos facilitaste. No disponemos del traceback de tu VPS. Si aparece otro error después de actualizar, se necesitará el log de Odoo para identificarlo.

## Mejoras de presentación

- Reorganización tipo centro de control (en la misma acción de Odoo, no una PWA aparte).
- Barra lateral oscura, cabecera, filtros separados, seis KPI, panel de evolución, resumen de calidad y rankings visibles de destinos y transportistas.
- Tablas con búsqueda, ordenamiento y exportación `.xlsx` por dimensión.
- Adaptación a escritorio, tablet y móvil; no se insertan estilos globales que afecten a otras pantallas de Odoo.
- Mensaje de error legible y botón Reintentar, sin mostrar trazas internas a usuarios.
- Se mantienen las reglas de cálculo, límites de consulta, validación de compañías y grupo de Analítica.

## Archivos modificados en el addon

1. `__manifest__.py`: versión `18.0.5.11.0`.
2. `models/analitica.py`: corrección de ordenación.
3. `static/src/js/dashboard.js`: rankings, visualización, gestión de errores.
4. `static/src/css/dashboard.css`: estilo renovado, encapsulado.
5. `static/src/xml/dashboard.xml`: disposición visual y navegación.
6. `tests/test_analitica_v57.py`: prueba de regresión.

Se incorpora este documento de actualización. **No se modificaron los controladores de guías o PWA, modelos de embarques o liquidaciones, permisos, datos, integraciones, contratos API ni estructura de la base de datos.**

## Pasos seguros de actualización en VPS

1. Programar una ventana de mantenimiento y avisar a los choferes. **Antes de limpiar cachés o desinstalar una PWA, sincronizar evidencias offline pendientes.**
2. Respaldar la base de datos PostgreSQL, el filestore y la carpeta actual del addon V5.10. Recomendable repetir primero el proceso en copia de pruebas.
3. Descomprimir el ZIP y sustituir la carpeta `logistica_transcash` en el `addons_path` personalizado. Conservar propietario/permisos correctos.
4. Reiniciar el servicio de Odoo (por ejemplo, `sudo systemctl restart odoo18`; verifica primero el nombre real con `systemctl list-units --type=service | grep -i odoo`). Si usas Docker, utiliza el procedimiento de tu despliegue.
5. Entrar a **Aplicaciones**, activar modo desarrollador, localizar **Transcash - Seguimiento de Guías** y pulsar **Actualizar**. No desinstalar el módulo.
6. Abrir **Logística Transcash → Transcash · Indicadores**; usar `Ctrl+F5` o una ventana privada para descartar los assets antiguos. Si la interfaz no cambia, revisar la actualización de `web.assets_backend` y probar una vez con `?debug=assets`.
7. Verificar con un usuario miembro de **Analítica: consultar dashboard logístico**. Probar filtros por semana/mes, destinos, transportistas, choferes, marcas, Excel y Control de novedades.

## Comprobación del error (VPS)

Si después de la V5.11 sigue mostrando «Server Error», tomar el traceback de Odoo **en el momento de pulsar Actualizar datos**. Ejemplo para un servicio llamado `odoo18`:

```bash
sudo journalctl -u odoo18 --since "10 minutes ago" --no-pager | tail -n 180
```

En Docker (identificar primero el contenedor real con `docker ps`):

```bash
docker logs --since 10m NOMBRE_CONTENEDOR 2>&1 | tail -n 180
```

No compartir tokens de API, cookies de sesión ni credenciales. El dato útil será la excepción final y la ruta/función que originó el error.

## Pruebas verificadas fuera de Odoo

- Sintaxis Python de todos los archivos `.py`.
- Parseo XML de todos los archivos `.xml`.
- Sintaxis JavaScript (Node `--check`).
- Simulación aislada de rankings con IDs numéricos y códigos alfanuméricos de destinos (sin `KeyError`).
- Capturas de maqueta ilustrativa en 1440px y 390px, sin desplazamiento horizontal de página.
- Revisión de archivos frente a V5.10 para detectar cambios fuera del dashboard y la prueba.

**Pendiente:** ejecución de pruebas de módulo real en Odoo 18 y regresión completa con tu base y tus datos. No se puede certificar el comportamiento del VPS a partir de la revisión estática solamente.
