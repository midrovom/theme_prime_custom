# 18.0.1.1.1

- Recuperación defensiva para despliegues donde el código nuevo se carga antes de actualizar el esquema.
- Pre-migración crea de forma idempotente las cuatro columnas nuevas de `res_partner` antes de cargar el módulo.
- Catastros incompletos pueden guardarse; la completitud se comunica con el indicador visual en lugar de bloquear migraciones/escrituras.
- Validación de `Número de locales` se mantiene.
- Validación GPS del cliente usa la marca real de captura, no el valor numérico 0/0.
- Un vendedor ya no puede cambiar el estado de una visita finalizada/cancelada.
- Regla multi-compañía añadida a horarios de atención.

# Changelog

## 18.0.1.1.0

- Rediseño completo de UX para Odoo 18 Community, priorizando móvil.
- Nueva vista exclusiva de Catastro sobre `res.partner`; deja de reutilizar la ficha visual general de Contactos.
- Se desactiva la extensión visual antigua para evitar RUC/identificación duplicados y campos de terceros en el flujo del Catastro.
- `Número de tiendas` pasa a `Número de locales` y queda visible/editable en la sección principal.
- Tipo de negocio cambia de selección única a etiquetas múltiples configurables (`Many2many`).
- Se elimina `Ruteo` de la experiencia nueva. Se introduce `Canal comercial`: Mayorista, Revendedor/distribuidor, Tienda al detalle, Mixto u Otro.
- CAPA queda como campo legado oculto hasta que se defina su significado funcional.
- Contactos del dueño y comercial quedan estructurados con nombre + teléfono.
- Nuevo horario estructurado por día, hora desde y hora hasta usando `float_time`; admite múltiples franjas por día.
- Nueva vista Kanban para clientes y visitas, pensada para móviles.
- Formularios de Catastro y Visita reorganizados en tarjetas y controles táctiles.
- Mini encuesta de visita usa controles de radio para respuestas Sí/No.
- Se conserva GPS, validación de distancia, proformas estándar y seguridad existente.
- Incluye migración desde los antiguos tipos de negocio; `Mixto Cel/Acc.` migra a dos etiquetas y `Ruteo` migra a Canal `Otro` sin asumir semántica.
