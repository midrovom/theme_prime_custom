# Transcash Commissions - Metas y Liquidaciones

Extensión para Odoo 18 que se instala sobre `transcash_commission`. Esta versión mantiene la lógica trabajada de metas y liquidaciones e incorpora carga automática de vendedores relacionados y duplicación controlada de parámetros.

## Funcionalidad vigente

### Metas de vendedores
- La meta del vendedor es global al período; no depende de localidad.
- Todas las ventas del vendedor dentro del período participan en su cumplimiento.
- Solo puede existir una meta por vendedor y período.
- Los rangos de cumplimiento no pueden repetirse dentro de la misma meta.
- Los vendedores sin meta no se generan en la liquidación ni aparecen en los PDF.

### Gestión de administradores
La cabecera se configura por:
- período;
- administrador;
- local cuya meta debe cumplirse.

Al seleccionar el administrador, el detalle carga automáticamente todos los vendedores activos cuyo campo `Administrador responsable` (`commission.seller.manager_id`) apunta a ese administrador.

Cada vendedor del detalle tiene sus propios parámetros:
- tipo de mínimo: monto fijo o porcentaje de su meta;
- mínimo de venta / porcentaje mínimo;
- porcentaje específico de comisión para el administrador;
- base de cálculo;
- activo.

El administrador cobra por un vendedor únicamente cuando:
1. el vendedor supera el mínimo administrativo configurado en su línea; y
2. el local de la cabecera cumple su meta.

La meta propia del vendedor sigue siendo independiente de esta condición, salvo cuando el tipo de mínimo se define expresamente como `% de la meta del vendedor`.

El botón **Cargar vendedores relacionados** permite agregar nuevos vendedores que hayan sido relacionados al administrador después de crear la configuración.

## Duplicación

### Duplicar período y metas
En el formulario del período existe el botón **Duplicar período y metas**.

El sistema:
1. crea un nuevo período en borrador;
2. mantiene la misma duración;
3. busca automáticamente el siguiente rango de fechas disponible para evitar solapamientos;
4. copia las metas de vendedores con todos sus rangos;
5. copia las metas locales;
6. copia las configuraciones de gestión de administradores con todos sus vendedores y porcentajes;
7. no copia ninguna liquidación calculada.

### Duplicar un parámetro individual
En las metas de vendedor, metas de local y gestión de administrador aparece **Duplicar a otro período**.

Se utiliza un asistente para escoger el período destino. El destino debe estar en borrador y ser diferente del período origen.

No se permite duplicar el mismo parámetro dentro del mismo período. Esto evita crear configuraciones ambiguas al usar la función estándar de Odoo `Duplicar`.

## Validaciones contra duplicados

El módulo impide guardar:
- dos metas para el mismo vendedor y período;
- dos metas para el mismo local y período;
- dos gestiones para el mismo administrador + local + período;
- el mismo vendedor dos veces dentro de una gestión;
- el mismo vendedor en dos gestiones activas del mismo período;
- dos rangos idénticos de cumplimiento dentro de una meta de vendedor.

## Reportes
- PDF consolidado de la liquidación.
- PDF individual por vendedor.
- Los vendedores sin meta se excluyen de ambos procesos de liquidación.

## Actualización

Versión técnica: `18.0.1.3.0`.

Para actualizar desde la versión anterior:
1. reemplazar la carpeta `transcash_commission_goal_rules`;
2. reiniciar Odoo;
3. actualizar la lista de aplicaciones si corresponde;
4. ejecutar **Actualizar** sobre el módulo.

No es necesario ejecutar SQL manual.
