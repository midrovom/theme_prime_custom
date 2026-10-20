# -*- coding: utf-8 -*-
"""Verified public product photography, separated from inventory snapshots.

A product's shop id is NOT assumed to be its product.product id. The image
link is read from its public HTML and validated as a real image response.
"""
import json
import logging
import base64
from io import BytesIO
from PIL import Image, UnidentifiedImageError
from datetime import timedelta
from urllib.parse import urlencode, urlparse, quote
from urllib.request import Request, urlopen, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError, URLError

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError

from ..services.photo_matcher import (
    SITE_ROOT, ALLOWED_HOSTS, extract_catalog_links, extract_product_image_candidates,
    index_by_sku, match_slug_prefix, product_from_url, product_image_url,
    is_safe_photo_url, is_safe_shop_url,
)

_logger = logging.getLogger(__name__)
MAX_HTML = 3 * 1024 * 1024
AGENT = 'TranscashInventoryPhoto/1.5 (+catalog-image-validation)'


def _safe_remote(url):
    try:
        p = urlparse(url)
        return (len(url) <= 2048 and p.scheme == 'https' and p.hostname in ALLOWED_HOSTS
                and (p.port in (None, 443)) and not p.username and not p.password)
    except (ValueError, TypeError):
        return False


class _RestrictedRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not _safe_remote(newurl):
            raise ValueError('Redirección a un dominio o puerto no permitido')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_HTTP = build_opener(_RestrictedRedirect())


def _http_get(url, accept='text/html', max_bytes=MAX_HTML):
    if not _safe_remote(url):
        raise ValueError('Dominio o esquema remoto no permitido')
    headers = {'User-Agent': AGENT, 'Accept': accept, 'Accept-Language': 'es-EC,es;q=0.9'}
    with _HTTP.open(Request(url, headers=headers), timeout=10) as response:
        if not _safe_remote(response.geturl()):
            raise ValueError('Redirección a otro dominio no permitida')
        content_type = (response.headers.get('Content-Type') or '').lower()
        content = response.read(max_bytes + 1)
        if len(content) > max_bytes:
            raise ValueError('Respuesta remota demasiado grande')
        return content_type, content


def _shop_html(url):
    typ, data = _http_get(url, max_bytes=MAX_HTML)
    if 'text/html' not in typ and 'application/xhtml+xml' not in typ:
        raise ValueError('La tienda no devolvió HTML')
    return data.decode('utf-8', errors='replace')


def _valid_image_signature(buf):
    return (buf.startswith(b'\xff\xd8\xff') or
            buf.startswith(b'\x89PNG\r\n\x1a\n') or
            buf.startswith((b'GIF87a', b'GIF89a')) or
            (len(buf) >= 12 and buf[:4] == b'RIFF' and buf[8:12] == b'WEBP'))


def _verified_photo_with_thumbnail(url):
    """Check image bytes and store a bounded 240px JPEG for same-origin display."""
    if not is_safe_photo_url(url) or not _safe_remote(url):
        return None
    headers = {'User-Agent': AGENT, 'Accept': 'image/webp,image/png,image/jpeg,image/gif,image/*'}
    try:
        with _HTTP.open(Request(url, headers=headers), timeout=10) as response:
            if not _safe_remote(response.geturl()):
                raise ValueError('Redirección de foto no permitida')
            typ = (response.headers.get('Content-Type') or '').split(';')[0].strip().lower()
            if typ not in ('image/jpeg', 'image/png', 'image/gif', 'image/webp'):
                return None
            raw = response.read(6 * 1024 * 1024 + 1)
            if len(raw) > 6 * 1024 * 1024 or not _valid_image_signature(raw):
                return None
        with Image.open(BytesIO(raw)) as pic:
            if pic.width < 20 or pic.height < 20 or pic.width * pic.height > 28_000_000:
                return None
            pic.thumbnail((240, 240))
            if pic.mode != 'RGB':
                pic = pic.convert('RGB')
            thumbnail = BytesIO()
            pic.save(thumbnail, format='JPEG', quality=79, optimize=True)
            return base64.b64encode(thumbnail.getvalue()).decode('ascii')
    except (UnidentifiedImageError, Image.DecompressionBombError, Image.DecompressionBombWarning, OSError, ValueError):
        return None
    except HTTPError as exc:
        if exc.code in (403, 429, 500, 502, 503, 504):
            raise
        return None
    except (URLError, TimeoutError):
        raise



