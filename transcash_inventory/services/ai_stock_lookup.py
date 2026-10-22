# -*- coding: utf-8 -*-
"""Safe, deterministic inventory listing queries (no OpenAI request).

Read exclusively the product facts already populated in Odoo, scoped to the
selected company and import snapshot. No SQL or column names from the user.
"""
import re
from .ai_catalog_filters import _norm, _canonical, catalog_values

# Comparison tokens are only interpreted in the explicit physical-stock clause.
# A list of predicates (rather than a single one) preserves "stock < 100 y > 0".
# Stock is a physical quantity, not an amount in dollars.  Natural language
# frequently inserts a unit phrase between "stock" and "menor/mayor":
#   "el stock en unidades sea menor a 100 y mayor a 0".
# The v1.34 parser silently missed that pattern, causing an OpenAI fallback.
_STOCK_WORD = r'(?:stock|existencias?|inventario\s+(?:actual|disponible))'
_STOCK_QUALIFIER = (r'(?:\s+(?:en\s+)?(?:unidades|unidad(?:es)?|cantidad|fisico|f[ií]sico|disponible|actual))?'
                    r'(?:\s+(?:es|sea|sean|este|est[eé]|esta|est[aá]|que\s+(?:es|sea|este|est[eé])))?')
_CMP = (r'(?:menor(?:es)?\s+(?:a|de|que)|inferior(?:es)?\s+a|'
        r'menos\s+de|por\s+debajo\s+de|debajo\s+de|<=?|'
        r'mayor(?:es)?\s+(?:a|de|que)|superior(?:es)?\s+a|'
        r'm[aá]s\s+de|por\s+encima\s+de|>=?|igual(?:es)?\s+a|=)')
_NUM = r'(-?\d+(?:[.,]\d+)?)'
_STOCK_START = re.compile(r'\b' + _STOCK_WORD + r'\b' + _STOCK_QUALIFIER +
    r'\s*(?P<cmp>' + _CMP + r')\s*(?P<num>' + _NUM + r')', re.IGNORECASE)
_STOCK_NEXT = re.compile(r'\s*(?:,|y|e)\s*(?:(?:con\s+)?' + _STOCK_WORD +
    _STOCK_QUALIFIER + r'\s*)?(?P<cmp>' + _CMP + r')\s*(?P<num>' + _NUM + r')', re.IGNORECASE)
_STOCK_REPEAT = re.compile(r'\b' + _STOCK_WORD + _STOCK_QUALIFIER + r'\s*(?P<cmp>' +
    _CMP + r')\s*(?P<num>' + _NUM + r')', re.IGNORECASE)
_STOCK_BETWEEN = re.compile(r'\b' + _STOCK_WORD + _STOCK_QUALIFIER +
    r'\s+entre\s+(?P<low>' + _NUM + r')\s+y\s+(?P<high>' + _NUM + r')', re.IGNORECASE)
FORMAT_IN_TEXT = re.compile(r'(?<!\d)(\d{1,3}(?:[.,]\d{1,2})?)\s*[x×*]\s*'
                            r'(\d{1,3}(?:[.,]\d{1,2})?)(?!\d)', re.IGNORECASE)


def _make_condition(comparator, raw_number):
    label = _norm(comparator)
    if label.startswith('<='):
        operator = '<='
    elif label.startswith('>='):
        operator = '>='
    elif label == '=' or label.startswith('igual'):
        operator = '='
    elif any(word in label for word in ('mayor', 'superior', 'mas', 'encima', '>')):
        operator = '>'
    else:
        operator = '<'
    value = float(str(raw_number).replace(',', '.'))
    if not -100000000 <= value <= 100000000:
        raise ValueError('La cantidad de stock está fuera del intervalo permitido.')
    return {'operator': operator, 'value': value}


