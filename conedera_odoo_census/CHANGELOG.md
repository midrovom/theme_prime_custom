# Changelog

## 18.0.1.8.3

Corrección móvil de Equipo comercial y bloqueo del Catastro: el vendedor puede seleccionar un equipo válido mientras la ficha está en borrador; los equipos técnicos quedan fuera del selector; Configuración usa vistas propias sin dashboard gráfico; Usuarios y permisos permite asignar rol + equipo; Registrar/Terminar edición ya no usa un `reload` genérico ni hooks de `res.partner` de terceros, evitando el error de acceso a `route.sale.visit` de Ventas en Ruta. Incluye migración conservadora y Data Guard.

## 18.0.1.8.2

Corrección del equipo comercial técnico `Sitio web`, permisos explícitos Comercial/Supervisor/Administrador, nuevo menú `Usuarios y permisos`, equipo de Catastro autoasignado y protegido contra equipos técnicos, ACL controladas para administrar equipos y migración conservadora de usuarios/equipos históricos. Consulte `CHANGELOG_18.0.1.8.2.md`.

## 18.0.1.8.1

Revisión de seguridad y consistencia de la 18.0.1.8.0: unicidad concurrente de RUC/cédula, validación global segura del selector, RUC en contactos hijos, reglas jerárquicas sobre el cliente comercial, bloqueo backend reforzado, solicitudes auditadas y lectura histórica de proformas tras reasignación.
