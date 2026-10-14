# TRANSCASH — Inventario Inteligente (Odoo 18 Community)

Módulo independiente para Odoo 18 Community que mantiene el mismo diseño del dashboard HTML de Transcash. La visualización web se carga dentro del cliente backend de Odoo mediante una acción OWL y un iframe del mismo origen. No requiere Enterprise, Inventory de Odoo, internet ni bibliotecas externas para leer el Excel.

## Funcionalidad incluida

- Importación manual de un archivo `.xlsx` con las hojas **Productos**, **Stock**, **Ventas** y **Compras** (estructura del archivo `Analisis Transcash inventarios.xlsx`).
- Procesamiento en el servidor con lectores OOXML estándar, sin `pandas` ni `openpyxl`.
- Ocho apartados: Resumen ejecutivo, ABC/rentabilidad, cobertura/riesgo, simulación de reposición, bodegas, proveedores, explorador de productos y auditoría.
- Filtros interactivos por meses, categoría, marca, bodega y búsqueda de código/descripción/proveedor.
- Exportación CSV de resultados filtrados, detalle SKU y escenario de reposición 30/45/60/90 días.
- Historial de importaciones (cada archivo se guarda como nueva versión) y botón en el formulario histórico para visualizar sus indicadores.
- Separación por empresa de Odoo y grupos de seguridad de consulta e importación.
- Adaptador de análisis preparado para una futura API: `services.processor.build_dataset(productos, stock, ventas, compras, ...)` y `models.snapshot.create_from_dataset(dataset, ...)`.

## Instalación

1. Descomprime el ZIP y copia **solo la carpeta `transcash_inventory`** a un directorio incluido en `addons_path` de Odoo. Compruébalo en tu configuración: `grep '^addons_path' /etc/odoo18wv.conf`.
2. Asegura que el usuario del servicio Odoo pueda leer la carpeta y los archivos, reinicia el servicio Odoo correspondiente.
3. En Odoo: **Aplicaciones → Actualizar lista de aplicaciones**, busca `TRANSCASH | Inventario Inteligente` e instálalo.
4. Ve a **Ajustes → Usuarios** y asigna uno de los roles del módulo: **Consulta de inventarios** o **Responsable de inventarios (importar)**. Los administradores con el grupo Ajustes también pueden gestionar la carga.
5. Abre la aplicación **Inventario Inteligente → Dashboard** y pulsa **Importar Excel**. Carga tu Excel de cuatro hojas; el primer análisis tarda varios segundos dependiendo de CPU/memoria.

### Instalación desde consola (opcional)

Si tu configuración ya incluye la carpeta de complementos y tu entorno virtual está activado, un ejemplo es:

```bash
cd /opt/odoo18wv/odoo18wv
./odoo-bin -c /etc/odoo18wv.conf -d odoo18wv -i transcash_inventory --stop-after-init
```

Usa el **usuario del servicio Odoo**, no root. Verifica antes el nombre de la base, el ejecutable, el entorno virtual, `addons_path` y el nombre del servicio. Haz una copia de seguridad de la base antes de instalar en producción.

## Formato de las hojas Excel

| Hoja | Columnas esperadas |
|---|---|
| Productos | `Codigo`, `descripcion`, `categoria`, `Formato` (opcional), `marca`, `proveedor`, `costo`, `precio` |
| Stock | `producto`, `nBodega`, `Stock`, `Valor` |
| Ventas | `producto`, `cantidad`, `Total_venta`, `Total_costo`, `Mes`, `Anio` |
| Compras | `producto`, `Cantidad`, `Costo`, `Mes`, `Anio`, `Proveedor`, `Valor` |

La carga agrupa movimientos por SKU, mes y, en compras, proveedor. Distingue stock positivo y negativo por bodega. Conserva el valor de origen de Stock únicamente para auditoría y valoriza provisionalmente por `cantidad positiva × costo del catálogo`.

**Límites**: hasta 45 MB `.xlsx`, 320 MB descomprimidos y 350.000 filas por hoja. No hay importación CSV o XLS antiguo en esta versión.

## Permisos y empresas

Los endpoints `/transcash_inventory/dashboard`, `/transcash_inventory/data` y `/transcash_inventory/upload` requieren sesión de Odoo. La carga usa POST con token CSRF, exige rol de responsable y se guarda para la empresa actualmente seleccionada. Los datos se guardan comprimidos en un adjunto de Odoo, no en archivos públicos. El historial y la consulta se limitan a las empresas autorizadas.

## Limitaciones del análisis

- No calcula rotación contable ni GMROI porque la fuente no incluye inventarios promedio históricos valorizados.
- Los datos de venta no están desglosados por bodega. Filtrar una bodega filtra SKU con stock allí, pero **no atribuye ventas a esa bodega**.
- Los planes de compra son escenarios, no pedidos aprobados: faltan plazos de entrega, mercancía en tránsito, pedidos abiertos, stock reservado, mínimos de compra y presupuesto.
- Los movimientos mensuales no permiten establecer última fecha exacta de venta; la identificación de demanda se basa en ventas netas agregadas por mes.
- Las etiquetas de recomendación y ABC global utilizan los últimos 12 meses de referencia completos disponibles. El ABC mostrado por pantalla se recalcula por filtros; las recomendaciones globales no se recalculan con cada periodo seleccionado.
- El estado de stock proviene de una fotografía sin fecha explícita; validar contra el inventario físico/contable.
- La API externa **no está conectada aún**: el procesador compartido permite incorporarla en una segunda etapa sin cambiar el diseño HTML.

## Probar una importación

El Excel `Analisis Transcash inventarios.xlsx` analizado debe producir aproximadamente estos resultados (últimos 12 meses completos, oct/2025-sep/2026):

- 16.150 SKU consolidados (16.127 registros de Productos).
- Ventas: USD 23.790.118,40.
- Utilidad bruta: USD 6.352.490,39.
- Compras: USD 19.399.782,21.
- Inventario valorizado provisionalmente: USD 7.218.983,45.
- Stock sin ventas netas en 6 meses: USD 1.939.796,91.

Cualquier variación sustancial en estos importes tras cargar el mismo Excel puede indicar que la exportación cambió, que alguna columna tiene otro significado o que cambió la fecha de referencia.

## Arquitectura

```
transcash_inventory/
├── __manifest__.py
├── models/snapshot.py          # Metadatos e histórico; almacena JSON comprimido
├── services/processor.py       # XLSX → registros normalizados → dashboard JSON
├── controllers/routes.py       # Sesión Odoo, importación CSRF y entrega de datos
├── static/src/dashboard.html   # Maquetación original Transcash
├── static/src/dashboard.css    # Estilo original + ventana de carga
├── static/src/dashboard.js     # Gráficos, filtros y simulador; datos dinámicos
├── static/src/odoo_action.*    # Integración nativa en menú/cliente OWL Odoo
├── security/                    # ACL, grupos y regla multiempresa
└── views/                       # Menú, acción, historial
```

## Verificación efectuada

El importador fue probado en Python con el archivo original y coincidieron sus principales cifras. La visualización fue probada en Chromium con datos servidos de forma simulada: navegación, filtros, panel de reposición, productos y ventana de importación sin errores JavaScript. **No se ha realizado una instalación ni prueba E2E dentro de una instancia real de Odoo 18**; se recomienda instalar en staging antes de producción.