def validate_stock_conditions(conditions):
    """Whitelist operators/numbers, reject contradictions rather than return all."""
    if not isinstance(conditions, list) or not 1 <= len(conditions) <= 6:
        raise ValueError('Indique de una a seis condiciones de stock.')
    validated = []
    minimum, maximum = None, None
    equals = []
    for item in conditions:
        if not isinstance(item, dict):
            raise ValueError('Condición de stock incorrecta.')
        op = item.get('operator')
        if op not in ('<', '<=', '>', '>=', '='):
            raise ValueError('Operador de stock no permitido.')
        try:
            amount = float(item.get('value'))
        except (ValueError, TypeError, OverflowError):
            raise ValueError('Valor numérico de stock no válido.') from None
        import math
        if not math.isfinite(amount) or not -100000000 <= amount <= 100000000:
            raise ValueError('Valor de stock fuera del intervalo permitido.')
        validated.append({'operator': op, 'value': amount})
        if op in ('>', '>='):
            candidate = (amount, op == '>=')
            if minimum is None or candidate[0] > minimum[0] or (candidate[0] == minimum[0] and not candidate[1]):
                minimum = candidate
        elif op in ('<', '<='):
            candidate = (amount, op == '<=')
            if maximum is None or candidate[0] < maximum[0] or (candidate[0] == maximum[0] and not candidate[1]):
                maximum = candidate
        else:
            equals.append(amount)
    if len(set(equals)) > 1 or (minimum and maximum and
       (minimum[0] > maximum[0] or (minimum[0] == maximum[0] and not (minimum[1] and maximum[1])))):
        raise ValueError('Las condiciones de stock son incompatibles.')
    if equals and ((minimum and (equals[0] < minimum[0] or equals[0] == minimum[0] and not minimum[1])) or
                   (maximum and (equals[0] > maximum[0] or equals[0] == maximum[0] and not maximum[1]))):
        raise ValueError('Las condiciones de stock son incompatibles.')
    return validated


def parse_stock_conditions(question):
    """Read every AND-bound stock comparison, including repeated 'stock'.

    Do not treat 60x120 tile dimensions or 12-month periods as stock comparisons.
    """
    phrase = _norm(question)
    between = _STOCK_BETWEEN.search(phrase)
    if between:
        conditions = [{'operator': '>=', 'value': float(between.group('low').replace(',', '.'))},
                      {'operator': '<=', 'value': float(between.group('high').replace(',', '.'))}]
        return validate_stock_conditions(conditions)
    first = _STOCK_START.search(phrase)
    if not first:
        return []
    conditions = [_make_condition(first.group('cmp'), first.group('num'))]
    cursor = first.end()
    while True:
        next_match = _STOCK_NEXT.match(phrase, cursor)
        if not next_match:
            break
        conditions.append(_make_condition(next_match.group('cmp'), next_match.group('num')))
        cursor = next_match.end()
    # Independently mentioned stock comparisons must also be enforced.
    for extra in _STOCK_REPEAT.finditer(phrase):
        if extra.start() == first.start() or first.start() < extra.start() < cursor:
            continue
        conditions.append(_make_condition(extra.group('cmp'), extra.group('num')))
    # Never treat OR as AND and silently change the request.
    if re.search(r'\s+o\s+(?:' + _STOCK_WORD + r'\s*)?' + _CMP + r'\s*' + _NUM, phrase):
        raise ValueError('La comparación con «o» requiere una consulta distinta; utilice condiciones unidas por «y».')
    return validate_stock_conditions(conditions)


def condition_matches(stock, conditions):
    operators = {'<': lambda x,y: x < y, '<=': lambda x,y: x <= y,
                 '>': lambda x,y: x > y, '>=': lambda x,y: x >= y,
                 '=': lambda x,y: x == y}
    return all(operators[item['operator']](stock, item['value']) for item in conditions)


def condition_summary(conditions):
    return ' y '.join('stock %s %g' % (item['operator'], item['value']) for item in conditions)


def canonical_format(value):
    """Convert 60X1.20 / 60*120 / 60×120 into 60x120 (cm)."""
    match = FORMAT_IN_TEXT.search(str(value or ''))
    if not match:
        return _norm(value).replace(' ', '')
    result = []
    for raw in match.groups():
        number = float(raw.replace(',', '.'))
        # Tile measurements are in cm; 1.20 m means 120 cm, unlike 1.20cm.
        if 0 < number < 3 and ('.' in raw or ',' in raw):
            number *= 100
        result.append('%g' % number)
    return 'x'.join(result)


