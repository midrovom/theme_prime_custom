# Control de Gastos para móvil — Odoo 18

## Qué cambia

El menú raíz **Control de Gastos** abre **Accesos rápidos**, con tarjetas adaptativas.
Solo se listan las opciones del rol del usuario (Registro, Consulta, Aprobador o Administrador),
verificadas en el servidor mediante `has_group` y permisos de lectura.
No se modificaron ni elevaron los permisos de acceso.

- Teléfonos: una tarjeta por fila; tablets: dos; computadoras: tres.
- Dashboard: filtros, indicadores y gráficos adaptables al ancho disponible.
- Presupuestos: botones de cabecera y líneas mensuales desplazables sin esconder campos.
- Se conservan los PDF, flujos de aprobación, API, importaciones y cálculos.

## Instalación como PWA

Odoo 18 dispone de una **PWA nativa**; este módulo reutiliza esa instalación estándar.
No instala otro service worker, otro manifest ni permite introducir datos sin conexión.
**Requisito del navegador: utilizar HTTPS con un dominio válido.** Una dirección
`http://IP:puerto` pública no cumple los requisitos de instalación de PWA.

1. Configurar Odoo detrás de un proxy inverso con certificado HTTPS y URL externa correcta.
2. Iniciar sesión en Odoo desde Chrome en Android o Safari en iPhone.
3. Android: menú de Chrome > **Instalar aplicación** (o Añadir a pantalla principal).
4. iPhone: Compartir > **Añadir a pantalla de inicio**.
5. Abrir **Control de Gastos** y usar las tarjetas de **Accesos rápidos**.

La PWA nativa es el cliente Odoo completo; **no es una aplicación de gastos
separada ni una solución de trabajo offline**. Los consumos requieren conexión al servidor.

## Verificación funcional en servidor de pruebas

- Iniciar sesión desde móvil con Registro: Presupuestos e Importar; no Configuración.
- Iniciar sesión como Aprobador: Aprobaciones, Reportes y Dashboard; sin borradores.
- Administrador: todos los accesos y configuración.
- Probar 320, 375, 768 y 1280 píxeles de ancho en navegador.
- Abrir presupuesto y desplazarse por las líneas sin cortar las columnas.
- Probar el dashboard con barra/pastel, mes y cuenta elegidos.
- Confirmar que el menú principal siga funcionando en escritorio.
- Reiniciar Odoo, actualizar módulo, regenerar assets web y recargar navegador.

*Nota:* es necesario comprobar la interfaz real con el tema personalizado de tu servidor,
ya que otros addons pueden alterar el menú móvil de Odoo.
