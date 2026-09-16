# Changelog

## 18.0.1.3.0

- Nuevo flujo **Nuevo catastro**: primero valida RUC o nombre antes de crear.
- Si el cliente ya existe en Odoo, reutiliza la misma ficha y evita duplicarlo.
- Si la búsqueda por nombre devuelve varias coincidencias, exige RUC para decidir.
- Creación estándar deshabilitada en las vistas de Catastro; el alta pasa por el asistente.
- CAPA vuelve a mostrarse como **CAPA / Capacidad de compra** y es requisito para Visita/Proforma.
- Nuevo catálogo de **Marcas de celulares** y selección múltiple por cliente.
- Las marcas son opcionales y no afectan la completitud del catastro.
- Se mantiene GPS opcional mientras la instalación funcione sin HTTPS.