def detect_stock_lookup(question):
    """Direct path for physical-stock SKU listings; never drop extra bounds."""
    normalized = _norm(question)
    if not (re.search(r'\b(cuales|que|lista|listado|listar|muestra|mostrar|muestrame|dame|productos|articulos|skus)\b',
                      normalized) or normalized.startswith('stock')):
        return None
    # Grouped financial requests require the full validated AI/SQL planner.
    # A physical-stock filter does NOT imply that the user wants rows by SKU.
    if re.search(r'\b(?:agrupad[oa]s?\s+por|por\s+(?:marca|categoria|formato|proveedor|mes|bodega))\b', normalized):
        return None
    conditions = parse_stock_conditions(question)
    if not conditions:
        # Do not fall through to the LLM for an explicit stock comparison it
        # cannot read.  A wrong (unfiltered) result would be worse than a clear
        # validation error.  Restrict this guard to list-style stock questions.
        if re.search(r'\b' + _STOCK_WORD + r'\b', normalized) and re.search(
                r'\b(?:menor|mayor|inferior|superior|menos|mas|entre)\b|[<>]=?',
                normalized):
            raise ValueError('No se pudo interpretar el rango de stock físico. Use, por ejemplo, "stock mayor a 0 y menor a 100".')
        return None
    fmt = FORMAT_IN_TEXT.search(question)
    return {'conditions': conditions, 'formato': fmt.group(0) if fmt else ''}


def _question_catalog_value(question, choices, field):
    """Match product attributes as whole tokens, never by substring category."""
    haystack = _norm(question)
    matches = []
    for choice in choices:
        label = _norm(choice)
        if not label or len(label) < 4 or label.startswith('sin '):
            continue
        suffix = r'(?:s|es)?' if field == 'categoria' else ''
        if re.search(r'(?<!\w)' + re.escape(label) + suffix + r'(?!\w)', haystack):
            matches.append(choice)
    if not matches:
        return ''
    matches.sort(key=lambda candidate: len(_norm(candidate)), reverse=True)
    best = matches[0]
    if any(_norm(item) not in _norm(best) and _norm(best) not in _norm(item)
           for item in matches[1:]):
        raise ValueError('Seleccione un solo valor de %s.' % field)
    return best


def resolve_stock_filters(env, snapshot, question, ui, detected):
    result = {}
    for field in ('categoria', 'marca', 'proveedor'):
        choices = catalog_values(env, snapshot, field)
        supplied = str((ui or {}).get(field) or '').strip()
        mentioned = _question_catalog_value(question, choices, field)
        if supplied and mentioned and _canonical(supplied, choices, field) != _canonical(mentioned, choices, field):
            raise ValueError('La pregunta y el filtro de %s seleccionado son diferentes. Corrija el filtro antes de consultar.' % field)
        result[field] = _canonical(supplied or mentioned, choices, field) if (supplied or mentioned) else ''
    choices = catalog_values(env, snapshot, 'formato')
    selected_ui = str((ui or {}).get('formato') or '').strip()
    mentioned_format = str(detected.get('formato') or '').strip()
    if selected_ui and mentioned_format and canonical_format(selected_ui) != canonical_format(mentioned_format):
        raise ValueError('El formato seleccionado es diferente al solicitado. Corrija el filtro de formato.')
    selected = selected_ui or mentioned_format
    if selected:
        same = [v for v in choices if canonical_format(v) == canonical_format(selected)]
        if not same:
            raise ValueError('No existe el formato solicitado en el catálogo: %s.' % selected[:70])
        result['formato'] = sorted(same)[0]
        result['format_aliases'] = sorted(same)
    else:
        result['formato'] = ''
        result['format_aliases'] = []
    return result


def requested_stock_columns(question):
    """Columnas de listado por SKU dinámicas, sin omitir campos solicitados."""
    from .ai_requested_metrics import requested_metrics
    return requested_metrics(question, include_basics=True)


