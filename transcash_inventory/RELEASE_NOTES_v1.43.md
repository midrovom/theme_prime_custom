# Transcash Inventario Inteligente v1.43 — móvil y sincronización por perfil de consulta

**Cambio acotado sobre v1.42:** se conservan el asistente ChatGPT de análisis libre, la compilación SELECT segura, el dashboard, filtros, fotos, tablas y exportaciones.

## Visualización móvil
- El iframe del cliente Odoo deja de exigir una altura mínima superior al área real disponible: evita el recorte del pie en vista móvil dentro de Odoo.
- Barra inferior elevada sobre el área del sistema y botones más legibles, con espacio reservado para el último contenido.
- Se conserva el menú lateral completo, incluido ABC×XYZ y ChatGPT según perfil.

## Sincronización API de lectura por usuarios de consulta
- Los miembros de **Acceso al panel de inventarios (consulta)** pueden abrir **Sincronización API** desde el menú o **Sincronizar API** desde el dashboard.
- El wizard solo requiere un clic del usuario; consulta por el servidor los endpoints GET previamente configurados en API Administrator. No habilita la edición de endpoints, credenciales o inventario.
- Para los usuarios no administradores se ocultan endpoints y mes de corte; sigue disponible para administradores.
- La ejecución valida empresa activa, permisos, JSON y datos. Solo la operación validada eleva privilegios para actualizar el snapshot; la ACL de usuario sigue siendo de lectura.
- Si los datos no cambian, se mantiene la versión vigente; si cambia, se crea un nuevo corte con historial, materialización SQL y transición atómica existente.
- Al cerrar el wizard abierto desde el dashboard, se recarga su información.

## Instalación
Reemplazar la carpeta **transcash_inventory**, reiniciar Odoo y **actualizar** el módulo desde Apps (no desinstalar). Probar primero en entorno de pruebas con usuario de consulta y usuario administrador; aplicar en producción después de validar. La base de datos y las configuraciones de API Administrator se conservan.
