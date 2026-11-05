# Catastro PWA 18.0.1.5.13 — Cotizador compacto

- Catálogo: agregar o quitar productos desde su propia tarjeta; el botón indica “Agregado” inmediatamente, sin selección por lotes ni botón final.
- Cantidad editable desde el catálogo y desde el resumen, con comprobación del stock cargado.
- Se elimina la franja “productos encontrados” y se compacta el ordenamiento junto a los filtros.
- Barra fija “Revisar y guardar” que cambia a una vista de revisión independiente, sin tener que recorrer miles de productos.
- En la interfaz de Tienda solo se muestra el nombre de la forma de pago y el precio final orientativo. No se muestra el recargo, su porcentaje o desglose.
- El desglose financiero sigue registrándose en sale.order.line con los campos existentes, sin cambiar reglas de Odoo, Loyalty, negociaciones ni stock.
- Se retira la leyenda técnica al final del catálogo y el detalle técnico financiero de las proformas visualizadas en la PWA.
- Código base 18.0.1.5.12; no se alteran modelos, controladores, registros ni migraciones de base de datos.

## Instalación

Actualizar únicamente el complemento `conedera_odoo_census_mobile`. Conservar la base de datos y los registros IndexedDB; no desinstalar. Reiniciar Odoo, actualizar el módulo y cargar `/catastro/app?version=18.0.1.5.13`. Probar en entorno de homologación antes de producción.
