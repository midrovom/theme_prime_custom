# -*- coding: utf-8 -*-
"""Read-only SQL-like semantic query engine.

The model writes a SELECT against one *virtual* relation ``inventario``.
We parse a deliberately small SQL grammar, then construct NEW SQL using only
server-side column expressions and parameters. Model SQL is NEVER executed.
Company/snapshot scope is injected by Odoo in every source CTE.
"""
import json
import re
from decimal import Decimal

from ..vendor_lark import Lark, Tree, Token

from .ai_analytics import METRICS

GRAMMAR = r'''
start: "SELECT"i selections "FROM"i "inventario"i where? group? order? limit?
selections: selection ("," selection)*
?selection: name alias?                             -> direct
          | "SUM"i "(" name ")" alias?          -> summation
          | "COUNT"i "(" "*" ")" alias?       -> counting
          | "AVG"i "(" name ")" alias?         -> average
          | "MIN"i "(" name ")" alias?         -> minimum
          | "MAX"i "(" name ")" alias?         -> maximum
          | "MARGEN"i "(" ")" alias?         -> margin
alias: "AS"i name
name: NAME
where: "WHERE"i expr
?expr: expr "OR"i term   -> or_expr
     | term
?term: term "AND"i atom -> and_expr
     | atom
?atom: "(" expr ")" -> wrapped
     | name COMP scalar -> comparison
     | name "ILIKE"i scalar -> contains
     | name "LIKE"i scalar -> contains
     | name "BETWEEN"i scalar "AND"i scalar -> between
     | name "IN"i "(" scalar ("," scalar)* ")" -> in_list
?scalar: STRING -> textval
       | SIGNED_NUMBER -> number
       | "NULL"i -> nullval
group: "GROUP"i "BY"i name ("," name)*
order: "ORDER"i "BY"i name DIRECTION?
DIRECTION: "ASC"i | "DESC"i
limit: "LIMIT"i INT
COMP: "<=" | ">=" | "<>" | "!=" | "=" | "<" | ">"
NAME: /[A-Za-z_][A-Za-z_0-9]*/
STRING: /'(?:''|[^'])*'/
// Terminales definidos localmente para no depender de gramáticas externas
// de la librería Lark incorporada en este módulo.
SIGNED_NUMBER: /[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?/
INT: /[0-9]+/
WS: /[ \t\f\r\n]+/
%ignore WS
'''
PARSER = Lark(GRAMMAR, parser='lalr', maybe_placeholders=False)

# A virtual per-SKU view. Never expose arbitrary PostgreSQL identifiers.
COLUMNS = {
    'sku': ('inv.sku', 'text'), 'descripcion': ('inv.descripcion', 'text'),
    'categoria': ('inv.categoria', 'text'), 'marca': ('inv.marca', 'text'),
    'formato': ('inv.formato', 'text'), 'proveedor': ('inv.proveedor', 'text'),
    'proveedor_ficha': ('inv.proveedor', 'text'),
    'stock_unidades': ('inv.stock_unidades', 'num'), 'stock_valor': ('inv.stock_valor', 'num'),
    'cantidad_vendida': ('inv.cantidad_vendida', 'num'),
    'cantidad_comprada': ('inv.cantidad_comprada', 'num'),
    'ventas': ('inv.ventas', 'num'), 'costo_ventas': ('inv.costo_ventas', 'num'),
    'utilidad': ('inv.utilidad', 'num'), 'margen': ('inv.margen', 'num'),
    'compras': ('inv.compras', 'num'), 'costo_unitario': ('inv.costo_unitario', 'num'),
    'precio_venta': ('inv.precio_venta', 'num'),
    'ultima_venta': ('inv.ultima_venta', 'text'), 'ultima_compra': ('inv.ultima_compra', 'text'),
}
LABELS = dict(METRICS, sku='SKU', descripcion='Descripción', proveedor='Proveedor del catálogo',
              stock_unidades='Stock físico (cantidad)', formato='Formato', cantidad_comprada='Cantidad comprada',
              cantidad_vendida='Cantidad vendida', ultima_compra='Última compra (mes)', ultima_venta='Última venta (mes)')

