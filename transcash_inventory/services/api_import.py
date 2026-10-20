# -*- coding: utf-8 -*-
"""Adapter for the existing api.administrator module, using four named GET endpoints.

No URL/token is stored here. In the ERP the API Administrator config owns those.
Both Excel and API converge into build_dataset -> snapshots -> SQL fact models.
"""
import datetime
import json
import re
from .processor import build_dataset, normalize, InventoryImportError

ENDPOINTS = {
    'productos': 'getproductosinvt',
    'ventas': 'getventasinvt',
    'compras': 'getcomprasinvt',
    'stock': 'getstockinvt',
}
LIMIT = 400000


class APIInventoryError(ValueError):
    pass


def _unpack(raw, endpoint):
    """Unwrap common API Administrator / ERP response envelopes safely."""
    if hasattr(raw, 'json') and callable(raw.json):
        raw = raw.json()
    if isinstance(raw, (bytes, str)):
        try:
            raw = json.loads(raw)
        except (TypeError, ValueError):
            raise APIInventoryError('%s no devolvió JSON válido.' % endpoint) from None
    for _ in range(5):
        if isinstance(raw, list):
            if len(raw) > LIMIT:
                raise APIInventoryError('%s supera el límite de registros por carga.' % endpoint)
            if any(not isinstance(item, dict) for item in raw):
                raise APIInventoryError('%s debe devolver registros JSON de tipo objeto.' % endpoint)
            return raw
        if not isinstance(raw, dict):
            raise APIInventoryError('%s devolvió un formato de respuesta no admitido.' % endpoint)
        if raw.get('success') is False or raw.get('ok') is False or raw.get('error'):
            raise APIInventoryError('%s informó un error. Revise la bitácora de API Administrator.' % endpoint)
        for key in ('data', 'result', 'results', 'items', 'rows', 'records', 'response', 'payload'):
            if key in raw and isinstance(raw[key], (dict, list)):
                raw = raw[key]
                break
        else:
            # a single data record is valid; metadata-only response is not
            return [raw]
    raise APIInventoryError('%s tiene demasiados niveles anidados.' % endpoint)


def _field(row, *names):
    normalized = {normalize(k): v for k, v in row.items()}
    for name in names:
        key = normalize(name)
        if key in normalized and normalized[key] is not None:
            return normalized[key]
    return None


def _required(row, endpoint, label, *keys):
    value = _field(row, *keys)
    if value is None or str(value).strip() == '':
        raise APIInventoryError('%s: falta el campo %s en uno de los registros.' % (endpoint, label))
    return value


def _period(row, endpoint):
    year = _field(row, 'anio', 'ano', 'year', 'ejercicio')
    month = _field(row, 'mes', 'month', 'mes_numero', 'numero_mes')
    if year is not None and month is not None:
        try:
            y, m = int(float(year)), int(float(month))
            if 2000 <= y <= 2100 and 1 <= m <= 12:
                return y, m
        except (TypeError, ValueError):
            pass
    date = _field(row, 'periodo', 'fecha', 'date', 'fecha_documento', 'fecha_movimiento', 'year_month', 'period')
    if date is not None:
        match = re.match(r'^\s*(20\d\d)[-/](\d{1,2})(?:[-/].*)?\s*$', str(date))
        if match and 1 <= int(match.group(2)) <= 12:
            return int(match.group(1)), int(match.group(2))
    raise APIInventoryError('%s: se requiere anio y mes, o fecha/periodo YYYY-MM.' % endpoint)


def _sku(row, endpoint):
    return str(_required(row, endpoint, 'SKU', 'codigo', 'sku', 'producto',
                         'default_code', 'product_code', 'codproducto', 'producto_codigo')).strip()


def _numeric(row, endpoint, label, *names, required=True):
    value = _required(row, endpoint, label, *names) if required else _field(row, *names)
    if value is None or str(value).strip() == '':
        return 0.0
    try:
        value = float(value)
        if not (-1e15 < value < 1e15):
            raise ValueError()
        return value
    except (TypeError, ValueError):
        raise APIInventoryError('%s: %s debe ser numérico.' % (endpoint, label)) from None


def _map_product(row):
    return {
        'codigo': _sku(row, ENDPOINTS['productos']),
        'descripcion': str(_required(row, ENDPOINTS['productos'], 'nombre/descripción',
                       'descripcion', 'nombre', 'name', 'nombre_producto', 'product_name')).strip(),
        'categoria': str(_field(row, 'categoria', 'category', 'nombre_categoria', 'categoria_nombre') or 'SIN CATEGORIA').strip(),
        'marca': str(_field(row, 'marca', 'brand', 'nombre_marca', 'marca_nombre') or 'SIN MARCA').strip(),
        'formato': str(_field(row, 'formato', 'format', 'medida', 'dimension', 'formato_nombre') or '').strip(),
        'proveedor': str(_field(row, 'proveedor', 'proveedor_ficha', 'nombre_proveedor', 'supplier', 'proveedor_producto_nombre') or 'SIN PROVEEDOR').strip(),
        'costo': _numeric(row, ENDPOINTS['productos'], 'costo', 'costo', 'costo_unitario', 'cost', 'standard_price', required=False),
        'precio': _numeric(row, ENDPOINTS['productos'], 'precio', 'precio', 'precio_venta', 'price', 'list_price', required=False),
    }


