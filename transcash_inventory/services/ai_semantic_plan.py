# -*- coding: utf-8 -*-
"""Structured recovery for the inventory semantic query language.

The model chooses fields, aggregates and comparisons in JSON.  This module
produces a NEW query *only* from validated virtual-column identifiers. The
existing strict SQL parser reconstructs the final parametrized PostgreSQL
SELECT; no SQL or identifiers from the model reach PostgreSQL unchanged.
"""
import math
import re

from .ai_semantic_sql import COLUMNS, InvalidSemanticSQL, parse_compile

_ALLOWED_FUNCS = {'none', 'sum', 'avg', 'min', 'max', 'count', 'margin'}
_ALLOWED_OPS = {'=', '!=', '>', '<', '>=', '<=', 'ILIKE', 'LIKE', 'BETWEEN', 'IN'}
_IDENTIFIER = re.compile(r'^[a-z][a-z0-9_]{0,45}$')
_NUMBER = re.compile(r'^[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?$')


def _identifier(value, allow_star=False):
    value = str(value or '').strip().lower()
    if allow_star and value == '*':
        return value
    if value not in COLUMNS:
        raise InvalidSemanticSQL('La consulta requiere una columna que no está disponible en inventario.')
    return value


def _alias(value):
    value = str(value or '').strip().lower()
    if value and not _IDENTIFIER.fullmatch(value):
        raise InvalidSemanticSQL('El nombre de una columna calculada no es válido.')
    return value


def _value(value, column):
    if not isinstance(value, str) or len(value) > 250:
        raise InvalidSemanticSQL('Filtro inválido en la consulta.')
    if COLUMNS[column][1] == 'num':
        cleaned = value.strip()
        if not _NUMBER.fullmatch(cleaned):
            raise InvalidSemanticSQL('Una comparación numérica requiere una cantidad.')
        n = float(cleaned)
        if not math.isfinite(n) or abs(n) > 1e15:
            raise InvalidSemanticSQL('Cantidad fuera del rango admitido.')
        return cleaned
    return "'" + value.replace("'", "''") + "'"


def build_semantic_select(plan):
    """Compile a typed AI plan into the restricted virtual SELECT grammar."""
    if not isinstance(plan, dict):
        raise InvalidSemanticSQL('El plan de consulta no está disponible.')
    if plan.get('available') is False:
        raise InvalidSemanticSQL('Esta información no está disponible en el modelo de inventario.')
    selected = plan.get('columns')
    if not isinstance(selected, list) or not 1 <= len(selected) <= 20:
        raise InvalidSemanticSQL('Seleccione de 1 a 20 columnas disponibles.')
    selected_sql = []
    selected_aliases = set()
    aggregated = False
    direct = set()
    for item in selected:
        if not isinstance(item, dict):
            raise InvalidSemanticSQL('Definición de columna inválida.')
        fun = str(item.get('aggregation') or 'none').lower()
        if fun not in _ALLOWED_FUNCS:
            raise InvalidSemanticSQL('Operación de columna no autorizada.')
        alias = _alias(item.get('alias'))
        field = _identifier(item.get('field'), allow_star=fun in ('count', 'margin'))
        if fun == 'none':
            direct.add(field)
            expression = field
        elif fun == 'margin':
            expression = 'MARGEN()'
            aggregated = True
        elif fun == 'count':
            expression = 'COUNT(*)'
            aggregated = True
        else:
            if fun in ('sum','avg') and COLUMNS[field][1] != 'num':
                raise InvalidSemanticSQL('No se pueden sumar atributos de texto.')
            if fun in ('sum','avg') and field == 'margen':
                raise InvalidSemanticSQL('Un margen agrupado requiere MARGEN().')
            expression = fun.upper() + '(' + field + ')'
            aggregated = True
        if alias:
            expression += ' AS ' + alias
        name = alias or (('total_productos' if fun == 'count' else 'margen' if fun == 'margin' else
                         fun + '_' + field if fun != 'none' else field))
        if name in selected_aliases:
            raise InvalidSemanticSQL('Hay columnas con nombres duplicados.')
        selected_aliases.add(name)
        selected_sql.append(expression)
    groups = plan.get('group_by') or []
    if not isinstance(groups, list) or len(groups) > 6:
        raise InvalidSemanticSQL('Agrupación no válida.')
    group_fields = [_identifier(x) for x in groups]
    if len(group_fields) != len(set(group_fields)):
        raise InvalidSemanticSQL('Agrupación repetida.')
    if aggregated:
        if not direct.issubset(set(group_fields)):
            raise InvalidSemanticSQL('Las dimensiones deben incluirse en la agrupación.')
    elif group_fields:
        raise InvalidSemanticSQL('La agrupación debe incluir un indicador agregado.')
    sql = 'SELECT ' + ', '.join(selected_sql) + ' FROM inventario'
    filters = plan.get('filters') or []
    if not isinstance(filters, list) or len(filters) > 30:
        raise InvalidSemanticSQL('Se superó el máximo de filtros.')
    conditions = []
    for flt in filters:
        if not isinstance(flt, dict):
            raise InvalidSemanticSQL('Filtro no válido.')
        field = _identifier(flt.get('field'))
        op = str(flt.get('operator') or '').upper()
        if op not in _ALLOWED_OPS:
            raise InvalidSemanticSQL('Operador de filtro no permitido.')
        if op in ('LIKE','ILIKE') and COLUMNS[field][1] != 'text':
            raise InvalidSemanticSQL('La búsqueda de texto requiere un campo de texto.')
        if op == 'BETWEEN':
            cond = field + ' BETWEEN ' + _value(flt.get('value'), field) + ' AND ' + _value(flt.get('second_value'), field)
        elif op == 'IN':
            vals = flt.get('values')
            if not isinstance(vals,list) or not 1 <= len(vals) <= 30:
                raise InvalidSemanticSQL('Filtro IN sin valores válidos.')
            cond = field + ' IN (' + ', '.join(_value(v, field) for v in vals) + ')'
        else:
            cond = field + ' ' + op + ' ' + _value(flt.get('value'), field)
        conditions.append('(' + cond + ')')
    if conditions:
        sql += ' WHERE ' + ' AND '.join(conditions)
    if group_fields:
        sql += ' GROUP BY ' + ', '.join(group_fields)
    order = plan.get('order_by') or {}
    if not isinstance(order, dict):
        raise InvalidSemanticSQL('Ordenamiento inválido.')
    order_field = str(order.get('field') or '').strip().lower()
    if order_field:
        # Both an aliased output and an authorized source field are allowed.
        if order_field not in selected_aliases and order_field not in COLUMNS:
            raise InvalidSemanticSQL('El campo solicitado para ordenar no está disponible.')
        direction = str(order.get('direction') or 'DESC').upper()
        if direction not in ('ASC', 'DESC'):
            raise InvalidSemanticSQL('Dirección de orden no autorizada.')
        sql += ' ORDER BY ' + order_field + ' ' + direction
    try:
        limit = int(plan.get('limit') or 1000)
    except (TypeError, ValueError):
        raise InvalidSemanticSQL('Límite de filas inválido.') from None
    if not 1 <= limit <= 3000:
        raise InvalidSemanticSQL('El límite de resultados debe ser entre 1 y 3000.')
    sql += ' LIMIT ' + str(limit)
    if len(sql) >= 4000:
        raise InvalidSemanticSQL('La consulta resultante es demasiado extensa.')
    # Double validation: the original strict SQL compiler is the only route
    # to the real database, and it will bind all user-provided values.
    parse_compile(sql)
    return sql
