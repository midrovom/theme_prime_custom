# -*- coding: utf-8 -*-
"""Importador XLSX y contrato de datos del dashboard Transcash.

Sin dependencias externas: usa el formato OOXML estándar y procesa filas
incrementalmente. `build_dataset` también sirve para una futura integración API.
"""
import collections
import datetime
import calendar
import io
import math
import posixpath
import re
import statistics
import unicodedata
import xml.etree.ElementTree as ET
import zipfile

_MAIN = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
_REL = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
_PACKAGE_REL = 'http://schemas.openxmlformats.org/package/2006/relationships'
NS = {'x': _MAIN}
ACTIONS = ['COMPRAR', 'MANTENER', 'REDUCIR', 'SUSPENDER / LIQUIDAR', 'REVISAR', 'SIN ACTIVIDAD / SIN STOCK']
MAX_FILE = 45 * 1024 * 1024
MAX_UNCOMPRESSED = 320 * 1024 * 1024
MAX_ROWS = 350000


class InventoryImportError(ValueError):
    pass


def normalize(label):
    label = unicodedata.normalize('NFKD', str(label or ''))
    return re.sub(r'[^a-z0-9]+', '', ''.join(c for c in label if not unicodedata.combining(c)).lower())


def number(value):
    if value in (None, ''):
        return 0.0
    try:
        x = float(value)
    except (ValueError, TypeError, OverflowError):
        return 0.0
    return x if math.isfinite(x) else 0.0


def value(row, *alternatives, default=''):
    for k in alternatives:
        k = normalize(k)
        if k in row:
            return row[k]
    return default


def text(value):
    return str(value if value is not None else '').strip()


def month_key(row):
    year = int(number(value(row, 'Anio', 'Año', 'Year')))
    month = int(number(value(row, 'Mes', 'Month')))
    if year < 2000 or year > 2100 or not 1 <= month <= 12:
        return None
    return '%04d-%02d' % (year, month)


def _letters_to_index(ref):
    acc = 0
    for c in ref:
        if not c.isalpha():
            break
        acc = acc * 26 + (ord(c.upper()) - 64)
    return acc - 1


def _sheet_paths(book):
    wb = ET.fromstring(book.read('xl/workbook.xml'))
    rels = ET.fromstring(book.read('xl/_rels/workbook.xml.rels'))
    locs = {r.get('Id'): r.get('Target') for r in rels.findall('{%s}Relationship' % _PACKAGE_REL)}
    paths = {}
    for node in wb.findall('x:sheets/x:sheet', NS):
        target = locs.get(node.get('{%s}id' % _REL), '')
        if not target:
            continue
        path = target.lstrip('/') if target.startswith('/') else posixpath.normpath(posixpath.join('xl', target))
        if not path.startswith('xl/worksheets/') or '..' in path.split('/'):
            raise InventoryImportError('Ruta interna inválida en hoja Excel.')
        paths[normalize(node.get('name'))] = path
    return paths


def _strings(book):
    if 'xl/sharedStrings.xml' not in book.namelist():
        return []
    result = []
    with book.open('xl/sharedStrings.xml') as stream:
        context = ET.iterparse(stream, events=('start', 'end'))
        _, root = next(context)
        for evt, node in context:
            if evt == 'end' and node.tag == '{%s}si' % _MAIN:
                result.append(''.join(t.text or '' for t in node.iter('{%s}t' % _MAIN)))
                node.clear()
                root.clear()
    return result


def _iter_rows(book, path, strings):
    head = None
    count = 0
    with book.open(path) as stream:
        context = ET.iterparse(stream, events=('start', 'end'))
        _, root = next(context)
        for evt, node in context:
            if evt != 'end' or node.tag != '{%s}row' % _MAIN:
                continue
            values = {}
            for c in node.findall('{%s}c' % _MAIN):
                ref = c.get('r', '')
                idx = _letters_to_index(ref)
                if idx < 0 or idx > 250:
                    continue
                v = c.find('{%s}v' % _MAIN)
                if v is not None:
                    raw = v.text or ''
                    if c.get('t') == 's':
                        try:
                            raw = strings[int(raw)]
                        except (IndexError, ValueError):
                            raw = ''
                elif c.get('t') == 'inlineStr':
                    inline = c.find('{%s}is' % _MAIN)
                    raw = ''.join(t.text or '' for t in inline.iter('{%s}t' % _MAIN)) if inline is not None else ''
                else:
                    continue
                values[idx] = raw
            if values:
                if head is None:
                    head = {idx: normalize(v) for idx, v in values.items()}
                else:
                    count += 1
                    if count > MAX_ROWS:
                        raise InventoryImportError('La hoja supera el máximo de %s registros.' % MAX_ROWS)
                    yield {head[idx]: val for idx, val in values.items() if idx in head}
            node.clear()
            root.clear()