class TranscashInventoryPhoto(models.Model):
    _name = 'transcash.inventory.photo'
    _description = 'Fotografía comercial SKU Transcash'
    _rec_name = 'sku'
    _order = 'sku'

    company_id = fields.Many2one('res.company', required=True, index=True,
                                 default=lambda self: self.env.company)
    sku = fields.Char('SKU', required=True, index=True)
    description = fields.Char('Descripción inventario', readonly=True)
    website_url = fields.Char('Ficha Transcash')
    image_url = fields.Char('Imagen principal verificada')
    image_thumbnail = fields.Binary('Miniatura almacenada', attachment=True, readonly=True)
    template_id_remote = fields.Integer('ID ficha web', readonly=True)
    match_type = fields.Selection([
        ('sku', 'SKU exacto en URL'), ('manual', 'Validado manualmente'),
    ], default='sku', required=True)
    enabled = fields.Boolean('Mostrar imagen', default=True)
    checked_on = fields.Datetime('Última comprobación', readonly=True)
    status = fields.Selection([
        ('unchecked', 'Sin verificar'), ('queued', 'Pendiente de búsqueda'),
        ('verified', 'Imagen verificada'), ('not_found', 'SKU no encontrado en tienda'),
        ('broken', 'Imagen o ficha incorrecta'), ('error', 'Error de conexión'),
    ], string='Estado fotografía', default='unchecked', required=True, index=True)
    attempt_count = fields.Integer('Intentos', default=0, readonly=True)
    last_error = fields.Char('Último error', readonly=True)
    next_retry = fields.Datetime('Próximo reintento', readonly=True, index=True)
    note = fields.Text('Observaciones')

    _sql_constraints = [
        ('sku_company_unique', 'unique(company_id,sku)',
         'Ya existe una imagen asociada a este SKU en esta empresa.'),
    ]

    @api.constrains('image_url', 'website_url')
    def _check_public_urls(self):
        for rec in self:
            if rec.image_url and not is_safe_photo_url(rec.image_url):
                raise ValidationError(_('La imagen debe ser HTTPS de transcash.ec/web/image o web/content.'))
            if rec.website_url and not is_safe_shop_url(rec.website_url):
                raise ValidationError(_('La ficha debe pertenecer a https://transcash.ec/shop/...'))

    def write(self, vals):
        # If a URL is modified by hand in Odoo's list/form, its old cached
        # photograph is no longer reliable until verified again.
        if ('image_url' in vals or 'website_url' in vals) and 'status' not in vals:
            vals = dict(vals, status='unchecked', image_thumbnail=False,
                        next_retry=False, last_error=False)
        return super().write(vals)

    @api.model
    def images_for_skus(self, skus):
        codes = list(dict.fromkeys([str(s).strip()[:120] for s in skus if str(s).strip()]))[:80]
        if not codes:
            return {}
        rows = self.search([('company_id', '=', self.env.company.id),
                            ('sku', 'in', codes), ('enabled', '=', True)])
        return {rec.sku: {'image_url': ('/transcash_inventory/photos/thumb?sku=' + quote(rec.sku, safe=''))
                                       if rec.status == 'verified' and rec.image_thumbnail else
                                       (rec.image_url if rec.status == 'unchecked' else ''),
                          'source_url': rec.image_url or '',
                          'website_url': rec.website_url or '',
                          'match_type': rec.match_type,
                          'status': rec.status,
                          'error': rec.last_error or ''}
                for rec in rows}


