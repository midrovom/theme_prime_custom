# -*- coding: utf-8 -*-
"""Compiled, read-only inventory SELECTs from model-generated, structured query AST.

No SQL supplied by ChatGPT is executed. A vetted plan is translated using
constant column expressions, fixed CTE relations and psycopg-bound values.
This intentionally does not import Lark: server startup is independent of
parser grammars, vendor package paths and third-party SQL dialects.
"""
import json
import math
import re
from decimal import Decimal
from .ai_semantic_sql import SOURCE, COLUMNS, LABELS, InvalidSemanticSQL

NUMERIC = re.compile(r'^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$')
IDENT = re.compile(r'^[a-z][a-z0-9_]{0,45}$')
OPS = {'none', 'sum', 'avg', 'min', 'max', 'count', 'weighted_margin'}
COMPARATORS = {'=', '!=', '<', '<=', '>', '>=', 'contains', 'not_contains', 'in', 'between', 'is_null', 'is_not_null'}
MAX_QUERY_COLUMNS = 20


def _field(name):
    if not isinstance(name, str) or name not in COLUMNS:
        raise InvalidSemanticSQL('La consulta menciona un campo no disponible en el inventario.')
    return COLUMNS[name]


def _numeric(value):
    raw = str(value).strip()
    if not NUMERIC.fullmatch(raw) or len(raw) > 45:
        raise InvalidSemanticSQL('Una condición numérica debe contener un número válido.')
    number = float(raw)
    if not math.isfinite(number) or abs(number) > 1e18:
        raise InvalidSemanticSQL('El valor numérico está fuera de rango.')
    return number


def _coerce(field, value):
    return _numeric(value) if _field(field)[1] == 'num' else str(value)[:250]


def _conditions(conditions, logic, params, having=False, aliases=None):
    if not isinstance(conditions, list) or len(conditions) > 24 or logic not in ('and','or'):
        raise InvalidSemanticSQL('Los filtros no tienen una estructura válida.')
    pieces=[]
    aliases = aliases or {}
    for obj in conditions:
        if not isinstance(obj, dict):
            raise InvalidSemanticSQL('Filtro no reconocido.')
        name = obj.get('field')
        if having and name in aliases:
            expr, dtype, operation = aliases[name]
            if operation == 'none':
                raise InvalidSemanticSQL('HAVING requiere una columna agregada.')
        elif not having:
            expr, dtype = _field(name)
        else:
            raise InvalidSemanticSQL('HAVING solo admite alias de agregaciones autorizadas.')
        operator = obj.get('operator')
        if operator not in COMPARATORS:
            raise InvalidSemanticSQL('El operador solicitado no está autorizado.')
        value = obj.get('value', '')
        if operator in ('is_null', 'is_not_null'):
            pieces.append('('+expr+' IS '+('NOT ' if operator=='is_not_null' else '')+'NULL)')
            continue
        if operator in ('contains','not_contains'):
            if dtype != 'text':
                raise InvalidSemanticSQL('La búsqueda de texto requiere una columna de texto.')
            v=str(value).replace('\\','\\\\').replace('%','\\%').replace('_','\\_')[:240]
            params.append('%'+v+'%')
            neg='NOT ' if operator=='not_contains' else ''
            pieces.append("(LOWER(COALESCE("+expr+",'')) "+neg+"LIKE LOWER(%s) ESCAPE '\\')")
            continue
        if operator == 'in':
            vals = [v.strip() for v in str(value).split('|') if v.strip()]
            if not vals or len(vals)>30:
                raise InvalidSemanticSQL('La lista de valores debe contener entre 1 y 30 elementos.')
            params.extend(_numeric(v) if dtype=='num' else v[:250] for v in vals)
            transformed = ('LOWER(TRIM(COALESCE('+expr+",'')))" if dtype=='text' else expr)
            if dtype=='text':
                params[-len(vals):] = [v.lower() for v in params[-len(vals):]]
            pieces.append('('+transformed+' IN ('+','.join(['%s']*len(vals))+'))')
            continue
        values=[value, obj.get('value_end','')] if operator=='between' else [value]
        cast=[_numeric(v) if dtype=='num' else str(v)[:250] for v in values]
        if dtype=='text' and operator not in ('=', '!=', 'between'):
            raise InvalidSemanticSQL('Solo se permiten comparaciones de igualdad o intervalo en texto.')
        lhs = ('LOWER(TRIM(COALESCE('+expr+",'')))" if dtype=='text' and operator in ('=','!=') else expr)
        if dtype=='text' and operator in ('=','!='):
            cast=[v.lower().strip() for v in cast]
        params.extend(cast)
        if operator=='between':
            pieces.append('('+lhs+' BETWEEN %s AND %s)')
        else:
            pieces.append('('+lhs+' '+('<>' if operator=='!=' else operator)+' %s)')
    return (' '+logic.upper()+' ').join(pieces)