def read_xlsx(payload):
    """Lee el Excel original de 4 hojas y produce registros simples."""
    if not payload or len(payload) > MAX_FILE:
        raise InventoryImportError('Excel vacío o superior al límite de 45 MB.')
    if not zipfile.is_zipfile(io.BytesIO(payload)):
        raise InventoryImportError('Solo se admiten archivos .xlsx válidos.')
    with zipfile.ZipFile(io.BytesIO(payload)) as book:
        infos = book.infolist()
        if len(infos) > 1500 or sum(i.file_size for i in infos) > MAX_UNCOMPRESSED:
            raise InventoryImportError('Archivo demasiado grande al descomprimir.')
        paths = _sheet_paths(book)
        needed = ['productos', 'stock', 'ventas', 'compras']
        if any(k not in paths for k in needed):
            raise InventoryImportError('El archivo debe contener las hojas Productos, Stock, Ventas y Compras.')
        shared = _strings(book)
        def rows(name):
            return _iter_rows(book, paths[name], shared)
        return build_dataset(rows('productos'), rows('stock'), rows('ventas'), rows('compras'))


def _months_until(end, n):
    y, m = [int(x) for x in end.split('-')]
    items = []
    for k in range(n):
        yy = y + (m - 1 - k) // 12
        mm = (m - 1 - k) % 12 + 1
        items.append('%04d-%02d' % (yy, mm))
    return list(reversed(items))


def _classify(pairs):
    classified = {}
    positive = [(k, v) for k, v in pairs if v > 0]
    positive.sort(key=lambda a: a[1], reverse=True)
    total = sum(v for k, v in positive)
    cum = 0.0
    for key, amount in positive:
        classified[key] = 'A' if cum / total < .80 else 'B' if cum / total < .95 else 'C'
        cum += amount
    return classified


