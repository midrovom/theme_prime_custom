# -*- coding: utf-8 -*-
"""Resolver literal catalog filters before compiling the trusted SQL statement.

The LLM cannot silently substitute CERAMICA when a user asks for PORCELANATO.
Explicit UI filters have the highest priority; recognizable catalog names mentioned
in the question take precedence over AI guesses. All names are resolved to actual
values present in the active company's snapshot.
"""
import re
import unicodedata

FIELDS = {
    'categoria': 'categoria', 'marca': 'marca', 'formato': 'formato',
    'proveedor': 'proveedor_ficha',
}


def _norm(value):
    normalized = unicodedata.normalize('NFKD', str(value or ''))
    normalized = ''.join(c for c in normalized if not unicodedata.combining(c)).casefold()
    normalized = normalized.replace('×', 'x').replace('*', 'x')
    return ' '.join(normalized.split())


def catalog_values(env, snapshot, field, real_supplier=False):
    if field not in FIELDS:
        raise ValueError('Filtro no permitido.')
    if field == 'proveedor' and real_supplier:
        table, col = 'transcash_inventory_fact_supplier_purchase', 'proveedor_compra'
    else:
        table, col = 'transcash_inventory_fact_product', FIELDS[field]
    # table/column are only drawn from whitelisted literals above.
    env.cr.execute('SELECT DISTINCT "' + col + '" FROM ' + table +
                   ' WHERE snapshot_id=%s AND company_id=%s AND "' + col + '" IS NOT NULL',
                   (snapshot.id, snapshot.company_id.id))
    return sorted({v.strip() for (v,) in env.cr.fetchall() if isinstance(v, str) and v.strip()})


def _canonical(value, choices, field):
    value = _norm(value)
    if not value:
        return ''
    matched = [name for name in choices if _norm(name) == value]
    if len(matched) == 1:
        return matched[0]
    if len(matched) > 1:
        return sorted(matched)[0]
    partial = [name for name in choices if _norm(name).startswith(value)]
    if len(partial) == 1 and len(value) >= 3:
        return partial[0]
    if len(partial) > 1:
        raise ValueError('El filtro de %s coincide con varios valores del catálogo; seleccione uno exacto.' % field)
    raise ValueError('El filtro de %s no existe en el catálogo: %s.' % (field, value[:70]))


def _mentioned(question, choices, field):
    phrase = _norm(question)
    # Only whole catalogue phrases; avoid finding short model names embedded in other words.
    matches = []
    for name in choices:
        needle = _norm(name)
        if len(needle) < 4 or needle.startswith('sin '):
            continue
        suffix = r'(?:s|es)?' if field == 'categoria' else ''
        if re.search(r'(?<![\w])' + re.escape(needle) + suffix + r'(?![\w])', phrase):
            matches.append(name)
    if not matches:
        return ''
    matches.sort(key=lambda x: len(_norm(x)), reverse=True)
    # If the question has 2 separate values for the same dimension, require
    # the user to select one in the UI rather than pick a random value.
    best = matches[0]
    if any((_norm(other) not in _norm(best) and _norm(best) not in _norm(other))
           for other in matches[1:]):
        raise ValueError('La consulta menciona varios valores de %s. Seleccione uno exacto en el filtro.' % field)
    return best


def resolve_catalog_filters(env, snapshot, plan, question, ui_filters):
    """Mutates validated plan. Resolve all explicit filters to actual values.

    UI exact > name literally mentioned in question > model proposal.
    If the plan is inconsistent with explicit question text, question wins.
    A bad AI guess is rejected rather than returning unrelated products.
    """
    plan = dict(plan)
    if (ui_filters or {}).get('proveedor') and plan.get('group_by') == 'proveedor_compra':
        raise ValueError('El filtro Proveedor del catálogo no se puede combinar con un ranking por proveedor real de compra. Retire el filtro o agrupe por proveedor de catálogo.')
    # Provider/brand names may literally include a category (e.g., supplier
    # 'CERAMICA CARMELO FIOR LTDA'). Exclude those full names from the text
    # before detecting an explicitly requested category.
    category_question = _norm(question)
    for other_field in ('proveedor', 'marca'):
        for label in catalog_values(env, snapshot, other_field):
            normalized_label = _norm(label)
            if len(normalized_label) >= 8 and ' ' in normalized_label:
                category_question = re.sub(r'(?<![\w])' + re.escape(normalized_label) +
                                           r'(?![\w])', ' ', category_question)
    for field in FIELDS:
        real_supplier = field == 'proveedor' and plan.get('group_by') == 'proveedor_compra'
        values = catalog_values(env, snapshot, field, real_supplier=real_supplier)
        ui = str((ui_filters or {}).get(field) or '').strip()
        explicit = _mentioned(category_question if field == 'categoria' else question,
                              values, field) if not ui else ''
        proposal = str(plan.get(field) or '').strip()
        if ui:
            plan[field] = _canonical(ui, values, field)
        elif explicit:
            plan[field] = _canonical(explicit, values, field)
        elif proposal:
            plan[field] = _canonical(proposal, values, field)
        else:
            plan[field] = ''
    return plan
