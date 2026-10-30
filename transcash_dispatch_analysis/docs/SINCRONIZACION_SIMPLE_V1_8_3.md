# Sincronización desde el ERP · versión 1.8.3

## Operación

1. Abrir **Análisis de despachos → Sincronizar**.
2. Pulsar **Sincronizar**. El diálogo muestra únicamente una descripción breve y los botones Sincronizar/Cerrar; no muestra fuente, método, empresa, parámetros ni el resultado técnico anterior.
3. La pantalla **Sincronización desde el ERP** aparece antes de iniciar la descarga. Durante la recepción muestra una barra animada y En curso. La misma animación se mantiene mientras se valida y se obtiene el total de facturas.
4. Al actualizar las facturas se muestra el porcentaje confirmado y los contadores **Facturas actualizadas**, **Total de facturas** y **Registros del ERP**. Solo se llega a 100% al terminar la publicación del corte.
5. Al finalizar se puede abrir el tablero o las facturas. Una respuesta sin cambios reutiliza la carga vigente y lo indica. Si falla la recepción, muestra el error y permite reintentar.

La fuente se toma de la empresa activa, priorizando la habilitada para la sincronización automática. La configuración se mantiene en **Configuración → Fuentes y API**, para el Responsable. El cron de consulta continúa cada dos horas y el procesamiento por bloques conserva sus transacciones y bloqueo por fuente.

El avance puede reabrirse desde Importaciones e histórico/Historial de cargas. Su origen se lee del corte guardado: una carga API vuelve a mostrar ERP aunque no se haya abierto desde el botón de sincronización. Una carga Excel sigue mostrando el archivo y su nombre.

No se presenta un porcentaje ficticio durante la descarga: aún no se conoce el total de facturas. La barra inicial anima la actividad; el porcentaje posterior se calcula con facturas confirmadas/total y se mantiene por debajo de 100 hasta publicar.

## Aplicar la actualización

Reemplazar la carpeta transcash_dispatch_analysis, reiniciar Odoo y actualizar el módulo desde Aplicaciones. Recargar el navegador con Ctrl+F5 para recibir los nuevos archivos de interfaz. Las credenciales y la configuración de la fuente se conservan. No hace falta reimportar el Excel.

## Implementación y validación

La acción del botón solo abre la vista de avance. Tras montarla, el cliente llama sync_api_data con control de permisos antes de elevar la operación al mismo conector existente. Se utiliza el ORM silencioso cuando está disponible para mantener visible el avance. El cron continúa usando el método privado existente.

214 pruebas Python locales, nueve regresiones del controlador y doce verificaciones de navegador real con el componente OWL y servicios RPC controlados. No equivalen a una prueba contra el servidor/ERP remoto. Las pruebas nativas adicionales se incluyen para ejecutar en una base de prueba Odoo.