def _map_sale(row):
    endpoint = ENDPOINTS['ventas']
    year, month = _period(row, endpoint)
    return {
        'producto': _sku(row, endpoint), 'anio': year, 'mes': month,
        'cantidad': _numeric(row, endpoint, 'cantidad', 'cantidad', 'cantidad_vendida', 'quantity', 'qty', 'unidades'),
        'total_venta': _numeric(row, endpoint, 'venta neta', 'total_venta', 'venta', 'ventas', 'venta_neta', 'net_sales', 'importe'),
        'total_costo': _numeric(row, endpoint, 'costo de ventas', 'total_costo', 'costo_ventas', 'costo_venta', 'cogs', 'coste_ventas'),
    }


def _map_purchase(row):
    endpoint = ENDPOINTS['compras']
    year, month = _period(row, endpoint)
    result = {
        'producto': _sku(row, endpoint), 'anio': year, 'mes': month,
        'cantidad': _numeric(row, endpoint, 'cantidad', 'cantidad', 'cantidad_comprada', 'quantity', 'qty', 'unidades'),
        'proveedor': str(_field(row, 'proveedor', 'proveedor_compra', 'supplier', 'nombre_proveedor') or 'SIN PROVEEDOR').strip(),
    }
    amount = _field(row, 'valor', 'compras', 'total_compra', 'importe', 'purchase_total')
    if amount is None:
        result['costo'] = _numeric(row, endpoint, 'costo unitario', 'costo', 'costo_unitario', 'cost')
    else:
        result['valor'] = _numeric(row, endpoint, 'valor compra', 'valor', 'compras', 'total_compra', 'importe', 'purchase_total')
    return result


def _map_stock(row):
    endpoint = ENDPOINTS['stock']
    return {
        'producto': _sku(row, endpoint),
        'nbodega': str(_field(row, 'nbodega', 'bodega', 'almacen', 'warehouse', 'nombre_bodega') or 'SIN BODEGA').strip(),
        'stock': _numeric(row, endpoint, 'stock', 'stock', 'cantidad', 'existencia', 'qty', 'on_hand'),
        'valor': _numeric(row, endpoint, 'valor', 'valor', 'valor_stock', required=False),
    }


def convert_api_payloads(payloads, reference_end=None):
    """Build exactly the same dashboard/SQL contract already used by Excel."""
    records = {name: _unpack(payloads[name], endpoint) for name, endpoint in ENDPOINTS.items()}
    if not records['productos']:
        raise APIInventoryError('getproductosinvt devolvió un catálogo vacío. No se creó ninguna versión.')
    if not records['ventas'] and not records['compras']:
        raise APIInventoryError('No existen compras ni ventas; no se puede definir un período de análisis.')
    # build_dataset expects normalized OOXML header keys. API adapters must use
    # the SAME canonicalization as the Excel parser (otherwise total_venta would
    # be silently read as zero because it is not keyed as totalventa).
    def canonical(mapped):
        return {normalize(key): val for key, val in mapped.items()}
    products = [canonical(_map_product(row)) for row in records['productos']]
    sales = [canonical(_map_sale(row)) for row in records['ventas']]
    purchases = [canonical(_map_purchase(row)) for row in records['compras']]
    stock = [canonical(_map_stock(row)) for row in records['stock']]
    known = {p['codigo'] for p in products}
    orphan = set(r['producto'] for r in sales + purchases + stock) - known
    if orphan:
        raise APIInventoryError('%s SKU de movimientos no existen en getproductosinvt; ejemplo: %s.' %
                                (len(orphan), ', '.join(sorted(orphan)[:4])))
    try:
        result = build_dataset(products, stock, sales, purchases, reference_end=reference_end)
    except InventoryImportError as exc:
        raise APIInventoryError(str(exc)) from exc
    result['source']['integration'] = 'API Administrator'
    result['source']['endpoints'] = list(ENDPOINTS.values())
    return result, {key: len(rows) for key, rows in records.items()}


def fetch_from_api_administrator(env):
    """Invoke preconfigured endpoints; never configure URLs or credentials here.

    Compatible with the previously integrated API Administrator contract:
    env['api.administrator'].call_api('endpoint', method='get', company_id=id).
    """
    if 'api.administrator' not in env.registry:
        raise APIInventoryError('No está instalado el módulo API Administrator (api.administrator).')
    admin = env['api.administrator']
    callable_api = getattr(admin, 'call_api', None)
    if not callable(callable_api):
        raise APIInventoryError('API Administrator no dispone del método call_api requerido.')
    payloads = {}
    for name, endpoint in ENDPOINTS.items():
        try:
            payloads[name] = callable_api(endpoint, method='get', company_id=env.company.id)
        except Exception:
            # Avoid exposing tokens, passwords, URLs or server response bodies to clients.
            raise APIInventoryError('No se pudo consultar %s. Revise API Administrator y su registro de errores.' % endpoint) from None
    return payloads
