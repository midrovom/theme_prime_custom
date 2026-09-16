# Changelog

## 18.0.1.2.1

- `Número de tiendas / locales` queda como entero editable propio del módulo y los registros nuevos parten en `0` para obligar al vendedor a ingresar el dato real.
- Nuevo bloqueo operativo: un catastro incompleto puede guardarse, pero no permite registrar visitas ni crear proformas desde Catastro.
- El bloqueo se aplica tanto en la interfaz como en backend/RPC para evitar saltárselo desde otros menús.
- Requisitos operativos: razón social, RUC, nombre comercial, número de tiendas > 0, tipos de negocio, canal comercial, dueño/teléfono, contacto comercial, teléfono o móvil, email, dirección, ciudad y horario de atención.
- GPS del cliente y de la visita queda temporalmente opcional mientras el servidor no tenga HTTPS.
- Una visita puede finalizar sin GPS; si existe captura, se sigue guardando y validando.
- La ficha muestra exactamente qué datos faltan antes de habilitar Visita/Proforma.
- Migración defensiva para `census_store_count` en bases que hayan quedado a medio actualizar.
