"""Validaciones estructurales de identificaciones ecuatorianas (no consulta al SRI)."""
import re


def valid_ecuador_cedula(value):
    value = value or ''
    if not re.fullmatch(r'[0-9]{10}', value):
        return False
    province = int(value[:2])
    if not (1 <= province <= 24 or province == 30):
        return False
    if int(value[2]) > 5:
        return False
    weights = (2, 1, 2, 1, 2, 1, 2, 1, 2)
    total = 0
    for digit, weight in zip(value[:9], weights):
        product = int(digit) * weight
        total += product - 9 if product > 9 else product
    return ((10 - total % 10) % 10) == int(value[9])


def valid_ecuador_cedula_or_ruc(value):
    value = value or ''
    if len(value) == 10:
        return valid_ecuador_cedula(value)
    if not re.fullmatch(r'[0-9]{13}', value):
        return False
    province = int(value[:2])
    if not (1 <= province <= 24 or province == 30):
        return False
    kind = int(value[2])
    if kind <= 5:
        # Para persona natural, los primeros 10 dígitos son una cédula.
        return valid_ecuador_cedula(value[:10]) and int(value[10:]) > 0
    if kind == 6:
        # El SRI no exige módulo 11 para los nuevos RUC de sociedades.
        return int(value[9:]) > 0
    if kind == 9:
        return int(value[10:]) > 0
    return False


def valid_ecuador_mobile(value):
    return bool(re.fullmatch(r'[0-9]{10}', value or ''))


def valid_foreign_document(value):
    return bool(re.fullmatch(r'[0-9]{10}', value or ''))


def valid_ecuador_or_foreign_document(value):
    """Primero comprobar cédula ecuatoriana; en caso contrario, documento extranjero.

    El documento extranjero se valida solo por formato: 10 dígitos numéricos.
    No hay verificación de existencia ni de nacionalidad por servicios externos.
    """
    if valid_ecuador_cedula(value):
        return True
    return valid_foreign_document(value)


def valid_ruc_length(value):
    """Regla solicitada: longitud/formato; no verifica estado en el SRI."""
    return bool(re.fullmatch(r'[0-9]{13}', value or ''))


def valid_credit_identity(value, document_type):
    return ((document_type == 'cedula' and valid_ecuador_cedula(value)) or
            (document_type == 'ruc' and valid_ruc_length(value)) or
            (document_type == 'foreign' and valid_foreign_document(value)))