def stock_sort(question):
    """The default is ascending stock; explicit ranking direction overrides it."""
    text = _norm(question)
    if re.search(r'\btop\s+\d+\b', text) or re.search(r'\b(?:mayor|mas\s+alto|descendente)\s+a\s+menor\b|\bde\s+mas\s+a\s+menos\b', text):
        return 'DESC'
    return 'ASC'


def _stock_result(rows, count, total_value, metrics, filters, conditions, period, sql='', params=None):
    from .ai_requested_metrics import METRIC_LABELS
    labels = METRIC_LABELS
    result_rows = []
    for item in rows:
        # Keep field insertion order matching the column layout requested.
        detail = {name: item.get(name) for name in metrics}
        result_rows.append({'grupo': item['sku'], 'valor': detail['stock_unidades'], 'metricas': detail})
    return {
        'tipo_resultado': 'listado_stock', 'dimension': 'sku', 'metrica': 'stock_unidades',
        'metricas': metrics, 'etiquetas': {name: labels[name] for name in metrics},
        # Physical quantities can be m², boxes or pieces: never aggregate incompatible UoMs.
        'totales': {'stock_unidades': None, 'stock_valor': round(float(total_value or 0), 2),
                    'cantidad_vendida': None, 'cantidad_comprada': None,
                    'ventas': None, 'compras': None, 'utilidad': None, 'margen': None, 'costo_ventas': None},
        'total': int(count), 'grupos_evaluados': int(count), 'sku_evaluados': int(count),
        'filas': result_rows, 'total_filas': int(count), 'filas_mostradas': len(result_rows),
        'periodo': {'desde': period[0], 'hasta': period[1]},
        'filtros': dict({k: v for k, v in filters.items() if k != 'format_aliases'},
                        stock=condition_summary(conditions)),
        'sql_consulta': sql, 'sql_parametros': params or [],
    }