def build_dataset(products, stocks, sales, purchases, reference_end=None, today=None):
    """Contrato estable del frontend; futuro adaptador API llamará esta función."""
    catalog = {}
    all_skus = set()
    errors = collections.Counter()
    counts = collections.Counter()
    for row in products:
        counts['productos'] += 1
        sku = text(value(row, 'Codigo', 'Producto'))
        if not sku:
            errors['producto_sin_codigo'] += 1
            continue
        if sku in catalog:
            errors['codigo_catalogo_duplicado'] += 1
            continue
        cost = number(value(row, 'Costo'))
        price = number(value(row, 'Precio'))
        # Formato original de la ficha comercial. No inferirlo en el servidor
        # ni alterar la posición de las columnas utilizadas por versiones 1.0-1.6.
        catalog[sku] = (text(value(row, 'Descripcion')) or sku, text(value(row, 'Categoria')) or 'SIN CATEGORIA',
                        text(value(row, 'Marca')) or 'SIN MARCA', text(value(row, 'Proveedor')) or 'SIN PROVEEDOR',
                        cost, price, text(value(row, 'Formato')))
        all_skus.add(sku)
        if cost <= 0:
            errors['costos_cero_o_negativos'] += 1
    qty_stock = collections.defaultdict(float)
    source_stock = 0.0
    for row in stocks:
        counts['stock'] += 1
        sku = text(value(row, 'Producto', 'Codigo'))
        if not sku:
            errors['stock_sin_codigo'] += 1
            continue
        wh = text(value(row, 'nBodega', 'Bodega', 'Almacen')) or 'SIN BODEGA'
        quantity = number(value(row, 'Stock', 'Cantidad'))
        qty_stock[(sku, wh)] += quantity
        source_stock += number(value(row, 'Valor'))
        all_skus.add(sku)
    sale_agg = collections.defaultdict(lambda: [0.0, 0.0, 0.0])
    available_months = set()
    for row in sales:
        counts['ventas'] += 1
        sku = text(value(row, 'Producto', 'Codigo'))
        month = month_key(row)
        if not sku or not month:
            errors['ventas_sin_codigo_o_fecha'] += 1
            continue
        available_months.add(month)
        record = sale_agg[(sku, month)]
        record[0] += number(value(row, 'Cantidad'))
        record[1] += number(value(row, 'Total_venta', 'Venta', 'Venta_neta'))
        record[2] += number(value(row, 'Total_costo', 'Costo_venta', 'Costo_ventas'))
        all_skus.add(sku)
    buy_agg = collections.defaultdict(lambda: [0.0, 0.0])
    supplier_agg = collections.defaultdict(float)
    for row in purchases:
        counts['compras'] += 1
        sku = text(value(row, 'Producto', 'Codigo'))
        month = month_key(row)
        if not sku or not month:
            errors['compras_sin_codigo_o_fecha'] += 1
            continue
        quantity = number(value(row, 'Cantidad'))
        val = value(row, 'Valor', default=None)
        amount = number(val) if val not in (None, '') else quantity * number(value(row, 'Costo'))
        supplier = text(value(row, 'Proveedor')) or 'SIN PROVEEDOR'
        record = buy_agg[(sku, month)]
        record[0] += quantity
        record[1] += amount
        supplier_agg[(sku, month, supplier)] += amount
        available_months.add(month)
        all_skus.add(sku)
    if not all_skus:
        raise InventoryImportError('El Excel no contiene productos válidos.')
    if not available_months:
        raise InventoryImportError('No se encontraron meses válidos de compras ni ventas.')
    today = today or datetime.date.today()
    previous = _months_until('%04d-%02d' % (today.year, today.month), 2)[0]
    cutoff_candidates = [m for m in available_months if m <= previous]
    ref = reference_end or (max(cutoff_candidates) if cutoff_candidates else max(available_months))
    months = _months_until(ref, 36)
    month_index = {month: idx for idx, month in enumerate(months)}
    r12, r6, r3 = months[-12:], months[-6:], months[-3:]
    ref_year, ref_month = map(int, ref.split('-'))
    ref_days_3 = sum(calendar.monthrange(int(m[:4]), int(m[5:]))[1] for m in r3)
    this_ytd = {'%d-%02d' % (ref_year, m) for m in range(1, ref_month + 1)}
    prior_ytd = {'%d-%02d' % (ref_year - 1, m) for m in range(1, ref_month + 1)}
    catalog_defaults = ('', 'SIN CATEGORIA', 'SIN MARCA', 'SIN PROVEEDOR', 0.0, 0.0, '')
    sorted_skus = sorted(all_skus)
    categories = sorted({(catalog.get(s) or (s,) + catalog_defaults[1:])[1] for s in sorted_skus})
    brands = sorted({(catalog.get(s) or (s,) + catalog_defaults[1:])[2] for s in sorted_skus})
    providers = sorted({(catalog.get(s) or (s,) + catalog_defaults[1:])[3] for s in sorted_skus})
    warehouses = sorted({w for _, w in qty_stock})
    purchase_suppliers = sorted({supplier for _, _, supplier in supplier_agg})
    idx_cat = {k: i for i, k in enumerate(categories)}
    idx_brand = {k: i for i, k in enumerate(brands)}
    idx_prov = {k: i for i, k in enumerate(providers)}
    idx_wh = {k: i for i, k in enumerate(warehouses)}
    idx_sup = {k: i for i, k in enumerate(purchase_suppliers)}
    idx_sku = {sku: i for i, sku in enumerate(sorted_skus)}
    sell_map = collections.defaultdict(list)
    for (sku, month), (quantity, revenue, cost) in sale_agg.items():
        if month in month_index:
            sell_map[sku].append((month, quantity, revenue, cost))
    stock_map = collections.defaultdict(list)
    stock_warehouses = []
    for (sku, wh), q in qty_stock.items():
        stock_map[sku].append(q)
        if q != 0:
            stock_warehouses.append([idx_sku[sku], idx_wh[wh], round(q, 4)])
    packed_sales = [[idx_sku[sku], month_index[m], round(q, 4), round(v, 4), round(c, 4)]
                    for (sku, m), (q, v, c) in sale_agg.items() if m in month_index]
    packed_purchases = [[idx_sku[sku], month_index[m], round(q, 4), round(v, 4)]
                        for (sku, m), (q, v) in buy_agg.items() if m in month_index]
    packed_suppliers = [[idx_sku[sku], month_index[m], idx_sup[supplier], round(v, 4)]
                        for (sku, m, supplier), v in supplier_agg.items() if m in month_index]
    rev12 = collections.defaultdict(float)
    profit12 = collections.defaultdict(float)
    for sku, txns in sell_map.items():
        for m, q, v, c in txns:
            if m in r12:
                rev12[sku] += v
                profit12[sku] += v - c
    abc_rev = _classify(rev12.items())
    abc_profit = _classify(profit12.items())
    products_out = []
    stock_value = 0.0
    stagnant_value = 0.0
    excess_value = 0.0
    stagnant_count = 0
    excess_count = 0
    negativeprofit_count = 0
    negativeprofit_amount = 0.0
    replenish_count = 0
    stock_operating = 0.0
    stock_special = 0.0
    stale_operating = 0.0
    stale_special = 0.0
    xyz_codes = {'X': 0, 'Y': 0, 'Z': 0}
    for sku in sorted_skus:
        desc, category, brand, prov, cost, price, product_format = catalog.get(sku, (sku, 'SIN CATEGORIA', 'SIN MARCA', 'SIN PROVEEDOR', 0.0, 0.0, ''))
        if sku not in catalog:
            errors['sku_sin_ficha'] += 1
        volumes = stock_map.get(sku, [])
        stock_pos = sum(max(0.0, q) for q in volumes)
        stock_neg = sum(min(0.0, q) for q in volumes)
        pos_val = stock_pos * max(0.0, cost)
        stock_value += pos_val
        recent = sell_map.get(sku, [])
        def quantities(window):
            return sum(q for m, q, v, c in recent if m in window)
        q3, q6, q12 = quantities(r3), quantities(r6), quantities(r12)
        monthly_volume = [max(0.0, sum(q for m, q, v, c in recent if m == month)) for month in r12]
        active_months = sum(x > 0 for x in monthly_volume)
        mean = statistics.fmean(monthly_volume)
        cv = (statistics.pstdev(monthly_volume) / mean) if mean > 0 else None
        xyz = '—' if cv is None else 'X' if cv <= .5 else 'Y' if cv <= 1 else 'Z'
        if xyz != '—':
            xyz_codes[xyz] += 1
        profit = profit12.get(sku, 0.0)
        coverage = (stock_pos * ref_days_3 / q3) if q3 > 0 else None
        if stock_pos > 0 and q6 <= 0:
            action, reason = 3, 'Stock sin demanda neta en 6 meses; verificar si es muestra, exhibición o reserva antes de liquidar.'
        elif stock_pos <= 0 and q3 <= 0:
            action, reason = 5, 'No hay existencias positivas ni demanda neta en últimos 3 meses.'
        elif stock_pos > 0 and q3 > 0 and coverage >= 180:
            action, reason = 2, 'Cobertura estimada superior a 180 días; revisar sobreinventario.'
        elif q3 > 0 and profit > 0 and (stock_pos == 0 or coverage < 30):
            action, reason = 0, 'Demanda reciente, contribución positiva y cobertura inferior a 30 días; validar reposición.'
        elif q3 > 0 and profit > 0 and coverage is not None:
            action, reason = 1, 'Demanda reciente y margen bruto positivo; mantener cobertura según estrategia.'
        else:
            action, reason = 4, 'Señales mixtas o utilidad no positiva; revisar condiciones comerciales.'
        if action == 0:
            replenish_count += 1
        if stock_pos > 0 and q6 <= 0:
            stagnant_count += 1
            stagnant_value += pos_val
        if stock_pos > 0 and coverage is not None and coverage >= 180:
            excess_count += 1
            excess_value += pos_val
        if rev12.get(sku, 0) > 0 and profit < 0:
            negativeprofit_count += 1
            negativeprofit_amount += profit
        products_out.append([sku, desc, idx_cat[category], idx_brand[brand], idx_prov[prov],
                             round(cost, 5), round(price, 4), round(stock_pos, 4), round(pos_val, 4),
                             round(stock_neg, 4), abc_rev.get(sku, '—'), abc_profit.get(sku, '—'), xyz, action,
                             round(q3, 4), round(q6, 4), round(q12, 4), round(profit, 4), reason, active_months, '', product_format])
    # Bodegas comerciales/especiales: indicador orientativo, no clasificación contable.
    by_sku_q6 = {p[0]: p[15] for p in products_out}
    for (sku, wh), q in qty_stock.items():
        if q <= 0:
            continue
        cost = max(0, (catalog.get(sku) or catalog_defaults)[4])
        vl = q * cost
        special = any(term in normalize(wh) for term in ('exhib', 'muestra', 'danado', 'remate', 'transito', 'faltante'))
        if special:
            stock_special += vl
            if by_sku_q6.get(sku, 0) <= 0: stale_special += vl
        else:
            stock_operating += vl
            if by_sku_q6.get(sku, 0) <= 0: stale_operating += vl
    sales12 = sum(v for (sku, month), (q, v, c) in sale_agg.items() if month in r12)
    profit_total12 = sum(v - c for (sku, month), (q, v, c) in sale_agg.items() if month in r12)
    buys12 = sum(v for (sku, month), (q, v) in buy_agg.items() if month in r12)
    sum_buys_supplier = collections.Counter()
    for (sku, month, supplier), amt in supplier_agg.items():
        if month in r12: sum_buys_supplier[supplier] += amt
    top5 = sum(v for k, v in sum_buys_supplier.most_common(5))
    def period_totals(period):
        rev = profit = 0.0
        for (sku, month), (q, v, c) in sale_agg.items():
            if month in period:
                rev += v
                profit += v-c
        return rev, profit
    sales_current, profit_current = period_totals(this_ytd)
    sales_prior, profit_prior = period_totals(prior_ytd)
    summary = dict(sku=len(sorted_skus), ventas12=round(sales12, 4), util12=round(profit_total12, 4),
                   margen12=profit_total12/sales12 if sales12 else 0,
                   compras12=round(buys12, 4), stock_catalogo=round(stock_value, 4),
                   stock_fuente=round(source_stock, 4), sin_ventas6_capital=round(stagnant_value, 4),
                   sin_ventas6_skus=stagnant_count, sin_ventas6_operativo=round(stale_operating, 4),
                   sin_ventas6_especial=round(stale_special, 4), stock_operativo=round(stock_operating, 4),
                   stock_especial=round(stock_special, 4), stock180=round(excess_value, 4), stock180_skus=excess_count,
                   ventas26=round(sales_current, 4), ventas25=round(sales_prior, 4),
                   util26=round(profit_current, 4), util25=round(profit_prior, 4),
                   ABC_A=sum(p[10] == 'A' for p in products_out),
                   replenishment_candidates=replenish_count,
                   top5supply_share=top5/buys12 if buys12 else 0,
                   negativeprofit_codes=negativeprofit_count, negativeprofit_sum=round(negativeprofit_amount, 4))
    source = dict(start=r12[0], end=ref, lastMonth=ref,
                  stockCostMethod='Stock positivo por bodega × costo de catálogo; no usar Stock.Valor sin conciliación.',
                  stockDate='Sin fecha de corte en hoja Stock.', historicStock=False,
                  productsLines=counts['productos'], stockLines=counts['stock'],
                  salesLines=counts['ventas'], purchasesLines=counts['compras'],
                  ignored= dict(errors), analysisYear=ref_year, cutoffMonth=ref_month)
    return dict(products=products_out, sales=packed_sales, purchases=packed_purchases,
                supplierPurchases=packed_suppliers, stockWarehouses=stock_warehouses,
                months=months, categories=categories, brands=brands, providers=providers,
                warehouses=warehouses, purchaseSuppliers=purchase_suppliers,
                actions=ACTIONS, summary=summary, source=source)