def compile_plan(plan, scope_filters=None):
    """Compile a model-generated AST to one bounded SELECT and parameters."""
    if not isinstance(plan, dict):
        raise InvalidSemanticSQL('El plan de consulta no es válido.')
    selected=plan.get('columns')
    if not isinstance(selected, list) or not 1<=len(selected)<=MAX_QUERY_COLUMNS:
        raise InvalidSemanticSQL('Seleccione entre 1 y 20 columnas disponibles.')
    output=[]; names=[]; aliases={}; direct=[]; aggregated=False
    for item in selected:
        if not isinstance(item,dict):
            raise InvalidSemanticSQL('Definición de columna no válida.')
        field=item.get('field'); expr,dtype=_field(field)
        operation=item.get('operation')
        if operation not in OPS:
            raise InvalidSemanticSQL('Operación de columna no permitida.')
        if operation in ('sum','avg') and dtype != 'num':
            raise InvalidSemanticSQL('No se puede sumar ni promediar una descripción.')
        if operation in ('sum','avg') and field=='margen':
            raise InvalidSemanticSQL('El porcentaje debe calcularse mediante margen ponderado.')
        if operation=='weighted_margin' and field!='margen':
            raise InvalidSemanticSQL('El margen ponderado solo aplica al campo margen.')
        alias = (item.get('alias') or (field if operation=='none' else operation+'_'+field)).strip().lower()
        if not IDENT.fullmatch(alias) or alias in names:
            raise InvalidSemanticSQL('Alias de columna duplicado o incorrecto.')
        if operation=='none':
            direct.append(field)
            expression=expr
        elif operation=='count':
            expression='COUNT(*)'
            dtype='num'; aggregated=True
        elif operation=='weighted_margin':
            expression='ROUND((100.0*SUM(inv.utilidad)/NULLIF(SUM(inv.ventas),0))::numeric,2)'
            dtype='num'; aggregated=True
        else:
            expression=operation.upper()+'('+expr+')'
            aggregated=True
        output.append(expression+' AS "'+alias+'"')
        aliases[alias]=(expression, dtype, operation)
        names.append(alias)
    groups=plan.get('group_by', [])
    if not isinstance(groups,list) or len(groups)>6 or len(set(groups))!=len(groups):
        raise InvalidSemanticSQL('La agrupación contiene campos repetidos o no válidos.')
    for name in groups:
        _field(name)
    if aggregated:
        # Non-aggregated fields must be grouped to prevent a SQL error. They
        # are explicitly selected by the model, so this cannot broaden access.
        for field in direct:
            if field not in groups:
                groups.append(field)
        if len(groups)>8:
            raise InvalidSemanticSQL('La agrupación contiene demasiados atributos.')
    elif groups:
        # SELECT DISTINCT is the semantic meaning of grouping without measures.
        for field in groups:
            if field not in direct:
                raise InvalidSemanticSQL('Para agrupar se deben incluir los atributos seleccionados.')
    wh_params=[]
    where=_conditions(plan.get('filters', []),plan.get('filter_logic','and'),wh_params)
    sql='SELECT '+('DISTINCT ' if groups and not aggregated else '')+', '.join(output)+' FROM inventario inv'
    wh=[where] if where else []
    for key,value in (scope_filters or {}).items():
        if key not in ('categoria','marca','formato','proveedor') or not str(value or '').strip():
            continue
        wh.append('LOWER(TRIM(COALESCE('+COLUMNS[key][0]+",''))) = LOWER(TRIM(%s))")
        wh_params.append(str(value)[:120])
    if wh:
        sql+=' WHERE '+' AND '.join('('+cond+')' for cond in wh)
    if groups and aggregated:
        sql+=' GROUP BY '+', '.join(_field(field)[0] for field in groups)
    hparams=[]
    having=_conditions(plan.get('having', []),plan.get('having_logic','and'),hparams,True,aliases)
    if having:
        if not aggregated:
            raise InvalidSemanticSQL('HAVING requiere una agregación.')
        sql+=' HAVING '+having
    sort=plan.get('order_by','')
    direction=plan.get('order_direction','desc')
    if direction not in ('asc','desc'):
        raise InvalidSemanticSQL('El orden debe ser ascendente o descendente.')
    if sort:
        if sort in aliases:
            order='"'+sort+'"'
        elif sort in groups:
            order=_field(sort)[0]
        else:
            raise InvalidSemanticSQL('Solo se puede ordenar por una columna visible o agrupada.')
        sql+=' ORDER BY '+order+' '+direction.upper()
    limit=plan.get('limit',1000)
    if type(limit)!=int or not 1<=limit<=3000:
        raise InvalidSemanticSQL('El máximo de filas de la consulta debe estar entre 1 y 3000.')
    sql+=' LIMIT %s'
    return sql,wh_params+hparams+[limit],names,{'group':groups,'aggregated':aggregated,'limit':limit}


