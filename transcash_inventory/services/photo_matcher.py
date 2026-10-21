# -*- coding: utf-8 -*-
"""Conservative Odoo shop SKU/photo matching for a configurable HTTPS host."""
import ipaddress
import re
import unicodedata
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

DEFAULT_SITE_ROOT = 'https://www.transcash.ec'
# Retained for compatibility with older test scripts; runtime uses site_root arguments.
SITE_ROOT = DEFAULT_SITE_ROOT
PRODUCT_PATH = re.compile(r'^/shop/([a-zA-Z0-9][a-zA-Z0-9\-_]*)-(\d+)/?$')


def normalize_site_root(value):
    """Normalize the administrator-supplied storefront root; no arbitrary paths."""
    val = str(value or '').strip()
    p = urlparse(val)
    host = (p.hostname or '').lower()
    if (len(val) > 255 or p.scheme != 'https' or not host or
            p.username or p.password or p.port not in (None, 443) or
            p.query or p.fragment or p.path not in ('', '/', '/shop', '/shop/') or
            '.' not in host or not re.fullmatch(r'[a-z0-9.-]+', host) or
            host.endswith(('.local', '.internal', '.localhost', '.test')) or
            host.startswith('-') or '..' in host):
        raise ValueError('Ingrese un dominio HTTPS válido, por ejemplo https://www.transcash.ec')
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise ValueError('Utilice un dominio público, no una dirección IP')
    return 'https://' + host


def allowed_hosts(site_root):
    host = urlparse(normalize_site_root(site_root)).hostname
    # Odoo shops commonly redirect from www to apex and vice-versa.
    return {host, host[4:]} if host.startswith('www.') else {host, 'www.' + host}


def is_site_url(url, site_root, path_type=None):
    try:
        p = urlparse(str(url or ''))
        if (p.scheme != 'https' or p.hostname not in allowed_hosts(site_root) or
                p.username or p.password or p.port not in (None, 443)):
            return False
        if path_type == 'shop':
            return bool(PRODUCT_PATH.fullmatch(p.path))
        if path_type == 'image':
            return p.path.startswith(('/web/image/', '/web/content/'))
        return True
    except (TypeError, ValueError):
        return False


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


def extract_catalog_links(raw_html, site_root=DEFAULT_SITE_ROOT):
    parser = LinkParser()
    parser.feed(raw_html)
    results = []
    seen = set()
    for href in parser.hrefs:
        url = urljoin(normalize_site_root(site_root) + '/', href)
        p = urlparse(url)
        if not is_site_url(url, site_root, 'shop'):
            continue
        match = PRODUCT_PATH.match(p.path)
        clean_url = '%s://%s%s' % (p.scheme, p.netloc, p.path)
        if clean_url in seen:
            continue
        seen.add(clean_url)
        results.append({'url': clean_url,
                        'slug': match.group(1).lower(),
                        'template_id': int(match.group(2))})
    return results


def product_from_url(url, site_root=DEFAULT_SITE_ROOT):
    if not is_site_url(url, site_root, 'shop'):
        return None
    p = urlparse(str(url))
    match = PRODUCT_PATH.match(p.path)
    return {'url': '%s://%s%s' % (p.scheme, p.netloc, p.path),
            'slug': match.group(1).lower(), 'template_id': int(match.group(2))}


def index_by_sku(skus):
    return {slugify(sku): sku for sku in skus if slugify(sku)}


def match_slug_prefix(slug, sku_index):
    parts = slug.lower().split('-')
    for end in range(min(len(parts) - 1, 12), 0, -1):
        key = '-'.join(parts[:end])
        if key in sku_index:
            return sku_index[key]
    return None


def product_image_url(template_id, site_root=DEFAULT_SITE_ROOT):
    return '%s/web/image/product.template/%d/image_512' % (
        normalize_site_root(site_root), int(template_id))


def is_safe_photo_url(value, site_root=DEFAULT_SITE_ROOT):
    return is_site_url(value, site_root, 'image')


def is_safe_shop_url(value, site_root=DEFAULT_SITE_ROOT):
    return is_site_url(value, site_root, 'shop')


class ProductImageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta = []
        self.details = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag.lower() == 'meta' and (a.get('property') or a.get('name') or '').lower() in (
                'og:image', 'og:image:url', 'twitter:image'):
            if a.get('content'):
                self.meta.append(a['content'])
        elif tag.lower() == 'link' and 'image_src' in (a.get('rel') or '').lower():
            if a.get('href'):
                self.meta.append(a['href'])
        elif tag.lower() == 'img':
            for key in ('data-zoom-image', 'data-src', 'src'):
                if a.get(key):
                    self.details.append(a[key])


def extract_product_image_candidates(raw_html, shop_url, template_id,
                                     site_root=DEFAULT_SITE_ROOT):
    parser = ProductImageParser()
    parser.feed(raw_html)
    ordered = []
    for raw in parser.meta + parser.details:
        url = urljoin(shop_url, raw)
        if not is_safe_photo_url(url, site_root):
            continue
        parsed = urlparse(url)
        is_meta = raw in parser.meta
        is_template = '/product.template/%d/' % template_id in parsed.path
        if (is_meta or is_template) and url not in ordered:
            ordered.append(url)
    return ordered
