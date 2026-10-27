"""Identificación fiscal de terceros del ERP, sin crear duplicados.

El tipo de identificación de Ecuador puede estar aportado por l10n_latam_base.
La búsqueda por identidad no depende de que el documento sea fiscalmente válido.
"""
import re
import unicodedata

from odoo import _
from odoo.exceptions import UserError, ValidationError


def fiscal_key(value):
    """Normaliza documento, conservando ceros iniciales y letras extranjeras."""
    return re.sub(r'[^A-Z0-9]', '', str(value or '').strip().upper())


def fiscal_variants(value):
    """Claves equivalentes, incluyendo prefijo EC para cédula/RUC ecuatoriano."""
    key = fiscal_key(value)
    if not key:
        return set()
    options = {key}
    if key.startswith('EC') and key[2:].isdigit() and len(key[2:]) in (10, 13):
        options.add(key[2:])
    if key.isdigit() and len(key) in (10, 13):
        options.add('EC' + key)
    return options


def fiscal_document(value):
    key = fiscal_key(value)
    if key.startswith('EC') and key[2:].isdigit() and len(key[2:]) in (10, 13):
        return key[2:]
    return key


def first_kind(document, role):
    """13 dígitos: intentar RUC; chofer con 10: cédula; resto: extranjera."""
    if document.isdigit() and len(document) == 13:
        return 'ruc'
    if role == 'driver' and document.isdigit() and len(document) == 10:
        return 'cedula'
    return 'foreign'


def _fold(value):
    return ''.join(ch for ch in unicodedata.normalize('NFKD', str(value or '').lower())
                   if not unicodedata.combining(ch))


def _type_token(record):
    values = [record.name or '']
    for field in ('code', 'l10n_ec_type'):
        if field in record._fields:
            values.append(str(record[field] or ''))
    return ' '.join(_fold(v) for v in values)


def _fiscal_type(env, role):
    """Localiza tipos existentes, sin inventar XML IDs ni crear nuevos catálogos."""
    if 'l10n_latam_identification_type_id' not in env['res.partner']._fields:
        return False
    if 'l10n_latam.identification.type' not in env.registry.models:
        return False
    Type = env['l10n_latam.identification.type'].sudo()
    types = Type.search([])
    ec = env.ref('base.ec', raise_if_not_found=False)
    def score(r):
        t = _type_token(r)
        if role == 'ruc':
            valid = bool(re.search(r'\bruc\b', t))
        elif role == 'cedula':
            valid = ('cedula' in t or 'ciudadania' in t) and not ('extranj' in t or 'foreign' in t)
        else:
            valid = any(x in t for x in ('foreign', 'extranjer', 'exterior', 'id extranjero', 'identificacion extranjera'))
        if not valid:
            return -1
        country = (r.country_id if 'country_id' in r._fields else False)
        if country and ec and country.id != ec.id:
            return -1
        return 2 if country and ec and country.id == ec.id else 1
    ranked = sorted(((score(r), r) for r in types), key=lambda item: (-item[0], item[1].id))
    return ranked[0][1] if ranked and ranked[0][0] >= 0 else False


def _type_values(env, kind, require=False):
    """No clasificar como RUC un identificador extranjero por defecto."""
    Partner = env['res.partner']
    if 'l10n_latam_identification_type_id' not in Partner._fields:
        if require:
            raise ValidationError(_(
                'Falta el campo Tipo de identificación de LATAM en Contactos. '
                'Configure la localización antes de importar documentos extranjeros.'))
        return {}
    kind_record = _fiscal_type(env, kind)
    if not kind_record:
        if require:
            raise ValidationError(_(
                'No se encontró el tipo de identificación %s en la localización. '
                'Configure RUC, Cédula e Identificación extranjera en Odoo.') % kind)
        return {}
    return {'l10n_latam_identification_type_id': kind_record.id}


def create_fiscal_partner(env, values, identification, role):
    """Crear un único contacto. Ante rechazo fiscal, reintentar como extranjero.

    No se usan contextos que desactiven validación fiscal ni se altera el IVA/RUC.
    Ambos intentos comparten el mismo número normalizado, y el caller ya tiene
    bloqueada la identidad con pg_advisory_xact_lock.
    """
    Partner = env['res.partner'].sudo().with_context(active_test=False)
    number = fiscal_document(identification)
    if not number or len(number) < 5:
        raise ValidationError(_('Identificación de proveedor/chofer vacía o demasiado corta.'))
    preferred = first_kind(number, role)
    fiscal_values = dict(values, vat=number)
    # Si el tipo existe en la instalación debe utilizarse; si no, para RUC
    # intentamos la validación nativa, pero no fingimos una ID extranjera.
    try:
        fiscal_values.update(_type_values(
            env, preferred,
            require=(preferred == 'foreign' or
                     'l10n_latam_identification_type_id' in Partner._fields)))
        with env.cr.savepoint():
            created = Partner.create(fiscal_values)
        return created, preferred, ''
    except (ValidationError, UserError) as err:
        if preferred == 'foreign':
            raise
        foreign = _type_values(env, 'foreign', require=True)
        try:
            with env.cr.savepoint():
                created = Partner.create(dict(values, vat=number, **foreign))
        except (ValidationError, UserError):
            raise ValidationError(_(
                'La identificación %s no fue aceptada como RUC/Cédula ni como '
                'identificación extranjera. Revise la localización fiscal.') % number) from err
        return created, 'foreign', _(
            'Documento %s rechazado como %s; contacto creado con identificación extranjera. '
            'Revisar antes de emitir comprobantes.') % (number, preferred.upper())