def execute_semantic_plan(env, snapshot, plan, default_start, default_end, scope_filters=None):
    months=json.loads(snapshot.relational_months or '[]')
    if (not months or default_start not in months or default_end not in months
            or default_start>default_end):
        raise InvalidSemanticSQL('No hay un período válido para la consulta.')
    query,params,names,meta=compile_plan(plan,scope_filters)
    scope=(snapshot.id,snapshot.company_id.id)
    base=[scope[0],scope[1],default_start,default_end,
          scope[0],scope[1],default_start,default_end,
          scope[0],scope[1],scope[0],scope[1],scope[0],scope[1]]
    with env.cr.savepoint():
        env.cr.execute("SET LOCAL statement_timeout = '18s'")
        env.cr.execute("SET LOCAL lock_timeout = '5s'")
        env.cr.execute(SOURCE+query,base+params)
        rows=env.cr.fetchall()
    result=[]
    for row in rows:
        vals={k:(round(float(v),4) if isinstance(v,(float,int,Decimal)) else v) for k,v in zip(names,row)}
        group=next((str(vals[k]) for k in names if k in ('sku','formato','categoria','marca','proveedor','descripcion')), 'TOTAL')
        result.append({'grupo':group,'valor': vals.get(names[0]),'metricas':vals})
    # The renderer and Excel must format alias columns by their source field,
    # e.g. 'beneficio' from utilidad remains USD and weighted margin remains %.
    currency_fields = {'ventas','costo_ventas','utilidad','compras','stock_valor','costo_unitario','precio_venta'}
    types={}
    for item in plan['columns']:
        alias=(item.get('alias') or (item['field'] if item['operation']=='none' else item['operation']+'_'+item['field'])).strip().lower()
        field=item['field']
        types[alias] = ('percent' if item['operation']=='weighted_margin' or field=='margen'
                         else 'currency' if field in currency_fields and item['operation']!='count'
                         else 'text' if COLUMNS[field][1]=='text' and item['operation'] not in ('count',)
                         else 'number')
    return {'tipo_resultado':'sql_semantico', 'dimension':'sku' if 'sku' in names else 'dinamico',
            'metrica': names[0], 'metricas':names, 'formatos_columnas':types,
            'etiquetas':{item['alias'].strip().lower() if item.get('alias') else
                         (item['field'] if item['operation']=='none' else item['operation']+'_'+item['field']):
                         LABELS.get(item['field'],item['field'].replace('_',' ').capitalize())
                         + (' · '+item['operation'] if item['operation'] in ('sum','avg','min','max','count') else '')
                         for item in plan['columns']},
            'totales':{}, 'filas':result, 'grupos_evaluados':len(result),
            'periodo':{'desde':default_start,'hasta':default_end},
            'filtros':scope_filters or {},'fuente':'odoo_sql',
            'sql_consulta':SOURCE+query,'sql_parametros':base+params,
            'plan_sql':query}
