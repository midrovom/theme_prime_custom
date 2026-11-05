# Catastro PWA 18.0.1.5.16 — Configuración de Consumidor Final

## Problema solucionado

El menú «Consumidor final por empresa» abría res.company como lista y formulario
con el nombre de empresa de solo lectura. Si se pulsaba Nuevo, se intentaba
crear una empresa nueva en lugar de configurar el contacto del cotizador.

## Nueva configuración

Catastro > Configuración > Configurar Consumidor Final.
- **Empresa que utilizará este cliente**: seleccionar una compañía de Odoo existente.
- **Cliente Consumidor Final**: buscar el contacto correspondiente; si no existe,
  utilizar Crear y editar para crear un **contacto**, no otra compañía.
- Pulsar **Guardar Consumidor Final**.
- Activar la compañía en el selector de empresas de Odoo si se requiere cambiarla.

La configuración continúa almacenándose mediante
`res.company.catastro_retail_partner_id` (campo calculado no almacenado que usa
`ir.config_parameter` por empresa); no se crea una columna nueva en `res_company`
ni se alteran las cotizaciones, inventario, Loyalty, permisos de negociación o PWA offline.

## Instalación

1. Copia de seguridad de PostgreSQL y de los módulos.
2. Reemplazar solo `conedera_odoo_census_mobile`.
3. Reiniciar todos los procesos/workers de Odoo.
4. Actualizar el módulo desde Aplicaciones.
5. Abrir Catastro > Configuración > Configurar Consumidor Final; elegir empresa y contacto, guardar.
6. Entrar a `/catastro/app` con el perfil Tienda de la empresa para probar Cotización directa.

No es necesario crear una empresa nueva ni borrar el almacenamiento local de la PWA.