# Constructed only from verified Odoo-table constants. Aggregate sales and
# purchases individually BEFORE joining, avoiding multiplying transactions.
SOURCE = '''WITH sold AS (
 SELECT product_id, SUM(ventas) AS ventas, SUM(costo_ventas) AS costo_ventas,
 SUM(cantidad_vendida) AS cantidad_vendida FROM transcash_inventory_fact_sale
 WHERE snapshot_id=%s AND company_id=%s AND mes BETWEEN %s AND %s GROUP BY product_id),
bought AS (
 SELECT product_id, SUM(compras) AS compras, SUM(cantidad_comprada) AS cantidad_comprada
 FROM transcash_inventory_fact_purchase
 WHERE snapshot_id=%s AND company_id=%s AND mes BETWEEN %s AND %s GROUP BY product_id),
last_s AS (
 SELECT product_id, MAX(mes) AS ultima_venta FROM transcash_inventory_fact_sale
 WHERE snapshot_id=%s AND company_id=%s AND cantidad_vendida > 0 GROUP BY product_id),
last_b AS (
 SELECT product_id, MAX(mes) AS ultima_compra FROM transcash_inventory_fact_purchase
 WHERE snapshot_id=%s AND company_id=%s AND cantidad_comprada > 0 GROUP BY product_id),
inventario AS (
 SELECT p.sku, p.name AS descripcion, p.categoria, p.marca, p.formato,
 p.proveedor_ficha AS proveedor, p.stock_unidades, p.stock_valor,
 p.costo_unitario, p.precio_venta,
 COALESCE(s.ventas,0) AS ventas, COALESCE(s.costo_ventas,0) AS costo_ventas,
 COALESCE(s.cantidad_vendida,0) AS cantidad_vendida,
 COALESCE(b.compras,0) AS compras, COALESCE(b.cantidad_comprada,0) AS cantidad_comprada,
 (COALESCE(s.ventas,0)-COALESCE(s.costo_ventas,0)) AS utilidad,
 CASE WHEN COALESCE(s.ventas,0)<>0 THEN
 100.0*(COALESCE(s.ventas,0)-COALESCE(s.costo_ventas,0))/s.ventas
 ELSE NULL END AS margen,
 ls.ultima_venta, lb.ultima_compra
 FROM transcash_inventory_fact_product p
 LEFT JOIN sold s ON s.product_id=p.id
 LEFT JOIN bought b ON b.product_id=p.id
 LEFT JOIN last_s ls ON ls.product_id=p.id
 LEFT JOIN last_b lb ON lb.product_id=p.id
 WHERE p.snapshot_id=%s AND p.company_id=%s
)
'''

class InvalidSemanticSQL(ValueError):
    pass


def ident(node):
    if isinstance(node, Tree) and node.data == 'name':
        return str(node.children[0]).lower()
    raise InvalidSemanticSQL('Campo no reconocido en la consulta.')


def scalar(node):
    if node.data == 'textval':
        return str(node.children[0])[1:-1].replace("''", "'")
    if node.data == 'number':
        return float(str(node.children[0]))
    raise InvalidSemanticSQL('No se admite ese valor de filtro.')


def _col(node, expected=None):
    col = ident(node)
    if col not in COLUMNS:
        raise InvalidSemanticSQL('La consulta utiliza un campo no disponible: %s.' % col[:60])
    if expected and COLUMNS[col][1] != expected:
        raise InvalidSemanticSQL('El campo %s no admite esa operación.' % col)
    return col, COLUMNS[col][0]


def _filter(node, params):
    typ = node.data
    if typ in ('and_expr', 'or_expr'):
        left = _filter(node.children[0], params)
        right = _filter(node.children[1], params)
        return '(' + left + (' AND ' if typ == 'and_expr' else ' OR ') + right + ')'
    if typ == 'wrapped':
        return '(' + _filter(node.children[0], params) + ')'
    if typ == 'between':
        _, expr = _col(node.children[0]); low = scalar(node.children[1]); high = scalar(node.children[2])
        params.extend([low,high]); return '(' + expr + ' BETWEEN %s AND %s)'
    if typ == 'in_list':
        _, expr = _col(node.children[0]); values = [scalar(x) for x in node.children[1:]]
        if len(values)>50:raise InvalidSemanticSQL('El filtro tiene demasiados valores.')
        params.extend(values)
        return '(' + expr + ' IN (' + ','.join(['%s']*len(values)) + '))'
    if typ in ('contains', 'comparison'):
        column, expr = _col(node.children[0]); val = scalar(node.children[-1])
        if isinstance(val,float) and COLUMNS[column][1]=='text':
            raise InvalidSemanticSQL('Una columna de texto requiere un valor de texto.')
        if isinstance(val,str) and COLUMNS[column][1]=='num':
            raise InvalidSemanticSQL('Una condición numérica requiere un número.')
        if typ == 'contains':
            if COLUMNS[column][1] != 'text':
                raise InvalidSemanticSQL('LIKE solo admite atributos de texto.')
            params.append(str(val).replace('%','\\%').replace('_','\\_').strip('%'))
            return 'LOWER(COALESCE(' + expr + ",'')) LIKE '%%' || LOWER(%s) || '%%' ESCAPE '\\'"
        op = str(node.children[1])
        params.append(val)
        return '(' + expr + ' ' + ('<>' if op=='!=' else op) + ' %s)'
    raise InvalidSemanticSQL('Condición SQL no autorizada.')


