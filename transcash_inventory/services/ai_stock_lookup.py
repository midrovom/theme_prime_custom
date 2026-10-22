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


def execute_stock_lookup(env, snapshot, question, ui, detected, period, max_rows=1000):
    filters = resolve_stock_filters(env, snapshot, question, ui, detected)
    stock_conditions = validate_stock_conditions(detected['conditions'])
    conditions = ['fp.snapshot_id = %s', 'fp.company_id = %s']
    params = [snapshot.id, snapshot.company_id.id]
    for predicate in stock_conditions:
        conditions.append('fp.stock_unidades ' + predicate['operator'] + ' %s')
        params.append(predicate['value'])
    for field, column in (('categoria', 'categoria'), ('marca', 'marca'), ('proveedor', 'proveedor_ficha')):
        if filters[field]:
            conditions.append('LOWER(TRIM(fp.' + column + ')) = LOWER(TRIM(%s))')
            params.append(filters[field])
    if filters['format_aliases']:
        conditions.append('fp.formato = ANY(%s)')
        params.append(filters['format_aliases'])
    where = ' AND '.join(conditions)
    table = 'transcash_inventory_fact_product'
    sql = ('SELECT fp.sku, fp.name, fp.categoria, fp.marca, fp.formato, '
           'fp.proveedor_ficha, fp.stock_unidades, fp.stock_valor '
           'FROM ' + table + ' fp WHERE ' + where +
           ' ORDER BY fp.stock_unidades ASC, fp.sku ASC LIMIT %s')
    env.cr.execute(sql, params + [max_rows])
    records = env.cr.fetchall()
    env.cr.execute('SELECT COUNT(*), COALESCE(SUM(fp.stock_unidades),0), COALESCE(SUM(fp.stock_valor),0) FROM ' + table + ' fp WHERE ' + where, params)
    count, total_units, total_value = env.cr.fetchone()
    metric_keys = ['descripcion', 'categoria', 'marca', 'formato', 'proveedor_ficha', 'stock_unidades', 'stock_valor']
    labels = {'descripcion': 'Descripción', 'categoria': 'Categoría', 'marca': 'Marca',
              'formato': 'Formato', 'proveedor_ficha': 'Proveedor',
              'stock_unidades': 'Stock · cantidad', 'stock_valor': 'Stock · valor USD'}
    rows = []
    for sku, name, cat, brand, fmt, provider, stock, value in records:
        detail = dict(zip(metric_keys, [name or '', cat or '', brand or '', fmt or '',
                                      provider or '', round(float(stock or 0), 4),
                                      round(float(value or 0), 2)]))
        rows.append({'grupo': sku, 'valor': detail['stock_unidades'], 'metricas': detail})
    return {
        'tipo_resultado': 'listado_stock', 'dimension': 'sku',
        'metrica': 'stock_unidades', 'metricas': metric_keys, 'etiquetas': labels,
        # No sum of unit quantities in the UI: catalog may mix m2 / pieces / boxes.
        'totales': {'stock_unidades': None, 'stock_valor': round(float(total_value), 2)},
        'total': int(count), 'grupos_evaluados': int(count), 'sku_evaluados': int(count),
        'filas': rows, 'total_filas': int(count), 'filas_mostradas': len(rows),
        'periodo': {'desde': period[0], 'hasta': period[1]},
        'filtros': dict({k: v for k, v in filters.items() if k != 'format_aliases'},
                        stock=condition_summary(stock_conditions)),
        'sql_consulta': sql, 'sql_parametros': params + [max_rows],
    }


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
    """Fast DB-resident snapshot fallback; never materializes or calls OpenAI.

    Old imports are already persisted as a compact JSON attachment in Odoo.
    Reading that attachment is preferable to forcing migration of 100k+ fact
    rows during a simple stock query. New/API imports use the SQL facts path.
    """
    import json
    from .ai_analytics import product_format
    dataset = json.loads(snapshot.get_dashboard_json())
    products = dataset.get('products') or []
    filters = _dataset_filters(dataset, question, ui, detected)
    stock_conditions = validate_stock_conditions(detected['conditions'])
    labels = {
        'categoria': dataset.get('categories') or [],
        'marca': dataset.get('brands') or [],
        'proveedor': dataset.get('providers') or [],
    }
    filtered = []
    total_value = 0.0
    for p in products:
        if len(p) < 8:
            continue
        category = labels['categoria'][p[2]]
        brand = labels['marca'][p[3]]
        provider = labels['proveedor'][p[4]]
        fmt = product_format(p)
        stock = float(p[7] or 0)
        if not condition_matches(stock, stock_conditions):
            continue
        if (filters['categoria'] and _norm(category) != _norm(filters['categoria']) or
            filters['marca'] and _norm(brand) != _norm(filters['marca']) or
            filters['proveedor'] and _norm(provider) != _norm(filters['proveedor']) or
            filters['format_aliases'] and fmt not in filters['format_aliases']):
            continue
        value = stock * max(0.0, float(p[5] or 0))
        total_value += value
        filtered.append((str(p[0]), str(p[1]), category, brand, fmt, provider, stock, value))
    filtered.sort(key=lambda row: (row[6], row[0]))
    metrics = ['descripcion', 'categoria', 'marca', 'formato', 'proveedor_ficha', 'stock_unidades', 'stock_valor']
    column_names = {'descripcion': 'Descripción', 'categoria': 'Categoría', 'marca': 'Marca',
                    'formato': 'Formato', 'proveedor_ficha': 'Proveedor',
                    'stock_unidades': 'Stock · cantidad', 'stock_valor': 'Stock · valor USD'}
    result_rows = []
    for sku, name, cat, brand, fmt, prov, stock, value in filtered[:max_rows]:
        fields = dict(zip(metrics, [name, cat, brand, fmt, prov, round(stock, 4), round(value, 2)]))
        result_rows.append({'grupo': sku, 'valor': fields['stock_unidades'], 'metricas': fields})
    return {
        'tipo_resultado': 'listado_stock', 'dimension': 'sku',
        'metrica': 'stock_unidades', 'metricas': metrics, 'etiquetas': column_names,
        'totales': {'stock_unidades': None, 'stock_valor': round(total_value, 2)},
        'total': len(filtered), 'grupos_evaluados': len(filtered), 'sku_evaluados': len(filtered),
        'filas': result_rows, 'total_filas': len(filtered), 'filas_mostradas': len(result_rows),
        'periodo': {'desde': period[0], 'hasta': period[1]},
        'filtros': dict({k: v for k, v in filters.items() if k != 'format_aliases'},
                        stock=condition_summary(stock_conditions)),
        'sql_consulta': '', 'sql_parametros': [],
    }
