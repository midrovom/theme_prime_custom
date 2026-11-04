# Catastro PWA — versión 18.0.1.5.0

## URL independiente

- URL preferida: `/catastro/app`.
- URL corta: `/catastro` (redirección a `/catastro/app`).
- URL anterior: `/conedera/app` (redirección conservada por compatibilidad).
- Odoo completo: `/web` **sin modificación**.
- Service Worker nuevo: `/catastro/sw.js`, alcance exclusivamente `/catastro/`.
- Las rutas técnicas internas y los modelos originales no se renombran.

## Cotizaciones en PWA

La ficha del cliente protegido muestra **Nueva cotización**. Existe también la pestaña **Cotizar** en móviles y escritorio. El usuario puede elegir un cliente protegido de su compañía, vincular una visita comercial finalizada, buscar productos por nombre/código, definir cantidades y una referencia externa, guardar el borrador y consultar el detalle dentro de la PWA.

La PWA crea cotizaciones reales de Odoo, `sale.order`, vinculadas al módulo Catastro (`census_originated=True`, `census_visit_id` cuando corresponda), usando el ORM y los permisos del usuario actual. **No envía precios, impuestos ni descuentos desde el navegador**. El motor de Odoo determina lista de precios, descuentos predeterminados, impuestos, moneda y totales al crear el borrador. Las condiciones específicas del formulario de Ventas deben revisarse antes de enviar al cliente.

**Offline**: el catálogo de productos consultados queda almacenado localmente; la cotización offline se guarda en la cola con UUID y no existe en el servidor hasta sincronizar. Los precios no se prometen ni se muestran offline. Si Odoo rechaza una operación, queda como error visible para revisión; no se marca como sincronizada. La PWA nunca confirma cotizaciones ni envía correos automáticamente.

**Límites y compatibilidad**: esta entrega implementa alta de cotizaciones en borrador, consulta de importes y detalle, e historial. Edición avanzada de cotizaciones ya creadas, variantes de lista de precios, condiciones comerciales especiales, envío, firma, PDF y reglas de campos personalizados siguen en Odoo. El código adjunto solo contiene la extensión de `sale.order` del módulo base; si existen otros módulos personalizados de cotización, hay que revisarlos para replicar sus campos y procesos particulares en la PWA. Las modificaciones automáticas mediante `onchange` de terceros no se reproducen de forma garantizada llamando a `create` por ORM. **Probar en staging con clientes y listas de precios reales**.

## Actualizar

1. Copia de seguridad y prueba en entorno de staging.
2. Actualice únicamente la carpeta técnica `conedera_odoo_census_mobile`, conservando el módulo base `conedera_odoo_census` instalado.
3. Reinicie Odoo, actualice con `-u conedera_odoo_census_mobile` en la base adecuada y acceda a `/catastro`.
4. Recargue PWA con conexión para instalar el nuevo Service Worker. Para accesos antiguos instalados con la URL `/conedera/app`, vuelva a instalar el acceso directo nuevo **solo después de sincronizar cualquier operación pendiente**.
5. Pruebe un usuario con permiso de Ventas y grupo de Catastro; un usuario sin el permiso de Ventas no podrá crear cotizaciones.

## Pruebas mínimas en Odoo

- `/web` continúa sin redirección; `/catastro` abre solo esta app.
- PWA instalada en teléfono con `/catastro/app` después de una carga online.
- En el catastro protegido, botón **Nueva cotización**; sin proteger, bloqueado.
- Producto de la compañía permitida, cantidad positiva, visita vinculada del mismo cliente y compañía.
- Cotización guardada como `draft`, totales y descuento calculados por Odoo, vinculada a su visita si se seleccionó.
- Usuario sin permiso de Ventas no puede guardar; cambio de sesión/compañía bloquea la cola offline.
- Cotización sin Internet: queda pendiente y al sincronizar se muestra número de cotización; verifique que la tarifa se recalculó con los valores vigentes.
- Validar campos personalizados de su instalación de Ventas antes de usar en producción.