def execute_stock_lookup(env, snapshot, question, ui, detected, period, max_rows=1000):
    """Stock-filtered product listing, with independently aggregated sales/purchases.

    Sales and purchases are reduced to one row per product before either join.
    No MxN multiplication, no arbitrary SQL supplied by the LLM or the user.
    """
    filters = resolve_stock_filters(env, snapshot, question, ui, detected)
    conditions = validate_stock_conditions(detected['conditions'])
    metrics = requested_stock_columns(question)
    predicates = ['fp.snapshot_id = %s', 'fp.company_id = %s']
    params = [snapshot.id, snapshot.company_id.id]
    for item in conditions:
        predicates.append('fp.stock_unidades ' + item['operator'] + ' %s')
        params.append(item['value'])
    for field, col in (('categoria', 'categoria'), ('marca', 'marca'), ('proveedor', 'proveedor_ficha')):
        if filters[field]:
            predicates.append('LOWER(TRIM(fp.' + col + ')) = LOWER(TRIM(%s))')
            params.append(filters[field])
    if filters['format_aliases']:
        predicates.append('fp.formato = ANY(%s)')
        params.append(filters['format_aliases'])
    where = ' AND '.join(predicates)
    table = 'transcash_inventory_fact_product'
    count_sql = ('SELECT COUNT(*), COALESCE(SUM(fp.stock_valor),0) FROM ' +
                 table + ' fp WHERE ' + where)
    env.cr.execute(count_sql, list(params))
    count, total_value = env.cr.fetchone()

    from .ai_requested_metrics import sort_metric
    requested_order = sort_metric(question)
    top_match = re.search(r'\btop\s*(\d{1,3})\b', _norm(question))
    if top_match:
        max_rows = max(1, min(100, int(top_match.group(1))))
    query_params = list(params)
    ctes = ['filtered AS (SELECT fp.* FROM ' + table + ' fp WHERE ' + where + ')']
    joins = []
    extra = []
    needs_sale = bool(set(metrics) & {
        'cantidad_vendida', 'ultima_venta', 'ventas', 'costo_ventas',
        'utilidad', 'margen', 'precio_promedio'}) or requested_order in ('ventas', 'utilidad', 'margen')
    needs_purchase = bool(set(metrics) & {'cantidad_comprada', 'ultima_compra', 'compras'}) or requested_order == 'compras'
    if needs_sale:
        ctes.append("""sales AS (SELECT s.product_id,
            SUM(CASE WHEN s.mes BETWEEN %s AND %s THEN s.cantidad_vendida ELSE 0 END) AS qty,
            SUM(CASE WHEN s.mes BETWEEN %s AND %s THEN s.ventas ELSE 0 END) AS amount,
            SUM(CASE WHEN s.mes BETWEEN %s AND %s THEN s.costo_ventas ELSE 0 END) AS cost,
            MAX(CASE WHEN s.cantidad_vendida > 0 THEN s.mes END) AS latest
            FROM transcash_inventory_fact_sale s JOIN filtered f ON f.id=s.product_id
            WHERE s.snapshot_id=%s AND s.company_id=%s GROUP BY s.product_id)""")
        query_params.extend([period[0], period[1]] * 3 + [snapshot.id, snapshot.company_id.id])
        joins.append('LEFT JOIN sales vs ON vs.product_id=fp.id')
        sale_sql = {
            'cantidad_vendida': 'COALESCE(vs.qty,0)',
            'ventas': 'COALESCE(vs.amount,0)',
            'costo_ventas': 'COALESCE(vs.cost,0)',
            'utilidad': '(COALESCE(vs.amount,0)-COALESCE(vs.cost,0))',
            'margen': '(CASE WHEN COALESCE(vs.amount,0) <> 0 THEN '
                      '100.0*(COALESCE(vs.amount,0)-COALESCE(vs.cost,0))/vs.amount END)',
            'precio_promedio': '(CASE WHEN COALESCE(vs.qty,0) <> 0 THEN vs.amount/vs.qty END)',
            'ultima_venta': 'vs.latest',
        }
        for key in ('cantidad_vendida', 'ventas', 'costo_ventas', 'utilidad',
                    'margen', 'precio_promedio', 'ultima_venta'):
            if key in metrics:
                extra.append(sale_sql[key] + ' AS ' + key)
    else:
        sale_sql = {}
    if needs_purchase:
        ctes.append("""purchases AS (SELECT b.product_id,
            SUM(CASE WHEN b.mes BETWEEN %s AND %s THEN b.cantidad_comprada ELSE 0 END) AS qty,
            SUM(CASE WHEN b.mes BETWEEN %s AND %s THEN b.compras ELSE 0 END) AS amount,
            MAX(CASE WHEN b.cantidad_comprada > 0 THEN b.mes END) AS latest
            FROM transcash_inventory_fact_purchase b JOIN filtered f ON f.id=b.product_id
            WHERE b.snapshot_id=%s AND b.company_id=%s GROUP BY b.product_id)""")
        query_params.extend([period[0], period[1]] * 2 + [snapshot.id, snapshot.company_id.id])
        joins.append('LEFT JOIN purchases ps ON ps.product_id=fp.id')
        if 'cantidad_comprada' in metrics:
            extra.append('COALESCE(ps.qty,0) AS cantidad_comprada')
        if 'compras' in metrics:
            extra.append('COALESCE(ps.amount,0) AS compras')
        if 'ultima_compra' in metrics:
            extra.append('ps.latest AS ultima_compra')
    base_cols = ['fp.sku', 'fp.name AS descripcion', 'fp.categoria', 'fp.marca',
                 'fp.formato', 'fp.proveedor_ficha', 'fp.stock_unidades', 'fp.stock_valor']
    sort_expressions = {'stock_unidades': 'fp.stock_unidades',
                        'ventas': sale_sql.get('ventas', 'fp.stock_unidades'),
                        'utilidad': sale_sql.get('utilidad', 'fp.stock_unidades'),
                        'margen': sale_sql.get('margen', 'fp.stock_unidades'),
                        'compras': 'COALESCE(ps.amount,0)' if needs_purchase else 'fp.stock_unidades'}
    sort_expression = sort_expressions[requested_order]
    sql = ('WITH ' + ', '.join(ctes) + ' SELECT ' + ', '.join(base_cols + extra) +
           ' FROM filtered fp ' + ' '.join(joins) +
           ' ORDER BY ' + sort_expression + ' ' + stock_sort(question) +
           ' NULLS LAST, fp.sku ASC LIMIT %s')
    env.cr.execute(sql, query_params + [max_rows])
    columns = ['sku', 'descripcion', 'categoria', 'marca', 'formato', 'proveedor_ficha',
               'stock_unidades', 'stock_valor'] + [column.split(' AS ')[-1] for column in extra]
    records = [dict(zip(columns, r)) for r in env.cr.fetchall()]
    for record in records:
        for key in set(metrics) & {'stock_unidades', 'stock_valor', 'cantidad_comprada',
                                   'cantidad_vendida', 'ventas', 'compras', 'utilidad',
                                   'margen', 'precio_promedio', 'costo_ventas'}:
            if key in record:
                record[key] = (None if record[key] is None else
                               round(float(record[key]), 2 if key in ('stock_valor', 'ventas',
                               'compras', 'utilidad', 'costo_ventas', 'precio_promedio', 'margen') else 4))
    return _stock_result(records, count, total_value, metrics, filters, conditions, period,
                         sql, query_params + [max_rows])


