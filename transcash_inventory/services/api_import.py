# -*- coding: utf-8 -*-
"""Adapter for the existing api.administrator module, using four named GET endpoints.

No URL/token is stored here. In the ERP the API Administrator config owns those.
Both Excel and API converge into build_dataset -> snapshots -> SQL fact models.
"""
import datetime
import json
import re
import collections
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


def _date_of_last_transaction(value):
    """Only accept real day-level dates. A YYYY-MM monthly bucket is NOT a date."""
    if value is None or str(value).strip() == '':
        return ''
    raw = str(value).strip()
    iso = re.match(r'^(20\d\d)-(\d{1,2})-(\d{1,2})(?:[T\s].*)?$', raw)
    local = re.match(r'^(\d{1,2})/(\d{1,2})/(20\d\d)(?:[T\s].*)?$', raw)
    dotted = re.match(r'^(20\d\d)\.(\d{1,2})\.(\d{1,2})(?:[T\s].*)?$', raw)
    if iso:
        y, m, d = map(int, iso.groups())
    elif dotted:
        y, m, d = map(int, dotted.groups())
    elif local:
        d, m, y = map(int, local.groups())
    else:
        return ''
    try:
        return datetime.date(y, m, d).isoformat()
    except ValueError:
        return ''


def _optional_last_quantity(row, *names):
    raw = _field(row, *names)
    if raw is None or str(raw).strip() == '':
        return None
    try:
        quantity = float(raw)
    except (TypeError, ValueError) as exc:
        raise APIInventoryError('La cantidad del último movimiento debe ser numérica.') from exc
    if not (-1e12 < quantity < 1e12):
        raise APIInventoryError('Cantidad del último movimiento fuera del rango permitido.')
    return quantity


def _last_movement_fields(row, kind):
    """Optional exact movement fields, never fabricated from monthly aggregates."""
    if kind == 'compra':
        date_fields = ('fecha_ultima_compra', 'ultima_fecha_compra', 'last_purchase_date', 'fecha_ult_compra')
        qty_fields = ('cantidad_ultima_compra', 'ultima_cantidad_compra', 'last_purchase_qty', 'cantidad_ult_compra')
    else:
        date_fields = ('fecha_ultima_venta', 'ultima_fecha_venta', 'last_sale_date', 'fecha_ult_venta')
        qty_fields = ('cantidad_ultima_venta', 'ultima_cantidad_venta', 'last_sale_qty', 'cantidad_ult_venta')
    return (_date_of_last_transaction(_field(row, *date_fields)),
            _optional_last_quantity(row, *qty_fields))


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
    # API endpoints deliver complete, already-consolidated monthly datasets.
    # Last record wins for the SAME natural key *within a single response*.
    # Re-running the same feed must never multiply sales or stock. If endpoints
    # return invoice lines rather than monthly totals, first aggregate them in
    # API Administrator (SKU+year+month [+supplier]).
    keys = {
        'productos': ('codigo',),
        'ventas': ('producto', 'anio', 'mes'),
        'compras': ('producto', 'anio', 'mes', 'proveedor'),
        'stock': ('producto', 'nbodega'),
    }
    adapters = {
        'productos': _map_product, 'ventas': _map_sale,
        'compras': _map_purchase, 'stock': _map_stock,
    }
    deduplicated = {}
    replaced = collections.Counter()
    for name, entries in records.items():
        merged = {}
        for raw in entries:
            item = canonical(adapters[name](raw))
            key = tuple(str(item.get(k, '')).strip() for k in keys[name])
            if key in merged:
                replaced[name] += 1
            merged[key] = item
        deduplicated[name] = list(merged.values())
    products, sales, purchases, stock = (deduplicated[k] for k in ('productos','ventas','compras','stock'))
    known = {p['codigo'] for p in products}
    orphan = set(r['producto'] for r in sales + purchases + stock) - known
    if orphan:
        raise APIInventoryError('%s SKU de movimientos no existen en getproductosinvt; ejemplo: %s.' %
                                (len(orphan), ', '.join(sorted(orphan)[:4])))
    # Exact last-document metadata is OPTIONAL. The four standard feeds contain
    # consolidated MONTHLY purchases/sales; never infer a fictitious day or a
    # document quantity from those monthly totals.  Accept exact fields when
    # ERP supplies them on products, sales or purchase feed rows.
    exact = {}
    for kind, feed in (('productos', records['productos']),
                       ('ventas', records['ventas']), ('compras', records['compras'])):
        for raw in feed:
            sku = str(_field(raw, 'codigo', 'sku', 'producto', 'default_code',
                             'product_code', 'codproducto', 'producto_codigo') or '').strip()
            if sku not in known:
                continue
            slot = exact.setdefault(sku, {'compra': ('', None), 'venta': ('', None)})
            for operation in ('compra', 'venta'):
                if kind not in ('productos', 'compras' if operation == 'compra' else 'ventas'):
                    continue
                observed = _last_movement_fields(raw, operation)
                if observed[0] and (observed[0] > slot[operation][0] or
                                    (observed[0] == slot[operation][0] and
                                     slot[operation][1] is None and observed[1] is not None)):
                    slot[operation] = observed
    try:
        result = build_dataset(products, stock, sales, purchases, reference_end=reference_end)
    except InventoryImportError as exc:
        raise APIInventoryError(str(exc)) from exc
    sku_positions = {p[0]: i for i, p in enumerate(result['products'])}
    result['recentMovements'] = [
        [sku_positions[sku], row['compra'][0], row['compra'][1],
         row['venta'][0], row['venta'][1]]
        for sku, row in sorted(exact.items())
        if sku in sku_positions and (row['compra'][0] or row['venta'][0])
    ]
    result['source']['integration'] = 'API Administrator'
    result['source']['endpoints'] = list(ENDPOINTS.values())
    return result, {key: len(deduplicated[key]) for key in records} | {'reemplazos': dict(replaced)}


def fetch_from_api_administrator(env):
    """Find each configured GET endpoint in API Administrator for the active company.

    The provided core api_administrator addon has no call_api method. Inventory
    extends its record with call_inventory_api, like the working commission bridge.
    Never select API records belonging to other companies.
    """
    if 'api.administrator' not in env.registry:
        raise APIInventoryError('Debe instalar API Administrator para sincronizar inventario.')

    admin = env['api.administrator'].sudo().with_company(env.company)
    payloads = {}
    for name, endpoint in ENDPOINTS.items():
        domain = [
            ('name', '=', endpoint),
            ('type', '=', 'get'),
            ('status', '=', 'A'),
            ('company_id', '=', env.company.id),
        ]
        matches = admin.search(domain, limit=2)
        if not matches:
            raise APIInventoryError(
                'No existe la configuración GET activa "%s" para la empresa seleccionada en API Administrator.' % endpoint
            )
        if len(matches) > 1:
            raise APIInventoryError(
                'Existen varias configuraciones GET activas "%s" para esta empresa. Mantenga solamente una.' % endpoint
            )
        api_record = matches[0]
        try:
            payloads[name] = api_record.call_inventory_api()
        except Exception as exc:
            # Keep URLs, credentials and raw API response bodies out of the UI.
            import logging
            logging.getLogger(__name__).exception(
                'Fallo al consultar endpoint de inventario %s para empresa %s', endpoint, env.company.id
            )
            raise APIInventoryError(
                'No se pudo consultar "%s". Verifique su estado, URL, credenciales y respuesta JSON en API Administrator.' % endpoint
            ) from None
    return payloads
