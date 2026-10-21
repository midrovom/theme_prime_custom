# Inventario Inteligente v1.29 — URL de fotografías por empresa

- Menú administrador: **Inventario Inteligente → Configuración de fotografías**.
- Edita el dominio HTTPS público de la tienda de la **empresa activa**; ejemplo `https://www.transcash.ec` (no se pega una ficha específica ni una URL a `/web/image`).
- Se almacena en `res.company.transcash_photo_site_url`; la configuración es independiente para cada empresa.
- El motor usa el dominio configurado para `/shop`, `/shop/page/N`, búsqueda por SKU, imágenes Odoo `/web/image` y `/web/content`, verificaciones y enlaces manuales.
- Solo permite HTTPS público, host y puerto permitidos; se valida dominio de redirecciones, tipo/tamaño de imagen y prefijo SKU exacto. No se consulta otro dominio.
- Si cambia el dominio, se marcan para nueva búsqueda solo las fotos de la empresa modificada; se limpian enlaces y miniaturas del sitio anterior, sin modificar otras empresas, inventarios, API Administrator, dashboards ni IA.
- Las miniaturas existentes del dominio anterior **se conservan cuando no se cambia la URL**.
- Funciona sobre v1.28, mantiene los otros módulos y no requiere volver a sincronizar productos, ventas, compras o stock.
- Requiere actualizar el módulo desde Aplicaciones y reiniciar Odoo, no solo copiar el ZIP.
- Pruebas sin conexión al servidor: sintaxis, validaciones del matcher, aislamiento de dominio y XML. Pendiente comprobar Odoo 18 en producción.