def _dataset_filters(dataset, question, ui, detected):
    """Resolve filters against the stored Odoo snapshot when SQL facts aren't built."""
    from .ai_catalog_filters import _canonical
    from .ai_analytics import product_format
    result = {}
    choices_map = {
        'categoria': dataset.get('categories') or [],
        'marca': dataset.get('brands') or [],
        'proveedor': dataset.get('providers') or [],
    }
    for field, choices in choices_map.items():
        supplied = str((ui or {}).get(field) or '').strip()
        mentioned = _question_catalog_value(question, choices, field)
        if supplied and mentioned and _canonical(supplied, choices, field) != _canonical(mentioned, choices, field):
            raise ValueError('La pregunta y el filtro de %s seleccionado son diferentes.' % field)
        result[field] = _canonical(supplied or mentioned, choices, field) if supplied or mentioned else ''
    formats = sorted({product_format(p) for p in dataset.get('products') or []})
    supplied = str((ui or {}).get('formato') or '').strip()
    mentioned = str(detected.get('formato') or '').strip()
    if supplied and mentioned and canonical_format(supplied) != canonical_format(mentioned):
        raise ValueError('El formato seleccionado es diferente al solicitado. Corrija el filtro de formato.')
    chosen = supplied or mentioned
    if chosen:
        result['format_aliases'] = [fmt for fmt in formats if canonical_format(fmt) == canonical_format(chosen)]
        if not result['format_aliases']:
            raise ValueError('No existe el formato solicitado en el catálogo: %s.' % chosen[:70])
        result['formato'] = result['format_aliases'][0]
    else:
        result['format_aliases'] = []
        result['formato'] = ''
    return result


