"""Normalización de RUC de transportistas ecuatorianos.
Nunca confundir la referencia ERP `proveedor` del producto con el transportista.
"""
import re

def normalize_transport_ruc(value):
    raw = re.sub(r'[^A-Z0-9]', '', str(value or '').strip().upper())
    if raw.startswith('EC') and raw[2:].isdigit():
        raw = raw[2:]
    return raw if raw.isdigit() and len(raw) in (10, 13) else ''
