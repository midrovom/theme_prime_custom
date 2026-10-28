# -*- coding: utf-8 -*-
"""Destino del ERP: un único código por compañía, con ciudad como nombre.

La clave usada en la PWA es transcash.guia.destino frente a
transcash.hoja.ruta.destino_id.codigo. No se compara por nombre de ciudad.
"""
import logging
import re
import unicodedata

from odoo import api, models, _
from odoo.exceptions import AccessError, ValidationError

_logger = logging.getLogger(__name__)


def erp_destination_key(value):
    """Equivalencia de formato: -NAJ, NAJ y ' N A J ' -> NAJ."""
    raw = unicodedata.normalize('NFKD', str(value or '').upper())
    return re.sub(r'[^A-Z0-9]', '', ''.join(
        ch for ch in raw if not unicodedata.combining(ch)))


def erp_destination_code(value):
    """Código legible de ERP, eliminando espacios y prefijos de formato."""
    raw = unicodedata.normalize('NFKD', str(value or '').upper().strip())
    raw = ''.join(ch for ch in raw if not unicodedata.combining(ch))
    raw = re.sub(r'\s+', '', raw)
    raw = re.sub(r'^[^A-Z0-9]+', '', raw)
    if not raw:
        return ''
    if len(raw) > 80 or not re.fullmatch(r'[A-Z0-9][A-Z0-9._-]*', raw):
        raise ValidationError(_('Código de destino ERP inválido: %s') % value)
    return raw


def _clean_city(value):
    return ' '.join(str(value or '').strip().split())[:255]


def upsert_erp_destination(env, company_id, code, city):
    """Crear/reutilizar transcash.destino sin duplicar por variantes del código.

    Mantiene códigos que ya están vinculados a rutas/tarifas. La ciudad sí se
    actualiza desde el ERP. No reactiva destinos archivados automáticamente.
    Debe ejecutarse dentro de una transacción Odoo (con savepoint por guía).
    """
    canonical = erp_destination_code(code)
    if not canonical:
        return False
    key = erp_destination_key(canonical)
    Destination = env['transcash.destino'].sudo().with_context(active_test=False)
    # Mismo candado utilizado por la importación: serializa creaciones por compañía.
    env.cr.execute('SELECT id FROM res_company WHERE id = %s FOR UPDATE', (company_id,))
    # También detecta registros históricos como NAJ / -NAJ sin crear otro.
    env.cr.execute('''
        SELECT id FROM transcash_destino
        WHERE company_id = %s
          AND regexp_replace(upper(coalesce(codigo, '')), '[^A-Z0-9]', '', 'g') = %s
        ORDER BY id
    ''', (company_id, key))
    ids = [row[0] for row in env.cr.fetchall()]
    if len(ids) > 1:
        raise ValidationError(_(
            'Hay varios destinos existentes para el código ERP %s (IDs %s). '
            'Revise el catálogo antes de volver a sincronizar.'
        ) % (canonical, ', '.join(map(str, ids))))
    city = _clean_city(city)
    if ids:
        rec = Destination.browse(ids[0])
        if not rec.active:
            # No reactivamos una ficha deshabilitada por un administrador.
            return rec
        vals = {}
        if city and rec.name != city:
            vals['name'] = city
        if city and rec.ciudad != city:
            vals['ciudad'] = city
        if vals:
            rec.write(vals)
        return rec
    return Destination.create({
        'company_id': company_id,
        'codigo': canonical,
        'name': city or canonical,
        'ciudad': city or False,
        'fuente': 'erp',
    })