def execute_stock_lookup_snapshot(snapshot, question, ui, detected, period, max_rows=1000):
    """Legacy snapshot path supports the same requested metrics without OpenAI."""
    import json
    from .ai_analytics import product_format
    dataset = json.loads(snapshot.get_dashboard_json())
    products = dataset.get('products') or []
    filters = _dataset_filters(dataset, question, ui, detected)
    conditions = validate_stock_conditions(detected['conditions'])
    metrics = requested_stock_columns(question)
    labels = {'categoria': dataset.get('categories') or [],
              'marca': dataset.get('brands') or [],
              'proveedor': dataset.get('providers') or []}
    selected = []
    total_value = 0.0
    for idx, p in enumerate(products):
        if len(p) < 8:
            continue
        cat, brand, provider = (labels['categoria'][p[2]], labels['marca'][p[3]],
                                labels['proveedor'][p[4]])
        fmt, stock = product_format(p), float(p[7] or 0)
        if not condition_matches(stock, conditions):
            continue
        if (filters['categoria'] and _norm(cat) != _norm(filters['categoria']) or
            filters['marca'] and _norm(brand) != _norm(filters['marca']) or
            filters['proveedor'] and _norm(provider) != _norm(filters['proveedor']) or
            filters['format_aliases'] and fmt not in filters['format_aliases']):
            continue
        val = stock * max(0.0, float(p[5] or 0))
        total_value += val
        selected.append((idx, {'sku': str(p[0]), 'descripcion': str(p[1]),
                               'categoria': cat, 'marca': brand, 'formato': fmt,
                               'proveedor_ficha': provider, 'stock_unidades': round(stock, 4),
                               'stock_valor': round(val, 2)}))
    selected.sort(key=lambda row: ((-1 if stock_sort(question) == 'DESC' else 1) *
                                   row[1]['stock_unidades'], row[1]['sku']))
    visible = selected[:max_rows]
    visible_ids = {idx for idx, _ in visible}
    indexed = {idx: entry for idx, entry in visible}
    months = dataset.get('months') or []
    if months and (period[0] not in months or period[1] not in months or period[0] > period[1]):
        raise ValueError('El período solicitado no existe en esta versión del inventario.')
    want_s = any(key in metrics for key in ('cantidad_vendida', 'ultima_venta', 'ventas',
                 'costo_ventas', 'utilidad', 'margen', 'precio_promedio'))
    want_b = any(key in metrics for key in ('cantidad_comprada', 'ultima_compra', 'compras'))
    if want_s:
        for sku_i, month_i, qty, *rest in dataset.get('sales') or []:
            if sku_i not in visible_ids:
                continue
            record = indexed[sku_i]
            if period[0] <= months[month_i] <= period[1]:
                if 'cantidad_vendida' in metrics or 'precio_promedio' in metrics:
                    record['cantidad_vendida'] = round(record.get('cantidad_vendida', 0) + float(qty or 0), 4)
                if any(m in metrics for m in ('ventas', 'utilidad', 'margen', 'precio_promedio')):
                    record['ventas'] = record.get('ventas', 0) + float(rest[0] if len(rest)>0 else 0)
                if any(m in metrics for m in ('costo_ventas', 'utilidad', 'margen')):
                    record['costo_ventas'] = record.get('costo_ventas', 0) + float(rest[1] if len(rest)>1 else 0)
            if 'ultima_venta' in metrics and float(qty or 0) > 0:
                record['ultima_venta'] = max(record.get('ultima_venta') or '', months[month_i])
    if want_b:
        for sku_i, month_i, qty, *rest in dataset.get('purchases') or []:
            if sku_i not in visible_ids:
                continue
            record = indexed[sku_i]
            if period[0] <= months[month_i] <= period[1]:
                if 'cantidad_comprada' in metrics:
                    record['cantidad_comprada'] = round(record.get('cantidad_comprada', 0) + float(qty or 0), 4)
                if 'compras' in metrics:
                    record['compras'] = record.get('compras', 0) + float(rest[0] if rest else 0)
            if 'ultima_compra' in metrics and float(qty or 0) > 0:
                record['ultima_compra'] = max(record.get('ultima_compra') or '', months[month_i])
    for record in indexed.values():
        for field in ('cantidad_comprada', 'cantidad_vendida'):
            if field in metrics:
                record.setdefault(field, 0.0)
        for field in ('compras', 'ventas', 'costo_ventas'):
            if field in metrics:
                record.setdefault(field, 0.0)
        if 'utilidad' in metrics:
            record['utilidad'] = round(record.get('ventas', 0.0) - record.get('costo_ventas', 0.0), 2)
        if 'margen' in metrics:
            amount = record.get('ventas', 0.0)
            record['margen'] = round(100 * (amount-record.get('costo_ventas', 0.0)) / amount, 2) if amount else None
        if 'precio_promedio' in metrics:
            qty = record.get('cantidad_vendida', 0.0)
            record['precio_promedio'] = round(record.get('ventas', 0.0) / qty, 2) if qty else None
        for field in ('ultima_compra', 'ultima_venta'):
            if field in metrics:
                record.setdefault(field, None)
    return _stock_result([item for _, item in visible], len(selected), total_value,
                         metrics, filters, conditions, period)
