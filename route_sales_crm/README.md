# CRM Ventas en Ruta — Odoo 18 Community

Control móvil para vendedores ruteros basado en CRM, Contactos y Ventas de Odoo.

## Alcance

- Cliente principal con múltiples tiendas o sucursales.
- Sector, segmento, zona, potencial, frecuencia, horario y vendedor asignado.
- Planificación diaria de rutas y orden de visitas.
- Entrada y salida GPS solicitadas únicamente al pulsar el botón correspondiente.
- Fecha, coordenadas y precisión del GPS; enlace directo a Google Maps.
- Fotos del establecimiento y otras evidencias.
- Resultado, observaciones, próxima visita y actividad de seguimiento.
- Encuesta comercial flexible por visita.
- Competidores, productos, precios, promociones, presencia y fotos.
- Registro operativo de cobranzas y evidencias, sin asiento ni pago contable.
- Cotizaciones y pedidos estándar de Odoo vinculados a la visita y oportunidad CRM.
- Análisis por vendedor, resultado, cliente, fechas, duración y valores cobrados.

## Instalación

1. Copiar `route_sales_crm` al directorio de addons.
2. Reiniciar Odoo y actualizar la lista de aplicaciones.
3. Instalar **CRM Ventas en Ruta**.
4. Asignar en Usuarios uno de los perfiles: Vendedor rutero, Supervisor o Administrador.
5. Marcar los clientes aplicables como **Cliente de ruta** y crear sus tiendas como contactos hijos de tipo Tienda/Sucursal.

## Requisitos para GPS

- Abrir Odoo mediante HTTPS.
- Autorizar ubicación en el navegador del teléfono.
- Tener activo el GPS del dispositivo.
- El módulo no hace seguimiento permanente: guarda ubicación solo en Entrada y Salida.

## Nota de privacidad

La empresa debe informar a los vendedores sobre la finalidad del registro, limitar el acceso a supervisores autorizados y definir un período de conservación de los datos acorde con su política interna y la normativa aplicable.
