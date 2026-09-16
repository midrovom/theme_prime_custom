# Conedera - Catastro Comercial (Odoo 18 Community)

Módulo para **Odoo 18 Community** orientado al catastro de clientes y visitas comerciales de vendedores de campo.

## Dependencias

Solo utiliza módulos disponibles en Community:

- `contacts`
- `mail`
- `sale_management`
- `web`

No depende de `web_map`, Studio ni otros módulos Enterprise.

## Qué reutiliza de Odoo

- `res.partner`: cliente, RUC (`vat`), dirección, ciudad, email, vendedor y coordenadas estándar.
- `sale.order`: cotizaciones/proformas y flujo comercial existente.
- `mail.thread` y `mail.activity.mixin`: chatter, trazabilidad y actividades.
- Vistas estándar list/form/pivot/graph para operación y análisis.

## Qué agrega

- Pestaña **Catastro comercial** en Contactos.
- Clasificación de negocio y cliente según el archivo BORRADOR ODOO.
- Captura GPS desde el navegador del celular y guardado en `partner_latitude/partner_longitude`.
- Modelo **Visita comercial** con mini encuesta, foto, observaciones, GPS y validación de distancia.
- Tolerancia de ubicación por visita (300 m por defecto).
- Generación de cotización/proforma estándar desde cliente o visita.
- Reagendamiento mediante actividades estándar de Odoo.
- Enlace `sale.order.census_visit_id` para trazabilidad visita → proforma.
- Apertura de la ubicación del cliente y de cada visita en **OpenStreetMap**, sin API key.
- Seguridad: vendedor ve sus visitas, no puede borrar visitas y no puede modificar/reabrir una visita finalizada; gerente de ventas administra las visitas de sus compañías.

## Campos del Excel cubiertos

- Nombre del cliente → `res.partner.name`
- RUC → `res.partner.vat`
- Contacto dueño → `owner_phone`
- Contacto comercial → `commercial_contact_phone`
- Nombre de la tienda → `commercial_name`
- Ciudad / Dirección / Email → campos estándar de Contactos
- Número de tiendas → `store_count`
- CAPA → `capa` (pendiente definir semántica exacta)
- Tipo de negocio → `business_type`
- Tipo de cliente → `customer_census_type`
- Resultado de visita → campos de `conedera.census.visit`

## Instalación

1. Copiar la carpeta `conedera_odoo_census` al directorio incluido en `addons_path`.
2. Reiniciar Odoo 18.
3. Activar modo desarrollador si hace falta y actualizar la lista de aplicaciones.
4. Instalar **Conedera - Catastro Comercial (Community)**.
5. Conceder al vendedor permisos de Ventas.

La geolocalización del navegador requiere **HTTPS** (excepto `localhost`) y permiso de ubicación del dispositivo.

## Flujo recomendado

1. Catastro Comercial → Clientes catastrados → Nuevo.
2. Completar ficha y pestaña Catastro comercial.
3. Capturar GPS y guardar.
4. Desde el cliente, Registrar visita.
5. Capturar GPS de la visita, responder la mini encuesta y finalizar.
6. Generar proforma; Odoo abre una cotización estándar enlazada a la visita.
7. Supervisor usa Visitas / Análisis para revisar productividad y registros fuera de ubicación.
8. Los botones **Abrir ubicación en mapa** muestran el punto capturado en OpenStreetMap.

## Mapa y recorrido en Community

Esta versión **no usa la vista Map Enterprise**. Conserva todos los puntos GPS reales de las visitas y permite abrir cada punto en OpenStreetMap.

El recorrido continuo del vendedor (línea GPS durante toda la jornada) no se captura en segundo plano en este MVP. La siguiente fase Community puede incorporar un dashboard cartográfico propio (por ejemplo con Leaflet/OpenStreetMap) para representar todos los puntos del día y el recorrido sin licencias Enterprise.

## Compatibilidad

Versión técnica del módulo: `18.0.1.0.0`.
