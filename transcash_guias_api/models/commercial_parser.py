"""Normalización del contrato comercial del ERP (sin dependencias de Odoo)."""
import unicodedata


def _clean(value):
    return str(value).strip() if value is not None and value is not False else ''


def _key(key):
    raw = unicodedata.normalize('NFKD', _clean(key)).lower()
    return ''.join(ch for ch in raw if not unicodedata.combining(ch)).replace(' ', '_')


def _lookup(mapping, *keys):
    if not isinstance(mapping, dict):
        return ''
    normalized = {_key(k): v for k, v in mapping.items()}
    for key in keys:
        val = normalized.get(_key(key))
        if val is not None and val is not False and _clean(val):
            return _clean(val)
    return ''


def extract_commercial(item):
    """Admite JSON anidado o plano. No atribuye proveedor de transporte a producto.

    El campo ERP `proveedor` del encabezado/filas originales es ambiguo
    y NO se usa como identificador fiscal por inferencia.
    """
    if not isinstance(item, dict):
        return {key: '' for key in (
            'brand_code', 'brand_name', 'supplier_code', 'supplier_name',
            'supplier_tax', 'supplier_reference')}
    brand = item.get('marca') or item.get('Marca') or {}
    supplier = item.get('proveedor_producto') or item.get('Proveedor_producto') or {}
    # marca puede ser un texto en respuestas legacy; no se interpreta como código.
    if not isinstance(brand, dict):
        brand = {'nombre': brand}
    if not isinstance(supplier, dict):
        supplier = {'nombre': supplier}
    return {
        'brand_code': _lookup(brand, 'codigo', 'code') or _lookup(item, 'marca_codigo', 'codigo_marca'),
        'brand_name': _lookup(brand, 'nombre', 'name') or _lookup(item, 'marca_nombre', 'nombre_marca'),
        'supplier_code': _lookup(supplier, 'codigo', 'code') or _lookup(item, 'proveedor_producto_codigo', 'codigo_proveedor_producto'),
        'supplier_name': _lookup(supplier, 'nombre', 'name') or _lookup(item, 'proveedor_producto_nombre', 'nombre_proveedor_producto'),
        'supplier_tax': _lookup(supplier, 'identificacion_fiscal', 'ruc', 'tax_id') or _lookup(item, 'proveedor_producto_ruc', 'proveedor_producto_identificacion'),
        'supplier_reference': _lookup(supplier, 'referencia_erp') or _lookup(item, 'proveedor_producto_referencia'),
    }


def guide_lines(guide):
    if not isinstance(guide, dict):
        return []
    for key in ('detalle', 'lineas', 'productos'):
        if key in guide and isinstance(guide[key], list):
            return guide[key]
    return []
