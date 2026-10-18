# Transcash 5.19 · Objeción de carga privada y control interno

- El chofer revisa fotos y videos en la misma pantalla de su embarque. No ve costos ni liquidaciones.
- Antes de salir puede pulsar OBJETAR ESTE EMBARQUE, ingresar un motivo obligatorio (12-2000 caracteres) y bloquear la salida.
- La PWA interna muestra una alerta roja con contador y listado de embarques objetados; el jefe de Logística también la ve.
- El operador reabre el viaje, registra fotos o videos NUEVOS para cada ruta, declara la acción correctiva y lo vuelve a liberar al chofer.
- Cada objeción y corrección conserva chofer, fechas, texto y responsable en bitácora privada. No se borra.
- Se ocultan observaciones generales internas al portal y los eventos de aceptación/liberación ya no son públicos para clientes.
- La creación de hojas de ruta, tarifa única por embarque, liquidaciones y la API no cambian.
- *Pruebas funcionales en una copia real de Odoo 18 son obligatorias antes de poner en producción.*
