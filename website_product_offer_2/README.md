# Ofertas Web por Sitio — Odoo 18 Community

Módulo para recibir y negociar ofertas por cantidad desde la ficha de un producto, sin alterar el carrito, la lista de precios ni el flujo de venta pública.

## Funciones principales

- Activación independiente por sitio web.
- Alcance para todos los productos publicados o solo productos seleccionados.
- Reglas de cantidad mínima, máxima y porcentaje mínimo por producto/sitio.
- Precio de lista recalculado con la lista de precios activa del website.
- Stock tomado del almacén configurado para el website.
- Formulario AJAX adaptable a móvil, sin recargar la ficha del producto.
- Clientes identificados o visitantes, según la configuración del sitio.
- Flujo: Recibida → En revisión → Contraoferta → Presupuesto creado/Rechazada.
- Portal seguro mediante token para consultar, cancelar o aceptar una contraoferta.
- Conversión a `sale.order` en borrador; nunca confirma automáticamente la venta.
- Correos automáticos en cola para recepción, contraoferta, aprobación y rechazo.
- Seguridad multi-compañía y permisos para usuarios/administradores de Ventas.

## Instalación

1. Copiar la carpeta `website_product_offer` al directorio de addons personalizados.
2. Reiniciar el servicio de Odoo.
3. Activar el modo desarrollador y actualizar la lista de aplicaciones.
4. Buscar **Ofertas Web por Sitio** e instalar.
5. Ir a **Sitio web → Configuración → Ajustes**, seleccionar el website correcto y activar **Permitir ofertas en este sitio**.
6. Si el alcance es **Solo productos configurados**, abrir **Ofertas Web → Productos habilitados** y crear las reglas.

## Configuración recomendada para dos sitios

- Sitio mayorista: ofertas activas; productos seleccionados; control de stock activo.
- Sitio público: ofertas desactivadas. No se cambia ninguna vista ni controlador del carrito.

## Pruebas incluidas

El módulo incluye pruebas de conversión a presupuesto, restricciones positivas y aceptación de contraoferta. Para ejecutarlas en una base de pruebas:

```bash
./odoo-bin -d BASE_PRUEBAS -i website_product_offer --test-enable --stop-after-init --test-tags /website_product_offer
```

## Consideraciones

- Los precios de lista y oferta se manejan antes de impuestos; al convertir, Odoo aplica los impuestos y la posición fiscal del presupuesto.
- Enviar una oferta no reserva inventario. El stock se vuelve a validar al crear el presupuesto.
- Para recibir correos debe existir un servidor de correo saliente configurado en Odoo.

