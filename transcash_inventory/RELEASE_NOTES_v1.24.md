# TRANSCASH Inventario Inteligente v1.24

- Una barra compacta de filtros globales, sin marca duplicada ni barra independiente de filtros generales.
- Período, categoría, marca buscable, formato buscable, proveedor buscable, bodega y SKU en una sola sección.
- Los filtros de rentabilidad por proveedor y los filtros del asistente de IA usan esa misma selección global.
- Período personalizado muestra Desde y Hasta solo cuando es necesario.
- Apertura: la pantalla de carga desaparece después del primer recálculo exitoso, aplicando el período predeterminado.
- Actualización automática al escribir o seleccionar; campo libre conserva el texto al perder foco.
- No modifica importaciones, snapshots, tablas SQL, API Administrator, permisos, imágenes ni configuración de ChatGPT.

**Instalación:** realizar copia de seguridad; sustituir addons/transcash_inventory; reiniciar Odoo y actualizar módulo desde Aplicaciones. Cerrar pestaña y usar Ctrl+F5.

**Alcance de la prueba:** JavaScript, XML/Python y navegador aislado con datos originales; servidor productivo Odoo no probado.