class TranscashInventoryPhotoSync(models.Model):
    _name = 'transcash.inventory.photo.sync'
    _description = 'Sincronización de fotos públicas Transcash'
    _rec_name = 'company_id'

    company_id = fields.Many2one('res.company', required=True, index=True,
                                 default=lambda self: self.env.company)
    next_page = fields.Integer(default=1, required=True)
    examined = fields.Integer(default=0)
    matched = fields.Integer(default=0)
    finished = fields.Boolean(default=False)
    last_error = fields.Text()
    last_run = fields.Datetime()
    empty_pages = fields.Integer(default=0)
    last_page_fingerprint = fields.Char()
    _sql_constraints = [('company_photo_sync_unique', 'unique(company_id)',
                         'Ya existe sincronización para esta empresa.')]

    @api.model
    def get_current(self):
        rec = self.search([('company_id', '=', self.env.company.id)], limit=1)
        if not rec:
            rec = self.create({'company_id': self.env.company.id})
        return rec

    @api.model
    def _get_latest_sku_map(self):
        snapshot = self.env['transcash.inventory.snapshot'].search([
            ('company_id', '=', self.env.company.id)], limit=1,
            order='create_date desc, id desc')
        if not snapshot:
            raise UserError(_('Primero importe el Excel desde Cargar archivos.'))
        dataset = json.loads(snapshot.get_dashboard_json())
        items = [(str(p[0]).strip(), str(p[1])) for p in dataset.get('products', []) if len(p) > 1]
        return index_by_sku([sku for sku, _ in items]), dict(items)

    def _photo_record(self, sku, description):
        Photo = self.env['transcash.inventory.photo']
        rec = Photo.search([('company_id', '=', self.env.company.id), ('sku', '=', sku)], limit=1)
        if not rec:
            rec = Photo.create({'company_id': self.env.company.id, 'sku': sku,
                                'description': description, 'status': 'queued'})
        return rec

    def enqueue_skus(self, skus, force=False):
        """Queue only known, exact snapshot SKUs; no blocking network call."""
        self.ensure_one()
        _, names = self._get_latest_sku_map()
        lookup = {s.casefold(): s for s in names}
        now = fields.Datetime.now()
        found = 0
        codes = list(dict.fromkeys(str(x).strip()[:120] for x in skus if str(x).strip()))[:80]
        for code in codes:
            canonical = lookup.get(code.casefold())
            if not canonical:
                continue
            rec = self._photo_record(canonical, names[canonical])
            if rec.status == 'verified' and not force:
                continue
            if not force and rec.next_retry and rec.next_retry > now:
                continue
            if force or rec.status not in ('queued', 'verified'):
                rec.write({'status': 'queued', 'next_retry': False, 'last_error': False})
                found += 1
        return found

    def _search_public_product(self, sku, description, sku_index):
        # Odoo shop search is public, but its search behaviour may depend on the
        # site's configuration. Always confirm exact SKU prefix in returned URLs.
        terms = [sku]
        if description:
            terms.append(description[:80])
        for term in terms:
            html = _shop_html(SITE_ROOT + '/shop?' + urlencode({'search': term}))
            for link in extract_catalog_links(html):
                if match_slug_prefix(link['slug'], sku_index) == sku:
                    return link
        return None

    def _verify_shop_photo(self, shop_link):
        """Check shop SKU & image response; never assume template and variant IDs match."""
        html = _shop_html(shop_link['url'])
        candidates = extract_product_image_candidates(html, shop_link['url'], shop_link['template_id'])
        # Some older templates omit OpenGraph; these URLs are fallbacks only
        # and *must* pass actual image-response validation before being saved.
        candidates.extend([
            '%s/web/image/product.template/%d/image_1920' % (SITE_ROOT, shop_link['template_id']),
            product_image_url(shop_link['template_id']),
        ])
        tested = set()
        for url in candidates[:12]:
            if url in tested:
                continue
            tested.add(url)
            thumbnail = _verified_photo_with_thumbnail(url)
            if thumbnail:
                return url, thumbnail
        raise ValueError('La ficha existe, pero ninguna URL devuelve una imagen JPEG, PNG, GIF o WebP válida')

    def resolve_single_sku(self, sku, supplied_url=None, manual=False, force=True):
        self.ensure_one()
        sku_index, names = self._get_latest_sku_map()
        canonical = next((s for s in names if s.casefold() == str(sku).strip().casefold()), None)
        if not canonical:
            raise UserError(_('El SKU no existe en el último inventario importado.'))
        # Reject mismatched manual links without mutating any existing photo.
        if supplied_url:
            supplied_link = product_from_url(supplied_url)
            if not supplied_link or match_slug_prefix(supplied_link['slug'], sku_index) != canonical:
                raise UserError(_('La dirección web no corresponde al SKU indicado.'))
        rec = self._photo_record(canonical, names[canonical])
        now = fields.Datetime.now()
        if not force and rec.next_retry and rec.next_retry > now:
            return rec
        if rec.status == 'verified' and not force:
            return rec
        vals = {'checked_on': now, 'attempt_count': rec.attempt_count + 1,
                'last_error': False, 'next_retry': False}
        try:
            shop_link = product_from_url(supplied_url or rec.website_url)
            if shop_link and match_slug_prefix(shop_link['slug'], sku_index) != canonical:
                shop_link = None
            if not shop_link:
                shop_link = self._search_public_product(canonical, names[canonical], sku_index)
            if not shop_link:
                vals.update({'status': 'not_found', 'image_url': False, 'image_thumbnail': False,
                             'last_error': 'No aparece una ficha con este SKU exacto en la búsqueda pública',
                             'next_retry': now + timedelta(days=7)})
            else:
                url, thumbnail = self._verify_shop_photo(shop_link)
                vals.update({'website_url': shop_link['url'], 'image_url': url,
                             'image_thumbnail': thumbnail,
                             'template_id_remote': shop_link['template_id'],
                             'match_type': 'manual' if manual else rec.match_type if rec.match_type == 'manual' else 'sku',
                             'status': 'verified', 'last_error': False,
                             'next_retry': now + timedelta(days=30)})
        except ValueError as exc:
            vals.update({'status': 'broken', 'image_url': False, 'image_thumbnail': False,
                         'last_error': str(exc)[:250], 'next_retry': now + timedelta(days=2)})
            if supplied_url and product_from_url(supplied_url):
                vals['website_url'] = product_from_url(supplied_url)['url']
        except (HTTPError, URLError, OSError, TimeoutError) as exc:
            # A blocked/outage site is not proof the product has no photo.
            vals.update({'status': 'error', 'image_url': False, 'image_thumbnail': False,
                         'last_error': ('Error consultando tienda: %s' % str(exc))[:250],
                         'next_retry': now + timedelta(hours=12)})
            if supplied_url and product_from_url(supplied_url):
                vals['website_url'] = product_from_url(supplied_url)['url']
        rec.write(vals)
        return rec

    @api.model
    def cron_index_public_catalog(self):
        """Prioritise visible SKUs; also discover catalogue pages in bounded batches."""
        snapshots = self.env['transcash.inventory.snapshot'].sudo().search(
            [], order='create_date desc,id desc', limit=250)
        done = set()
        now = fields.Datetime.now()
        for snap in snapshots:
            if snap.company_id.id in done:
                continue
            done.add(snap.company_id.id)
            sync = self.sudo().with_company(snap.company_id).get_current()
            Photo = self.env['transcash.inventory.photo'].sudo().with_company(snap.company_id)
            base = [('company_id', '=', snap.company_id.id), ('enabled', '=', True),
                    '|', ('next_retry', '=', False), ('next_retry', '<=', now)]
            to_retry = (Photo.search(base + [('status', '=', 'queued')], limit=4) |
                        Photo.search(base + [('status', 'in', ['unchecked', 'broken', 'error', 'not_found'])], limit=1))
            for rec in to_retry:
                try:
                    sync.resolve_single_sku(rec.sku, force=False)
                except Exception:
                    _logger.exception('Transcash: error con foto SKU %s', rec.sku)
            if not sync.finished and (not sync.last_error or not sync.last_run or
                                     (now - sync.last_run) >= timedelta(hours=6)):
                try:
                    sync.scan_pages(1)
                except Exception:
                    _logger.exception('Transcash: no se pudo recorrer catálogo de %s', snap.company_id.name)
            break

    def _download_listing(self, page):
        path = '/shop' if page == 1 else '/shop/page/%s' % page
        return _shop_html(SITE_ROOT + path)

    def scan_pages(self, amount=2):
        """Discover product URLs only; image resolution is a bounded second step."""
        self.ensure_one()
        if self.finished:
            return self.public_stats()
        sku_index, names = self._get_latest_sku_map()
        Photo = self.env['transcash.inventory.photo']
        for _ in range(max(1, min(int(amount), 4))):
            page = self.next_page
            if page > 90:
                self.write({'finished': True, 'last_error': 'Se alcanzó el límite de 90 páginas.'})
                break
            try:
                links = extract_catalog_links(self._download_listing(page))
            except (HTTPError, URLError, TimeoutError, ValueError, OSError) as exc:
                self.write({'last_error': ('No se pudo consultar la página %s: %s' % (page, exc))[:250],
                            'last_run': fields.Datetime.now()})
                break
            fingerprint = ','.join(str(x['template_id']) for x in links[:60])
            if fingerprint and fingerprint == self.last_page_fingerprint:
                self.write({'finished': True, 'last_error': False, 'last_run': fields.Datetime.now()})
                break
            if not links:
                empty = self.empty_pages + 1
                self.write({'empty_pages': empty, 'next_page': page + 1,
                            'last_error': False, 'last_run': fields.Datetime.now()})
                if empty >= 2:
                    self.write({'finished': True})
                continue
            new_matches = 0
            for link in links:
                sku = match_slug_prefix(link['slug'], sku_index)
                if not sku:
                    continue
                rec = Photo.search([('company_id', '=', self.env.company.id), ('sku', '=', sku)], limit=1)
                if rec and (rec.status == 'verified' or rec.match_type == 'manual'):
                    continue
                vals = {'website_url': link['url'], 'template_id_remote': link['template_id'],
                        'description': names.get(sku, sku), 'status': 'queued',
                        'next_retry': False, 'last_error': False}
                if rec:
                    rec.write(vals)
                else:
                    Photo.create(dict(vals, company_id=self.env.company.id, sku=sku, match_type='sku'))
                new_matches += 1
            self.write({'next_page': page + 1, 'examined': self.examined + len(links),
                        'matched': self.matched + new_matches, 'empty_pages': 0,
                        'last_page_fingerprint': fingerprint, 'last_error': False,
                        'last_run': fields.Datetime.now()})
        return self.public_stats()

    def reset_scan(self):
        self.ensure_one()
        self.write({'next_page': 1, 'examined': 0, 'matched': 0,
                    'finished': False, 'empty_pages': 0,
                    'last_page_fingerprint': False, 'last_error': False})

    def public_stats(self):
        self.ensure_one()
        Photo = self.env['transcash.inventory.photo']
        domain = [('company_id', '=', self.env.company.id), ('enabled', '=', True)]
        return {'next_page': self.next_page, 'examined': self.examined,
                'matched_last_scan': self.matched,
                'photos_linked': Photo.search_count(domain + [('status', '=', 'verified')]),
                'photos_pending': Photo.search_count(domain + [('status', 'in', ['queued', 'unchecked'])]),
                'photos_failed': Photo.search_count(domain + [('status', 'in', ['broken', 'error', 'not_found'])]),
                'finished': self.finished, 'last_error': self.last_error or '',
                'last_run': str(self.last_run or '')}
