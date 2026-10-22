# Transcash Inventario Inteligente v1.44 — lectura de indicadores para el perfil de consulta

## Incidencia corregida
- El perfil **Acceso al panel de inventarios (consulta)** podía ejecutar la sincronización API, pero `/transcash_inventory/data` fallaba al acceder a `dashboard_data`: el campo binario está restringido a responsables y administradores.
- `get_dashboard_json()` comprueba primero los permisos de lectura del registro (ACL y regla multiempresa) del usuario real y, **después**, lee exclusivamente el binario protegido con `sudo()` en el servidor. Ya no hay una lectura previa del campo bajo el usuario de consultas.
- No se modifica la ACL, los grupos, la regla multiempresa, los permisos de escritura, la configuración de API Administrator ni la interfaz del dashboard.

## Alcance de la actualización
- Solo cambia `models/snapshot.py` y la versión en `__manifest__.py`; se añade este archivo de notas.
- Se mantienen todos los recursos de v1.43 (diseño móvil, sincronización de consulta, IA, filtros, exportaciones, fotos y vistas), sin cambios.

## Instalación y verificación
1. Respaldar base de datos y módulo; desplegar la carpeta `transcash_inventory` de este ZIP, reiniciar el servicio de Odoo 18 y **Actualizar** el módulo (no desinstalar).
2. Probar con usuario del grupo **Acceso al panel de inventarios (consulta)** y empresa activa con datos: **Dashboard** debe mostrar indicadores.
3. Abrir **Datos importados** y confirmar filas; usar **Sincronización API** y comprobar que después el dashboard refleje la versión vigente.
4. Comprobar que ese usuario no puede abrir la configuración de API Administrator ni modificar snapshots o credenciales, y que otras empresas no se muestran.
5. Verificar también el perfil administrador y las consultas ChatGPT existentes.

No es necesario reimportar datos si ya se habían sincronizado correctamente. Si aún aparece el aviso, capturar estado HTTP y respuesta de `/transcash_inventory/data` en Red del navegador, junto con el traceback del registro Odoo.
