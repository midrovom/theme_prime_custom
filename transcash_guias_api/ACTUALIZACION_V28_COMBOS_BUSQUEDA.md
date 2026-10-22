# Transcash Guías API 18.0.2.8.0 — PWA: búsqueda en desplegables

## Alcance

Actualiza **solo** `transcash_guias_api`; no requiere modificar `logistica_transcash` ni instalar addons adicionales.

En **/transcash/operacion**, los siete selectores de creación de hojas de ruta y planificación de embarques admiten búsqueda:

1. Empresa de transporte (nombre, RUC y referencia ERP del contacto).
2. Chofer (nombre, login/cédula y RUC/cédula del contacto).
3. Destino (nombre y código).
4. Tipo de vehículo.
5. Grupo de rutas de un mismo transporte/chofer/vehículo.
6. Embarque existente para agrupar rutas.
7. Destino de tarifa.

La mejora conserva cada `<select>` y su `name`, `value`, `required` y `change` originales. No hay consultas adicionales a la API ni nuevas reglas de asignación: continúan las restricciones de v2.7. Si JavaScript no carga, se muestra el selector nativo.

## Instalación

1. Respaldar base de datos y addon instalado.
2. Sustituir únicamente la carpeta `transcash_guias_api` por esta versión.
3. Reiniciar Odoo, actualizar `transcash_guias_api` y forzar recarga de la PWA (cerrar y abrir para renovar caché).
4. Probar **Operación → Nueva hoja de ruta** y **Operación → Armar embarque**.

## Pruebas rápidas

- Buscar transportista por fragmento de nombre y por RUC; debe elegir el ID real de `proveedor_id`.
- Buscar chofer por apellido y cédula; debe elegir el ID real de `chofer_id`.
- Buscar destino por nombre y código; cambiar selección.
- Seleccionar grupo de rutas; debe seguir abriendo las rutas compatibles.
- Si no se elige un valor en un campo requerido, no debe guardar la ruta.
- En móvil probar teclado, desplazamiento de resultados y opción «sin coincidencias».
- Confirmar que **Agregar guías** sigue filtrando por empresa, chofer y destino con v2.7.

## Diseño y seguridad

No se modifican registros, permisos, portales de choferes ni el backend operativo. Los valores enviados siguen siendo los IDs válidos ofrecidos por el servidor. La búsqueda se realiza sobre las opciones visibles al operador autorizado, sin solicitar datos privados de proveedores de productos o marcas.
