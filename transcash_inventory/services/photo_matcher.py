# -*- coding: utf-8 -*-
"""Parseo conservador de enlaces de producto públicos Transcash.

Nunca confunde un SKU por similitud de nombre. No intenta deducir el ID de Odoo
si no aparece en la URL pública original del producto.
"""
import re
import unicodedata
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

SITE_ROOT = 'https://www.transcash.ec'
ALLOWED_HOSTS = {'transcash.ec', 'www.transcash.ec'}
PRODUCT_PATH = re.compile(r'^/shop/([a-zA-Z0-9][a-zA-Z0-9\-_]*)-(\d+)/?$')


def slugify(value):
    value = unicodedata.normalize('NFKD', str(value or ''))
    value = ''.join(c for c in value if not unicodedata.combining(c)).lower()
    return re.sub(r'[^a-z0-9]+', '-', value).strip('-')


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hrefs = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == 'a':
            d = dict(attrs)
            if d.get('href'):
                self.hrefs.append(d['href'])


def extract_catalog_links(raw_html):
    parser = LinkParser()
    parser.feed(raw_html)
    results = []
    seen = set()
    for href in parser.hrefs:
        url = urljoin(SITE_ROOT, href)
        p = urlparse(url)
        if p.scheme != 'https' or p.hostname not in ALLOWED_HOSTS:
            continue
        match = PRODUCT_PATH.match(p.path)
        if not match or url in seen:
            continue
        seen.add(url)
        results.append({'url': url.split('?', 1)[0],
                        'slug': match.group(1).lower(),
                        'template_id': int(match.group(2))})
    return results


def product_from_url(url):
    p = urlparse(str(url or ""))
    if p.scheme != "https" or p.hostname not in ALLOWED_HOSTS:
        return None
    match = PRODUCT_PATH.match(p.path)
    if not match:
        return None
    return {"url": "%s://%s%s" % (p.scheme, p.netloc, p.path),
            "slug": match.group(1).lower(), "template_id": int(match.group(2))}


def index_by_sku(skus):
    """Prefijos Odoo que pueden contener el SKU antes del nombre del producto."""
    return {slugify(sku): sku for sku in skus if slugify(sku)}


def match_slug_prefix(slug, sku_index):
    """Match exacto del prefijo SKU, con separador; no por coincidencia parcial."""
    parts = slug.lower().split('-')
    # Se evita un barrido O(N_SKU) por página.
    for end in range(min(len(parts) - 1, 12), 0, -1):
        key = '-'.join(parts[:end])
        if key in sku_index:
            return sku_index[key]
    return None


def product_image_url(template_id):
    return '%s/web/image/product.template/%d/image_512' % (SITE_ROOT, int(template_id))


def is_safe_photo_url(value):
    try:
        p = urlparse(str(value or ''))
        return (p.scheme == 'https' and p.hostname in ALLOWED_HOSTS and
                (p.path.startswith('/web/image/') or p.path.startswith('/web/content/')))
    except (TypeError, ValueError):
        return False


def is_safe_shop_url(value):
    try:
        p = urlparse(str(value or ''))
        return p.scheme == 'https' and p.hostname in ALLOWED_HOSTS and p.path.startswith('/shop/')
    except (TypeError, ValueError):
        return False
