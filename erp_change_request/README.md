# Solicitudes de Desarrollo ERP — Odoo 18 Community

Módulo para que los usuarios de un grupo empresarial soliciten desarrollos,
cambios, reportes e integraciones al equipo de Sistemas.

## Flujo

Solicitado → Revisión → Aprobado → Desarrollo → Pruebas → Terminado.

El cierre requiere la conformidad del solicitante. Desde Pruebas también puede
devolver la solicitud a Desarrollo con comentarios en el chatter.

## Funciones

- Empresa cliente y departamento obligatorios.
- Número automático `SD-AÑO-00000`.
- Prioridad, fecha requerida e indicador de vencimiento.
- Responsable de Sistemas, horas estimadas y reales.
- Archivos, capturas, comentarios, seguidores y actividades.
- Vistas kanban, lista, gráfica y tabla dinámica.
- Seguridad multiempresa y tres perfiles: Solicitante, Equipo de Sistemas y Administrador.

## Instalación

1. Copie `erp_change_request` en la ruta de addons personalizados.
2. Reinicie Odoo y actualice la lista de aplicaciones.
3. Instale **Solicitudes de Desarrollo ERP**.
4. Asigne a cada usuario un perfil en Ajustes → Usuarios.
5. Un administrador debe crear los departamentos por empresa desde
   Solicitudes ERP → Configuración → Departamentos.

## Recomendación de permisos

- Usuarios de las empresas: **Solicitante**.
- Analistas y desarrolladores: **Equipo de Sistemas**.
- Jefe de Sistemas: **Administrador de Solicitudes ERP**.

