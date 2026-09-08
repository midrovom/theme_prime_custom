# Transcash Retail Commissions - Odoo 18

Addon para liquidar comisiones a partir de una tabla propia de ventas sincronizadas.

## Cambios de arquitectura de la versión 18.0.2

### 1. Vendedores totalmente independientes de `res.users`

El vendedor es el modelo de negocio `commission.seller`. No hereda ni depende de `res.users` ni de `res.partner`.

Campos principales:

- `code`: código externo (`CodVendedor`).
- `name`: nombre externo (`Vendedor`).
- `role`: vendedor retail, proyectos, administrador o híbrido.
- `manager_id`: administrador responsable, relacionado contra el mismo maestro `commission.seller`.
- `default_location_id`: localidad principal.
- `created_from_sales`: identifica maestros creados automáticamente desde ventas.

### 2. Modelo de ventas

La tabla operativa es `commission.sale`. Conserva tanto los códigos/nombres recibidos como las relaciones a maestros:

- `seller_code`, `seller_name`, `seller_id`.
- `location_code`, `location_name`, `location_id`.
- todos los campos comerciales recibidos desde el origen.
- `quantity`: columna `Cantidad` recibida desde el origen.

La estructura posicional actual es:

```text
Tipo, Numero, Factura, Fecha_Registro, Vence, Cliente,
Vendedor, CodVendedor, bodega, Linea, Marca, Codproducto, nProducto,
Cantidad, costo, Total_Costo, Total_Precio, Porc_Descuento, pTarjeta,
Total_Neto, Indica_Precio, Descuento, Utilidad, PorcUtilidad, Forma_pago,
Proveedor, Origen, localidad, nLocal
```

Para payloads JSON por objeto, `Cantidad` se reconoce sin importar mayúsculas/minúsculas o separadores.

### 3. Creación automática de maestros al insertar ventas

La regla está implementada en `commission.sale.create()`, no solamente en el importador.

Al crear una venta:

1. Si llega `location_code` y no existe, se crea `commission.location` usando `location_code` + `location_name`.
2. Si llega `seller_code` y no existe, se crea `commission.seller` usando `seller_code` + `seller_name`.
3. La venta queda relacionada mediante `location_id` y `seller_id`.
4. Si el vendedor es nuevo y existe localidad, se asigna como localidad principal.
5. Si el maestro ya existe, se reutiliza; si cambió el nombre externo, se actualiza.

Esto funciona para cualquier código que use el ORM de Odoo:

```python
sale = env["commission.sale"].create({
    "registration_date": "2026-02-02",
    "seller_code": "181",
    "seller_name": "VANESSA SIGUENZA",
    "location_code": "SDO",
    "location_name": "010-001 Santo Domingo F/E",
    "quantity": 1.70,
    "total_net": 12.2719,
})
```

No se debe insertar directamente con SQL porque un `INSERT` SQL omite el ORM y, por tanto, las reglas de creación automática de maestros.

### 4. Cantidad / metros cuadrados

Ya no se estima la cantidad con `Total_Costo / costo`.

El bono de productos en liquidación utiliza directamente:

```text
commission.sale.quantity
```

Para `Indica_Precio = 3`, la cantidad se interpreta como m² según la fuente indicada por Transcash.

### 5. Apartado de sincronización

Existe el menú:

**Comisiones > Operación > Sincronización**

Modelo: `commission.sync`.

Cada ejecución registra:

- rango de fechas;
- fecha/hora de inicio y fin;
- filas recibidas;
- ventas creadas;
- duplicados omitidos;
- errores;
- ventas generadas por esa ejecución.

El punto preparado para colocar el código definitivo de consumo está en:

```text
models/sync.py
```

Método:

```python
def _fetch_remote_rows(self):
    ...
```

Este método debe devolver una lista de filas. Después de eso no debe preocuparse por crear vendedores o localidades: `commission.sale.create()` lo hace automáticamente.

Actualmente `_fetch_remote_rows()` contiene un conector REST genérico GET/POST para mantener el módulo ejecutable. La implementación definitiva puede reemplazar ese contenido o heredarlo desde otro addon.

Ejemplo de personalización limpia:

```python
from odoo import models


class CommissionSync(models.Model):
    _inherit = "commission.sync"

    def _fetch_remote_rows(self):
        self.ensure_one()
        # Pegar aquí la estructura real de consumo.
        rows = mi_consumo_transcash(self.date_from, self.date_to)
        return rows
```

### 6. Sincronización automática

El cron ejecuta `commission.sync.cron_synchronize_sales()`.

Los parámetros HTTP genéricos siguen disponibles en **Ajustes sincronización**. También se puede configurar cuántos días volver a consultar; la huella de importación evita volver a crear las mismas ventas.

## Reglas de comisiones conservadas

- períodos de liquidación;
- metas por vendedor y rangos de cumplimiento;
- metas por localidad;
- comisión propia de administradores;
- equipos administrador-vendedores;
- comisión de gestión condicionada por meta local y venta mínima del vendedor;
- reglas de proyectos por vendedor + origen;
- bono de liquidación por `Indica_Precio = 3` y tarifa por m²;
- tipos de documento con signo para devoluciones/notas de crédito;
- liquidaciones auditables con detalle por componente.

## Archivos principales

- `models/master.py`: vendedores y localidades independientes.
- `models/sale.py`: tabla de ventas, normalización, deduplicación y creación automática de maestros.
- `models/sync.py`: capa de sincronización y punto de integración con el consumo definitivo.
- `models/rules.py`: parámetros de comisiones.
- `models/settlement.py`: motor de cálculo.
- `models/period.py`: períodos y ejecución de sincronización desde el período.
- `tests/test_commission.py`: incluye prueba de creación automática de vendedor/localidad y uso de `Cantidad`.

## Instalación / actualización

```bash
./odoo-bin -d NOMBRE_BD -u transcash_commission --stop-after-init
```

La versión del manifest es `18.0.2.0.0`.
