# v1.45 – Fotos multiempresa sin alterar la analítica

- Corrección del indicador JavaScript de permisos: el backend emitía `true` mientras el frontend exigía `1`. Ahora el autoencolado de fotos funciona para usuarios autorizados.
- El perfil de consulta puede **solicitar en segundo plano** fotografías de SKU de su empresa, sin editar fichas, URLs, índices, catálogos ni credenciales. El sistema realiza la búsqueda asincrónica mediante el cron existente.
- El cron recorre las compañías con inventario de forma rotativa (hasta cuatro por ejecución), sin bloquearse en la compañía del snapshot más reciente. La sincronización por empresa sigue aislada.
- Si el mismo SKU ya tiene una foto pública verificada en otra compañía **con la misma URL HTTPS de tienda**, el sistema copia solo el enlace y la miniatura a un nuevo registro de la compañía actual, validando que el SKU de la ficha coincida. No se copian datos del inventario ni métricas.
- Ante errores temporales del sitio público, una fotografía previamente verificada conserva su miniatura y sigue visible. El último error queda registrado.
- En el encolado de SKU visibles se reutilizan imágenes públicas de otra compañía de la misma tienda **sin esperar al cron**. Los registros marcados como verificados cuya miniatura falte se reportan como pendientes de reparación, para permitir recuperarla.
- Se conserva la separación por empresa en todas las lecturas y URLs; se envía el ID explícito al buscar y encolar fotos.
- La tienda puede devolver productos sin fotografía pública o no indexados por SKU exacto; esos no se enlazan sin validación.
- Sin cambios a cálculos ABC/XYZ, datos importados, APIs, SQL de ChatGPT, dashboards, sincronización de inventario, diseño móvil ni exportaciones.

## Instalación y diagnóstico

1. Hacer respaldo de PostgreSQL y filestore; sustituir módulo; reiniciar **todos** los workers y actualizar módulo desde Aplicaciones. No desinstalar.
2. Abrir una empresa y un SKU con foto en el catálogo de la tienda. Visitar "Imágenes vinculadas" (gestor) para revisar `status` y `last_error`.
3. Confirmar la URL HTTPS en "Configuración de fotografías" de cada empresa. Una URL distinta impide compartir fotografías, intencionadamente.
4. Verificar el cron activo "TRANSCASH: Indexar fotos públicas por SKU"; ejecutar manualmente para acelerar la primera verificación y refrescar el explorador.
5. Probar en compañía A y B el mismo SKU; las miniaturas deben estar ligadas al contexto de compañía de la sesión.

**Nota:** no se ensayó en el servidor de producción ni se conocen sus registros o logs. La disponibilidad real depende de la respuesta HTTPS pública y los SKU publicados en la tienda.
