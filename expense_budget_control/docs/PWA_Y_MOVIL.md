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

## Instalación como PWA de Control de Gastos (v1.4.58)

Odoo 18 ya proporciona una PWA para el backend. Este módulo agrega una
**identidad de instalación propia** denominada "Control de Gastos", con iconos,
manifest y acceso directo que abre la pantalla de Accesos rápidos del módulo.
No instala otro service worker: reutiliza el existente de Odoo y no cachea
información financiera sensible para trabajo sin conexión.

**Requisitos:** dominio con certificado HTTPS válido, sesión de Odoo y un navegador
que admita instalación. La URL pública `http://IP:puerto` no cumple los
requisitos de instalación del navegador.

1. Actualizar `expense_budget_control` y abrir Odoo usando el dominio HTTPS.
2. Iniciar sesión con un usuario que tenga alguno de los roles del módulo.
3. Abrir **Control de Gastos → Accesos rápidos**.
4. Pulsar **Instalar Control de Gastos**, que abre `/expense-budget/pwa`.
5. Android (Chrome): pulsar **Instalar aplicación** si aparece el botón;
   de lo contrario, menú del navegador > **Instalar aplicación**.
6. iPhone (Safari): Compartir > **Añadir a pantalla de inicio**.
7. Abrir el nuevo icono, que inicia directamente la pantalla del módulo.

El manifest específico está en `/expense-budget/pwa/manifest.webmanifest`.
Su identificador es estable; la navegación continúa dentro de Odoo y sigue
respetando los roles y la sesión del usuario. No añade dependencias `pip`.

**Nota:** la instalación completa y el gesto de instalación dependen del
navegador y requieren probarse en un dispositivo físico. La PWA no permite
registrar consumos offline y no sustituye la necesidad de HTTPS.

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
