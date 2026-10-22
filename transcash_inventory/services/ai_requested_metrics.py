# -*- coding: utf-8 -*-
"""Metricas solicitadas en lenguaje natural: catálogo único, sin SQL arbitrario."""
import re
import unicodedata

METRIC_LABELS = {
    'descripcion': 'Descripción', 'categoria': 'Categoría', 'marca': 'Marca',
    'formato': 'Formato', 'proveedor_ficha': 'Proveedor de catálogo',
    'stock_unidades': 'Stock · cantidad', 'stock_valor': 'Stock · valor (USD)',
    'cantidad_comprada': 'Cantidad comprada', 'cantidad_vendida': 'Cantidad vendida',
    'compras': 'Compras (USD)', 'ventas': 'Ventas netas (USD)',
    'costo_ventas': 'Costo de ventas (USD)', 'utilidad': 'Utilidad bruta (USD)',
    'margen': 'Margen bruto (%)', 'precio_promedio': 'Precio promedio de venta',
    'ultima_compra': 'Última compra (mes)', 'ultima_venta': 'Última venta (mes)',
}
DISPLAY_COLUMNS = ('descripcion', 'categoria', 'marca', 'formato', 'proveedor_ficha', 'stock_unidades')
MOVEMENT_FIELDS = ('cantidad_comprada', 'cantidad_vendida', 'compras', 'ventas',
                   'costo_ventas', 'utilidad', 'margen', 'precio_promedio')
TEXT_FIELDS = frozenset(('descripcion', 'categoria', 'marca', 'formato',
                         'proveedor_ficha', 'ultima_compra', 'ultima_venta'))

def norm(text):
    text = unicodedata.normalize('NFKD', str(text or ''))
    return ''.join(ch for ch in text if not unicodedata.combining(ch)).lower()

def requested_metrics(question, include_basics=True):
    """Distingue valores USD de cantidades, y rentabilidad bruta de neta."""
    text = norm(question)
    if re.search(r'\b(?:rentabilidad\s+neta|utilidad\s+neta|beneficio\s+neto)\b', text):
        raise ValueError('La rentabilidad neta requiere gastos operativos que no están en los datos del inventario. Puede consultar utilidad y margen BRUTOS.')
    fields = list(DISPLAY_COLUMNS) if include_basics else []
    def add(*names):
        for key in names:
            if key not in fields:
                fields.append(key)
    quantity = bool(re.search(r'\b(?:cantidad(?:es)?|unidades?|volumen|m2|mts?2|metros? cuadrados?)\b', text))
    wants_buy = bool(re.search(r'\b(?:compr(?:a|as|ad[oa]s?)|adquirid[oa]s?)\b', text))
    wants_sale = bool(re.search(r'\b(?:venta(?:s)?|vendid[oa]s?|facturaci[oó]n|facturad[oa]s?)\b', text))
    last_buy = bool(re.search(r'\b(?:ultim[oa]\s+(?:fecha\s+de\s+)?compr|fecha\s+de\s+(?:la\s+)?ultim[oa]\s+compr)\w*', text))
    last_sale = bool(re.search(r'\b(?:ultim[oa]\s+(?:fecha\s+de\s+)?vent|fecha\s+de\s+(?:la\s+)?ultim[oa]\s+vent)\w*', text))
    financial = bool(re.search(r'\b(?:rentabilidad|rentable(?:s)?|margen(?:es)?|utilidad(?:es)?|beneficio(?:s)?|ganancia(?:s)?|ganad[oa]s?)\b', text))
    if wants_buy:
        if quantity or re.search(r'\b(?:cuant[oa]s?|numero\s+de)\b.*\bcompr', text):
            add('cantidad_comprada')
        else:
            add('compras')
    if wants_sale:
        if quantity or re.search(r'\b(?:cuant[oa]s?|numero\s+de)\b.*\bvend', text):
            add('cantidad_vendida')
        else:
            add('ventas')
    if re.search(r'\b(?:valor|importe|monto|total|dolares|usd|\$)\b', text):
        if wants_buy: add('compras')
        if wants_sale: add('ventas')
    if re.search(r'\b(?:costo\s+(?:de\s+)?ventas?|costos?\s+vendid[oa]s?)\b', text):
        add('costo_ventas')
    if financial:
        # Rentabilidad sin calificador = utilidad bruta y margen bruto, ambas.
        if re.search(r'\b(?:rentabilidad|rentable|rentables)\b', text):
            add('utilidad', 'margen')
        if re.search(r'\b(?:utilidad|utilidades|beneficio|beneficios|ganancia|ganancias)\b', text):
            add('utilidad')
        if re.search(r'\b(?:margen|margenes|porcentaje)\b', text):
            add('margen')
    if re.search(r'\b(?:precio\s+(?:promedio|medio)|ticket\s+medio)\b', text):
        add('precio_promedio')
    if re.search(r'\b(?:capital\s+inmovilizad[oa]|valor(?:izad[oa])?\s+(?:del\s+)?(?:stock|inventario))\b', text):
        add('stock_valor')
    if last_buy: add('ultima_compra')
    if last_sale: add('ultima_venta')
    return fields

def sort_metric(question):
    """Siempre devuelve un identificador fijo, nunca una expresion SQL del usuario."""
    text = norm(question)
    # Priorización explícita de orden, de lo contrario stock físico.
    if re.search(r'(?:ordenad[oa]s?\s+por|clasificad[oa]s?\s+por|ranking\s+de|top\s+\d+\s+(?:por|de))\s+(?:la\s+|el\s+)?(?:mayor(?:es)?\s+)?(?:utilidad|ganancia|rentabilidad|margen|venta|compra|stock)', text):
        if 'margen' in text or 'rentabilidad porcentual' in text: return 'margen'
        if 'utilidad' in text or 'ganancia' in text or 'rentabilidad' in text: return 'utilidad'
        if 'venta' in text: return 'ventas'
        if 'compra' in text: return 'compras'
    return 'stock_unidades'
