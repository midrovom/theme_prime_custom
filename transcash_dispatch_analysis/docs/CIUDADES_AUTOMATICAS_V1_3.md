# Ciudades y plazos automáticos · 18.0.1.3.0

## Comportamiento

- Cada ciudad detectada en Excel o API se registra en **Configuración → Plazos por ciudad**.
- Valor inicial: **9 días calendario**. **Guayaquil: 3 días calendario**.
- Los plazos son editables; se conservan los días, calendario, vigencias y estado archivado de las reglas existentes.
- Las variantes de mayúsculas, espacios y tildes no crean ciudades adicionales.
- Una ciudad vacía o el marcador SIN CIUDAD no crea una ciudad ficticia. Las facturas sin ciudad conservan su observación de calidad.
- Los nuevos plazos se capturan antes de calcular las facturas de esa importación.
- Las reglas por ciudad y modalidad siguen teniendo prioridad sobre el plazo de la ciudad para todas las modalidades.
- Las ciudades pertenecen a su compañía; un cambio no modifica otra compañía.
- No se crean fichas geográficas de contactos: estas filas son los parámetros del módulo de análisis.

## Actualizar una instalación existente

1. Reemplazar la carpeta `transcash_dispatch_analysis`, conservando el nombre técnico.
2. Reiniciar Odoo y **actualizar el módulo** en Aplicaciones. Recargar el navegador con Ctrl+F5.
3. Al actualizar se completan automáticamente las ciudades de las facturas ya importadas. No hace falta volver a subir el Excel para crear su configuración.
4. Revisar **Configuración → Plazos por ciudad**.
5. Para aplicar estos plazos al corte que ya estaba terminado, pulsar **Aplicar parámetros** en el tablero. Si hay una sola fuente, se abre el progreso directamente; mantener esa pantalla abierta. Si hay varias, se muestra la lista de nuevos cortes: abrir cada uno y pulsar **Procesar / ver progreso**.

Una importación nueva aplica los plazos automáticamente. Los cortes anteriores conservan las reglas con las que se calcularon; al reaplicar parámetros se genera un nuevo corte y se conserva el anterior como histórico.

Si un corte estaba a medio cargar antes de actualizar, terminarlo y luego reaplicar parámetros. Una regla de ciudad archivada o con vigencia limitada cuenta como configuración deliberada: no se reactiva ni se rellena su vigencia automáticamente. Una regla general sin ciudad puede mantenerse, pero los plazos por ciudad tienen prioridad.

## Validación

Se ejecutaron pruebas del motor, del control de importación y de los métodos reales de creación de ciudades mediante un ORM simulado. La validación nativa de instalación, transacciones PostgreSQL, permisos y plantillas OWL se realiza en el servidor Odoo de destino.
