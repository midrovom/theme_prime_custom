# Conexión de Inventario Inteligente con API Administrator (v1.34)

Esta versión utiliza **la misma convención HTTP del módulo `transcash_commission_api_bridge`**, pero no necesita que Comisiones esté instalado. No modifica `api_administrator` ni sus tablas.

## Configurar cuatro registros en API Administrator

En la empresa seleccionada en Odoo, crear o confirmar **exactamente uno por nombre**:

| Nombre (`name`) | Método (`type`) | Estado (`status`) |
| --- | --- | --- |
| `getproductosinvt` | `get` | `A` |
| `getventasinvt` | `get` | `A` |
| `getcomprasinvt` | `get` | `A` |
| `getstockinvt` | `get` | `A` |

Completar `url` (servidor/base), `end_point` (ruta), `user_id`, `password`, `company_id` (la empresa correcta). Las cuatro credenciales siguen centralizadas en API Administrator. No se copian a Inventario Inteligente.

## Formato de petición

- URL: `url.rstrip('/') + '/' + end_point.lstrip('/')` (o solo `url` si no hay endpoint).
- Método: GET.
- Cabeceras: `Accept: application/json`, `version: 1`, `framework: PRUEBAS`, `userid`, `password`, `deviceid: 000000000000000`, `sessionid: 0`.
- Tiempo máximo: 10 s para conexión y 120 s para lectura.
- Redirecciones bloqueadas para impedir reenviar credenciales a otro servidor. Si su API redirecciona, configure la URL final.
- Espera un JSON objeto/lista que el adaptador existente convertirá con su contrato `data/result/items/rows`.

## Multiempresa

Se consultan únicamente registros `api.administrator` activos, GET y con `company_id` igual a la **empresa activa**. Se rechazan registros inexistentes o múltiples. El usuario que sincroniza necesita permiso de administrador Odoo (el asistente ya lo exige).

## Migración

Reemplazar la carpeta `transcash_inventory`, reiniciar Odoo y **Actualizar** desde Aplicaciones. No desinstalar: los datos y snapshots previos permanecen. No hace falta instalar el módulo Comisiones.

## Si falla la integración

1. Revisar nombres y compañía de los cuatro registros en API Administrator.
2. Verificar tipo GET, estado Activado, `url`, `end_point` y cabeceras.
3. Revisar los logs de Odoo para conocer cuál endpoint falla sin mostrar credenciales al usuario.
4. Confirmar que la respuesta es JSON y contiene todas las claves requeridas por el contrato de inventario.

**Nota:** esta versión ha sido verificada con pruebas locales simuladas; la respuesta real de tus cuatro endpoints debe validarse en el servidor Odoo.