def parse_compile(proposed_sql, scope_filters=None):
    """Return a newly compiled SELECT clause, bounded value params and column names."""
    if not isinstance(proposed_sql, str) or not 10 < len(proposed_sql) < 4000:
        raise InvalidSemanticSQL('El SQL no tiene un formato válido.')
    try:
        tree = PARSER.parse(proposed_sql.strip())
    except Exception:
        raise InvalidSemanticSQL('La consulta propuesta no respeta el formato SELECT autorizado.') from None
    select_exprs=[]; names=[]; aliases={}; aggregated=False; direct_fields=[]
    where_part=''; where_params=[]; groups=[]; order=None; limit=1000
    for section in tree.children:
        if section.data == 'selections':
            if not 1 <= len(section.children) <= 20:raise InvalidSemanticSQL('Máximo 20 columnas por consulta.')
            for i, node in enumerate(section.children):
                typ=node.data
                alias=ident(node.children[-1].children[0]) if node.children and isinstance(node.children[-1],Tree) and node.children[-1].data=='alias' else None
                if typ=='direct':
                    field,expression=_col(node.children[0]); direct_fields.append(field)
                    name=alias or field
                elif typ in ('summation','average','minimum','maximum'):
                    field,expression=_col(node.children[0]); aggregated=True
                    if typ in ('summation','average') and COLUMNS[field][1]!='num':
                        raise InvalidSemanticSQL('Solo se pueden sumar o promediar cantidades.')
                    if typ in ('summation','average') and field=='margen':
                        raise InvalidSemanticSQL('No sume ni promedie porcentajes; use MARGEN().')
                    fun={'summation':'SUM','average':'AVG','minimum':'MIN','maximum':'MAX'}[typ]
                    expression=fun+'('+expression+')'
                    name=alias or (fun.lower()+'_'+field)
                elif typ=='counting':
                    expression='COUNT(*)'; name=alias or 'total_productos'; aggregated=True
                elif typ=='margin':
                    expression='ROUND((100.0*SUM(inv.utilidad)/NULLIF(SUM(inv.ventas),0))::numeric,2)'
                    name=alias or 'margen'; aggregated=True
                else:raise InvalidSemanticSQL('Expresión de columna no permitida.')
                if not re.fullmatch(r'[a-z][a-z0-9_]{0,45}',name) or name in names:
                    raise InvalidSemanticSQL('Nombre de columna duplicado o inválido.')
                names.append(name); aliases[name]=(expression,typ); select_exprs.append(expression+' AS "'+name+'"')
        elif section.data=='where':
            where_part=_filter(section.children[0],where_params)
        elif section.data=='group':
            groups=[_col(x)[0] for x in section.children]
            if len(groups)!=len(set(groups)):raise InvalidSemanticSQL('Agrupación repetida.')
        elif section.data=='order':
            name=ident(section.children[0]); direction=str(section.children[1]).upper() if len(section.children)>1 else 'DESC'
            if direction not in ('ASC','DESC'):raise InvalidSemanticSQL('Orden no permitido.')
            if name not in aliases and name not in COLUMNS:
                raise InvalidSemanticSQL('No se puede ordenar por esa columna.')
            if aggregated and name not in aliases and name not in groups:
                raise InvalidSemanticSQL('El ordenamiento debe usar un campo agrupado o calculado.')
            expr='"'+name+'"' if name in aliases else COLUMNS[name][0]
            order=expr+' '+direction
        elif section.data=='limit':
            limit=int(str(section.children[0]))
            if limit<1:raise InvalidSemanticSQL('LIMIT debe ser positivo.')
    if aggregated:
        if any(f not in groups for f in direct_fields):
            raise InvalidSemanticSQL('Los campos no agregados deben aparecer en GROUP BY.')
    elif groups:
        raise InvalidSemanticSQL('GROUP BY requiere una suma, conteo u otra agregación.')
    sql='SELECT '+', '.join(select_exprs)+' FROM inventario inv'
    all_conditions=[]
    if where_part:all_conditions.append(where_part)
    params=list(where_params)
    for key,value in (scope_filters or {}).items():
        if key not in ('categoria','marca','formato','proveedor'):continue
        if value:
            params.append(str(value))
            all_conditions.append('LOWER(TRIM(COALESCE('+COLUMNS[key][0]+",''))) = LOWER(TRIM(%s))")
    if all_conditions:sql+=' WHERE '+' AND '.join('('+condition+')' for condition in all_conditions)
    if groups:sql+=' GROUP BY '+', '.join(COLUMNS[f][0] for f in groups)
    if order:sql+=' ORDER BY '+order
    sql+=' LIMIT %s';params.append(min(limit, 3000))
    return sql,params,names, {'group':groups,'aggregated':aggregated,'limit':min(limit,3000)}


def execute_semantic_sql(env, snapshot, sql_text, default_start, default_end, scope_filters=None):
    months=json.loads(snapshot.relational_months or '[]')
    if not months or default_start not in months or default_end not in months or default_start>default_end:
        raise InvalidSemanticSQL('No hay un período válido para la consulta.')
    query,params,names,meta=parse_compile(sql_text,scope_filters)
    # Exact company and snapshot applied in EACH independent data source.
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
    return {'tipo_resultado':'sql_semantico',
            'dimension':'sku' if 'sku' in names else 'dinamico',
            'metrica': names[0], 'metricas':names,
            'etiquetas':{name:LABELS.get(name,name.replace('_',' ').capitalize()) for name in names},
            'totales':{},'filas':result,'grupos_evaluados':len(result),
            'periodo':{'desde':default_start,'hasta':default_end},
            'filtros':scope_filters or {},'fuente':'odoo_sql',
            'sql_consulta':SOURCE+query,'sql_parametros':base+params,
            'plan_sql':sql_text}
