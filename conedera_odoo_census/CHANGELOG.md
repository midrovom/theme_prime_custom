# Changelog

## 18.0.1.5.0

- Corrige el resumen de productos cotizados para consolidar por cliente comercial, incluyendo cotizaciones hechas a contactos/direcciones hijas.
- Corrige reglas de acceso que podían hacer parecer que bitácora/productos habían desaparecido tras una actualización.
- La bitácora comercial es visible para el equipo de ventas dentro de las compañías permitidas; los vendedores siguen modificando únicamente sus propias visitas.
- El detalle y resumen de productos se muestran para la compañía permitida, sin exigir que `res.partner.user_id` coincida con el vendedor actual.
- Añade guardia de integridad de datos pre/post actualización; el upgrade aborta si disminuyen catastros, visitas, horarios, relaciones o proformas del módulo.
- La búsqueda por RUC/cédula detecta también identificaciones guardadas en contactos hijos y reutiliza el cliente comercial principal.
- Añade captura directa de fotografía desde móvil mediante cámara trasera (`capture=environment`), sin requerir HTTPS.
- Mejora la UX móvil con acciones rápidas grandes y tarjetas a ancho completo.
- Las métricas globales de producto consideran todas las cotizaciones no canceladas de la compañía actual.
- Mantiene GPS opcional hasta disponer de HTTPS.
