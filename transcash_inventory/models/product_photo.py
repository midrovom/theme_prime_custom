# -*- coding: utf-8 -*-
"""Verified public product photography, separated from inventory snapshots.

A product's shop id is NOT assumed to be its product.product id. The image
link is read from its public HTML and validated as a real image response.
"""
import json
import logging
import base64
import binascii
from io import BytesIO
from PIL import Image, UnidentifiedImageError
from datetime import timedelta
from urllib.parse import urlencode, urlparse, quote
import ipaddress
import socket
from functools import lru_cache
import time
from urllib.request import Request, urlopen, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError, URLError

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError, AccessError

from ..services.photo_matcher import (
    DEFAULT_SITE_ROOT, allowed_hosts, extract_catalog_links, extract_product_image_candidates,
    index_by_sku, match_slug_prefix, product_from_url, product_image_url,
    is_safe_photo_url, is_safe_shop_url, normalize_site_root,
)

_logger = logging.getLogger(__name__)
MAX_HTML = 3 * 1024 * 1024
AGENT = 'TranscashInventoryPhoto/1.5 (+catalog-image-validation)'


def _public_dns(host):
    return _public_dns_cached(host, int(time.time() // 300))


@lru_cache(maxsize=256)
def _public_dns_cached(host, bucket):
    """Reject internal/private target addresses for administrator-configured sites."""
    try:
        addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        if not addresses:
            return False
        return all(ipaddress.ip_address(entry[4][0]).is_global for entry in addresses)
    except (OSError, ValueError):
        return False


def _safe_remote(url, site_root):
    try:
        p = urlparse(url)
        return (len(url) <= 2048 and p.scheme == 'https' and
                p.hostname in allowed_hosts(site_root) and
                p.port in (None, 443) and not p.username and not p.password and
                _public_dns(p.hostname))
    except (ValueError, TypeError):
        return False


class _RestrictedRedirect(HTTPRedirectHandler):
    def __init__(self, site_root):
        super().__init__()
        self.site_root = site_root

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not _safe_remote(newurl, self.site_root):
            raise ValueError('Redirección a un dominio o puerto no permitido')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _http_get(url, site_root, accept='text/html', max_bytes=MAX_HTML):
    if not _safe_remote(url, site_root):
        raise ValueError('La URL no pertenece a la tienda HTTPS configurada o no es pública')
    headers = {'User-Agent': AGENT, 'Accept': accept, 'Accept-Language': 'es-EC,es;q=0.9'}
    opener = build_opener(_RestrictedRedirect(site_root))
    with opener.open(Request(url, headers=headers), timeout=10) as response:
        if not _safe_remote(response.geturl(), site_root):
            raise ValueError('Redirección a otro dominio no permitida')
        content_type = (response.headers.get('Content-Type') or '').lower()
        content = response.read(max_bytes + 1)
        if len(content) > max_bytes:
            raise ValueError('Respuesta remota demasiado grande')
        return content_type, content


def _shop_html(url, site_root):
    typ, data = _http_get(url, site_root, max_bytes=MAX_HTML)
    if 'text/html' not in typ and 'application/xhtml+xml' not in typ:
        raise ValueError('La tienda no devolvió HTML')
    return data.decode('utf-8', errors='replace')


def _valid_image_signature(buf):
    return (buf.startswith(b'\xff\xd8\xff') or
            buf.startswith(b'\x89PNG\r\n\x1a\n') or
            buf.startswith((b'GIF87a', b'GIF89a')) or
            (len(buf) >= 12 and buf[:4] == b'RIFF' and buf[8:12] == b'WEBP'))


def _verified_photo_with_thumbnail(url, site_root):
    """Check image bytes and store a bounded 240px JPEG for same-origin display."""
    if not is_safe_photo_url(url, site_root) or not _safe_remote(url, site_root):
        return None
    headers = {'User-Agent': AGENT, 'Accept': 'image/webp,image/png,image/jpeg,image/gif,image/*'}
    try:
        with build_opener(_RestrictedRedirect(site_root)).open(Request(url, headers=headers), timeout=10) as response:
            if not _safe_remote(response.geturl(), site_root):
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



def _stored_thumbnail_jpeg(record):
    """Return a *real* stored JPEG, not a truthy Odoo bin_size placeholder.

    A status of ``verified`` is historical metadata and does not prove that
    its attachment still exists (for example, a database restored without its
    Odoo filestore). Never copy invalid bytes between companies.
    """
    try:
        # ``bin_size`` context can give values such as '18.3 Kb'. Binary
        # fields backed by ir.attachment must be fetched as full base64.
        encoded = record.with_context(bin_size=False).image_thumbnail
        if not encoded:
            return None
        if isinstance(encoded, str):
            encoded = encoded.encode('ascii')
        if not isinstance(encoded, bytes) or len(encoded) > 1024 * 1024:
            return None
        raw = base64.b64decode(encoded, validate=True)
        if not (100 <= len(raw) <= 700 * 1024 and
                raw.startswith(b'\xff\xd8\xff') and raw.endswith(b'\xff\xd9')):
            return None
        with Image.open(BytesIO(raw)) as pic:
            if pic.format != 'JPEG' or not (20 <= pic.width <= 300 and 20 <= pic.height <= 300):
                return None
            pic.verify()
        return raw
    except (ValueError, TypeError, UnicodeError, OSError, SyntaxError,
            Image.DecompressionBombError, binascii.Error):
        return None


class TranscashInventoryPhoto(models.Model):
    _name = 'transcash.inventory.photo'
    _description = 'Fotografía comercial SKU Transcash'
    _rec_name = 'sku'
    _order = 'sku'

    company_id = fields.Many2one('res.company', required=True, index=True,
                                 default=lambda self: self.env.company)
    sku = fields.Char('SKU', required=True, index=True)
    description = fields.Char('Descripción inventario', readonly=True)
    website_url = fields.Char('Ficha de la tienda')
    image_url = fields.Char('Imagen principal verificada')
    image_thumbnail = fields.Binary('Miniatura almacenada', attachment=True, readonly=True)
    # Form/list preview uses our authenticated JPEG endpoint rather than
    # Odoo's generic /web/image/<model>/<id>/<field> attachment route.  Some
    # deployments can write/read the attachment with sudo while ordinary users
    # cannot stream the attachment through /web/image (invisible placeholder).
    # These transient fields add no new table columns or duplicate image data.
    image_preview_small_html = fields.Html('Vista previa',
        compute='_compute_image_previews', sanitize=False, readonly=True)
    image_preview_large_html = fields.Html('Miniatura almacenada',
        compute='_compute_image_previews', sanitize=False, readonly=True)
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

    @api.depends('sku', 'company_id', 'status', 'enabled', 'write_date')
    def _compute_image_previews(self):
        """Show the image that /photos/thumb can actually serve.

        Avoid the generic image widget's attachment stream and its stale
        placeholder. The endpoint checks the selected company and user group
        on every image request and reads only that company's verified JPEG.
        """
        for rec in self:
            missing = '<span class="text-muted">Miniatura no disponible</span>'
            small, large = missing, missing
            if rec.id and rec.enabled and rec.status == 'verified' and rec.company_id and rec.sku:
                # Authentication already controls which photo records may be
                # read; sudo is used only to inspect the same record's binary,
                # not to choose any other company's data.
                jpeg = _stored_thumbnail_jpeg(rec.sudo())
                if jpeg:
                    url = ('/transcash_inventory/photos/thumb?sku=%s&amp;company_id=%d'
                           % (quote(rec.sku, safe=''), rec.company_id.id))
                    if rec.write_date:
                        url += '&amp;v=%s' % rec.write_date.strftime('%Y%m%d%H%M%S%f')
                    # SKU is percent-encoded; the fixed URL is safe even with
                    # sanitize=False (HTML here never includes raw user data).
                    small = ('<img src="%s" width="76" height="76" '
                             'alt="Fotografía SKU" loading="lazy" '
                             'style="max-width:76px;object-fit:contain"/>') % url
                    large = ('<img src="%s" width="240" height="240" '
                             'alt="Fotografía SKU" loading="lazy" '
                             'style="max-width:100%%;object-fit:contain"/>') % url
            rec.image_preview_small_html = small
            rec.image_preview_large_html = large

    @api.constrains('image_url', 'website_url')
    def _check_public_urls(self):
        for rec in self:
            if rec.image_url and not is_safe_photo_url(rec.image_url, rec.company_id.transcash_photo_site_url or DEFAULT_SITE_ROOT):
                raise ValidationError(_('La imagen debe pertenecer al dominio HTTPS configurado para esta empresa.'))
            if rec.website_url and not is_safe_shop_url(rec.website_url, rec.company_id.transcash_photo_site_url or DEFAULT_SITE_ROOT):
                raise ValidationError(_('La ficha debe pertenecer a /shop/ en el dominio configurado para esta empresa.'))

    def action_repair_thumbnail(self):
        # Explicit one-SKU recovery from the Odoo form; no mass import and no
        # change to the linked inventory dataset or other companies.
        self.ensure_one()
        if not (self.env.user.has_group('transcash_inventory.group_transcash_manager') or
                self.env.user.has_group('base.group_system')):
            raise UserError(_('No tiene permisos para reparar fotografías manualmente.'))
        rec = self.sudo().with_company(self.company_id)
        sync = self.env['transcash.inventory.photo.sync'].sudo().with_company(self.company_id).get_current()
        result = sync.resolve_single_sku(rec.sku, force=True)
        ok = result.status == 'verified' and bool(_stored_thumbnail_jpeg(result))
        return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
            'title': _('Fotografía recuperada') if ok else _('No se pudo recuperar la fotografía'),
            'message': _('Imagen guardada correctamente') if ok else (result.last_error or _('La tienda no devolvió la fotografía.')),
            'type': 'success' if ok else 'warning', 'sticky': not ok,
            # display_notification by itself leaves the old Binary widget in
            # memory; refresh the form after the toast so the new preview loads.
            'next': {'type': 'ir.actions.client', 'tag': 'reload'},
        }}

    def write(self, vals):
        # If a URL is modified by hand in Odoo's list/form, its old cached
        # photograph is no longer reliable until verified again.
        if ('image_url' in vals or 'website_url' in vals) and 'status' not in vals:
            vals = dict(vals, status='unchecked', image_thumbnail=False,
                        next_retry=False, last_error=False)
        return super().write(vals)

    @api.model
    def images_for_skus(self, skus):
        if not (self.env.user.has_group('transcash_inventory.group_transcash_user') or
                self.env.user.has_group('base.group_system')):
            raise AccessError(_('No tiene permiso de consulta de fotografías.'))
        codes = list(dict.fromkeys([str(s).strip()[:120] for s in skus if str(s).strip()]))[:80]
        if not codes:
            return {}
        # The caller checks user access and restricts the company. Use sudo
        # only to fetch attachments from that explicitly authorized company:
        # read-only staff cannot necessarily read ir.attachment directly.
        rows = self.sudo().with_context(bin_size=False).search([
            ('company_id', '=', self.env.company.id),
            ('sku', 'in', codes), ('enabled', '=', True)])
        result = {}
        for rec in rows:
            healthy = bool(_stored_thumbnail_jpeg(rec)) if rec.status == 'verified' else False
            broken = rec.status == 'verified' and not healthy
            result[rec.sku] = {
                'image_url': ('/transcash_inventory/photos/thumb?sku=' +
                              quote(rec.sku, safe='') + '&company_id=' + str(self.env.company.id))
                             if healthy else '',
                'source_url': rec.image_url or '',
                'website_url': rec.website_url or '',
                'match_type': rec.match_type,
                'status': 'broken' if broken else rec.status,
                'error': ('Miniatura ausente o dañada. El sistema la recuperará desde la tienda.')
                         if broken else (rec.last_error or ''),
            }
        return result


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
            raise UserError(_('Primero sincronice el inventario desde Sincronización API.'))
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
        sku_index, names = self._get_latest_sku_map()
        lookup = {s.casefold(): s for s in names}
        now = fields.Datetime.now()
        found = 0
        codes = list(dict.fromkeys(str(x).strip()[:120] for x in skus if str(x).strip()))[:80]
        for code in codes:
            canonical = lookup.get(code.casefold())
            if not canonical:
                continue
            rec = self._photo_record(canonical, names[canonical])
            healthy = bool(_stored_thumbnail_jpeg(rec)) if rec.status == 'verified' else False
            if rec.status == 'verified' and healthy and not force:
                continue
            # Reuse a verified PUBLIC photo from the same store immediately,
            # even if a previous remote search left a long retry backoff.
            if not force and rec.status != 'verified' and self._reuse_public_photo_from_another_company(
                    canonical, sku_index, rec):
                found += 1
                continue
            missing_attachment = rec.status == 'verified' and not healthy
            if not force and not missing_attachment and rec.next_retry and rec.next_retry > now:
                continue
            if force or missing_attachment or rec.status not in ('queued', 'verified'):
                rec.write({'status': 'queued', 'next_retry': False, 'last_error': False})
                found += 1
        return found

    def _site_root(self):
        return self.env['res.company'].transcash_photo_root()

    def _search_public_product(self, sku, description, sku_index):
        # Odoo shop search is public, but its search behaviour may depend on the
        # site's configuration. Always confirm exact SKU prefix in returned URLs.
        terms = [sku]
        if description:
            terms.append(description[:80])
        for term in terms:
            site_root = self._site_root()
            html = _shop_html(site_root + '/shop?' + urlencode({'search': term}), site_root)
            for link in extract_catalog_links(html, site_root):
                if match_slug_prefix(link['slug'], sku_index) == sku:
                    return link
        return None

    def _verify_shop_photo(self, shop_link):
        """Check shop SKU & image response; never assume template and variant IDs match."""
        site_root = self._site_root()
        html = _shop_html(shop_link['url'], site_root)
        candidates = extract_product_image_candidates(html, shop_link['url'], shop_link['template_id'], site_root)
        # Some older templates omit OpenGraph; these URLs are fallbacks only
        # and *must* pass actual image-response validation before being saved.
        candidates.extend([
            '%s/web/image/product.template/%d/image_1920' % (site_root, shop_link['template_id']),
            product_image_url(shop_link['template_id'], site_root),
        ])
        tested = set()
        for url in candidates[:12]:
            if url in tested:
                continue
            tested.add(url)
            thumbnail = _verified_photo_with_thumbnail(url, site_root)
            if thumbnail:
                return url, thumbnail
        raise ValueError('La ficha existe, pero ninguna URL devuelve una imagen JPEG, PNG, GIF o WebP válida')

    def _reuse_public_photo_from_another_company(self, sku, sku_index, record):
        """Replicate only public images verified for the same SKU and storefront.

        The record is always created/updated in the current company. Do not
        reuse assets from a different shop, or expose another company's data.
        This deliberately runs only after the exact SKU was validated against
        the current company's latest inventory snapshot.
        """
        site_root = self._site_root()
        candidates = self.env['transcash.inventory.photo'].sudo().search([
            ('company_id', '!=', self.env.company.id),
            ('sku', '=', sku), ('enabled', '=', True),
            ('status', '=', 'verified'),
        ], limit=25)
        for source in candidates:
            valid_jpeg = _stored_thumbnail_jpeg(source)
            if not valid_jpeg:
                continue
            try:
                source_root = source.company_id.sudo().transcash_photo_site_url
                link = product_from_url(source.website_url, site_root)
                if (source_root != site_root or not link or
                        match_slug_prefix(link['slug'], sku_index) != sku or
                        not is_safe_photo_url(source.image_url, site_root)):
                    continue
                record.write({
                    'website_url': link['url'],
                    'image_url': source.image_url,
                    'image_thumbnail': base64.b64encode(valid_jpeg),
                    'template_id_remote': source.template_id_remote,
                    'match_type': 'sku',
                    'status': 'verified',
                    'checked_on': fields.Datetime.now(),
                    'next_retry': fields.Datetime.now() + timedelta(days=30),
                    'last_error': False,
                })
                return True
            except (ValueError, ValidationError):
                continue
        return False

    def resolve_single_sku(self, sku, supplied_url=None, manual=False, force=True, sku_map=None):
        self.ensure_one()
        # Cron processes multiple SKUs from one snapshot. An optional already
        # validated map prevents repeatedly reading/decoding the full dataset.
        sku_index, names = sku_map if sku_map is not None else self._get_latest_sku_map()
        canonical = next((s for s in names if s.casefold() == str(sku).strip().casefold()), None)
        if not canonical:
            raise UserError(_('El SKU no existe en el último inventario importado.'))
        # Reject mismatched manual links without mutating any existing photo.
        if supplied_url:
            supplied_link = product_from_url(supplied_url, self._site_root())
            if not supplied_link or match_slug_prefix(supplied_link['slug'], sku_index) != canonical:
                raise UserError(_('La dirección web no corresponde al SKU indicado.'))
        rec = self._photo_record(canonical, names[canonical])
        now = fields.Datetime.now()
        verified_jpeg = _stored_thumbnail_jpeg(rec) if rec.status == 'verified' else None
        requires_repair = rec.status == 'verified' and not verified_jpeg
        if not force and not requires_repair and rec.next_retry and rec.next_retry > now:
            return rec
        if rec.status == 'verified' and verified_jpeg and not force:
            return rec
        # Exact SKU + same HTTPS shop permits public-photo reuse between
        # companies without any additional network request or cross-company
        # inventory access. Explicit manual linking always takes precedence.
        if (not supplied_url and rec.status != 'verified' and
                self._reuse_public_photo_from_another_company(canonical, sku_index, rec)):
            return rec
        preserved_verified = bool(verified_jpeg)
        vals = {'checked_on': now, 'attempt_count': rec.attempt_count + 1,
                'last_error': False, 'next_retry': False}
        try:
            # Restore a missing filestore attachment using the *already
            # verified* URL first. No catalogue search and no SKU reassignment.
            # If that URL is stale, fall through to the existing shop logic.
            stored_link = product_from_url(rec.website_url, self._site_root())
            valid_record_link = (stored_link and
                                 match_slug_prefix(stored_link['slug'], sku_index) == canonical)
            # A damaged previously-verified photo is marked queued by the
            # browser/cron. Its URL remains valid for repair after that status
            # change, so don't limit this fast path to status='verified'.
            if (not supplied_url and not verified_jpeg and valid_record_link and
                    is_safe_photo_url(rec.image_url, self._site_root())):
                restored = _verified_photo_with_thumbnail(rec.image_url, self._site_root())
                if restored:
                    rec.write(dict(vals, status='verified', image_thumbnail=restored,
                                   next_retry=now + timedelta(days=30)))
                    return rec
            shop_link = product_from_url(supplied_url or rec.website_url, self._site_root())
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
            if supplied_url and product_from_url(supplied_url, self._site_root()):
                vals['website_url'] = product_from_url(supplied_url, self._site_root())['url']
        except (HTTPError, URLError, OSError, TimeoutError) as exc:
            # A blocked/outage site is not proof the product has no photo.
            vals.update({'status': 'error', 'image_url': False, 'image_thumbnail': False,
                         'last_error': ('Error consultando tienda: %s' % str(exc))[:250],
                         'next_retry': now + timedelta(hours=12)})
            if supplied_url and product_from_url(supplied_url, self._site_root()):
                vals['website_url'] = product_from_url(supplied_url, self._site_root())['url']
        if not supplied_url and rec.image_url and vals.get('status') != 'verified':
            # The cached file may be gone while its validated source link is
            # still correct. Keep the link for the next repair attempt.
            vals.pop('image_url', None)
            vals.pop('website_url', None)
        if preserved_verified and not supplied_url and vals.get('status') != 'verified':
            # A timeout, rate-limit or changed public search page is not proof
            # that the previously checked JPEG is invalid. Leave it visible.
            vals.pop('image_url', None)
            vals.pop('image_thumbnail', None)
            vals['status'] = 'verified'
        rec.write(vals)
        return rec

    @api.model
    def cron_repair_missing_thumbnails(self):
        """Repair verified links whose local JPEG was lost, automatically.

        A previous scheduled job only inspected 35 verified photos every 15 min
        and repaired up to 3 per company. That made large production databases
        appear stuck. This dedicated worker audits a rotating window and
        repairs already-linked SKUs first, in a short, bounded transaction.

        No writes to imported inventory/snapshots, and never blindly forces
        re-downloads of healthy thumbnails. Each company is handled separately.
        """
        # Cron can run on multiple Odoo workers. Prevent simultaneous runs of
        # this repair worker inside the same PostgreSQL database.
        self.env.cr.execute('SELECT pg_try_advisory_xact_lock(%s)', [18480148])
        if not self.env.cr.fetchone()[0]:
            return
        Snapshot = self.env['transcash.inventory.snapshot'].sudo()
        grouped = Snapshot.read_group([], ['company_id'], ['company_id'], lazy=False)
        company_ids = sorted(int(row['company_id'][0]) for row in grouped
                             if row.get('company_id'))
        if not company_ids:
            return
        params = self.env['ir.config_parameter'].sudo()
        key = 'transcash_inventory.photo_repair.last_company_id'
        try:
            last_cid = int(params.get_param(key) or 0)
        except (ValueError, TypeError):
            last_cid = 0
        rotated = ([cid for cid in company_ids if cid > last_cid] +
                   [cid for cid in company_ids if cid <= last_cid])[:4]
        # More companies means a smaller batch for each, so the scheduled job
        # will not block Odoo while the remote site is slow or rate-limited.
        per_company_limit = min(12, max(4, 16 // len(rotated)))
        max_runtime_seconds = 45
        started = time.monotonic()
        inspected = repaired = attempted = 0
        for cid in rotated:
            if time.monotonic() - started >= max_runtime_seconds:
                break
            try:
                with self.env.cr.savepoint():
                    company = self.env['res.company'].sudo().browse(cid)
                    Photo = self.env['transcash.inventory.photo'].sudo().with_company(company)
                    sync = self.sudo().with_company(company).get_current()
                    now = fields.Datetime.now()
                    cursor_key = 'transcash_inventory.photo_repair.check_id.%d' % cid
                    try:
                        cursor = int(params.get_param(cursor_key) or 0)
                    except (TypeError, ValueError):
                        cursor = 0
                    verified_domain = [('company_id', '=', cid), ('enabled', '=', True),
                                       ('status', '=', 'verified')]
                    check_rows = Photo.search(verified_domain + [('id', '>', cursor)],
                                              order='id', limit=180)
                    if not check_rows:
                        check_rows = Photo.search(verified_domain, order='id', limit=180)
                    if check_rows:
                        params.set_param(cursor_key, str(check_rows[-1].id))
                    for rec in check_rows:
                        inspected += 1
                        if not _stored_thumbnail_jpeg(rec):
                            # URL/SKU links remain intact; only the state is
                            # queued for the existing single-SKU repair path.
                            rec.write({'status': 'queued', 'next_retry': False,
                                       'last_error': 'Recuperación automática de miniatura'})
                    due = ['|', ('next_retry', '=', False), ('next_retry', '<=', now)]
                    base = [('company_id', '=', cid), ('enabled', '=', True)]
                    # 1. Recover broken historical photo links first: one HTTPS
                    # download using the already verified and stored URL.
                    prioritized = Photo.search(base + [('status', '=', 'queued'),
                        ('image_url', '!=', False)] + due, order='id', limit=per_company_limit)
                    remaining = per_company_limit - len(prioritized)
                    others = Photo.browse()
                    if remaining:
                        others = Photo.search(base + [('status', '=', 'queued'),
                            ('image_url', '=', False)] + due, order='id', limit=remaining)
                    remaining -= len(others)
                    # Preserve previous behavior for older failed/unverified
                    # records without starving repair of stored image URLs.
                    fallback = Photo.browse()
                    if remaining:
                        fallback = Photo.search(base + [('status', 'in',
                            ['unchecked', 'broken', 'error', 'not_found'])] + due,
                            order='id', limit=min(remaining, 2))
                    batch = prioritized | others | fallback
                    if batch:
                        # Build the SKU map only once per company/batch (not
                        # once for every photo). Crucial for large inventories.
                        sku_map = sync._get_latest_sku_map()
                    for rec in batch:
                        if time.monotonic() - started >= max_runtime_seconds:
                            break
                        attempted += 1
                        try:
                            with self.env.cr.savepoint():
                                outcome = sync.resolve_single_sku(
                                    rec.sku, force=False, sku_map=sku_map)
                                if outcome.status == 'verified' and _stored_thumbnail_jpeg(outcome):
                                    repaired += 1
                        except Exception as exc:
                            _logger.exception('Transcash: reparación automática SKU %s / empresa %s',
                                              rec.sku, cid)
                            # Keep source URL and SKU even when a transient
                            # exception occurs; retry with backoff, not every
                            # 2 minutes forever on the first broken item.
                            with self.env.cr.savepoint():
                                rec.write({'status': 'error',
                                           'next_retry': fields.Datetime.now() + timedelta(hours=2),
                                           'last_error': ('Reparación automática: %s' % exc)[:250]})
            except Exception:
                _logger.exception('Transcash: recuperación automática fallida en empresa %s', cid)
            # Advance cursor even if one company has no photos or errors.
            params.set_param(key, str(cid))
        _logger.info('Transcash: fotos recuperadas %d de %d intentos; verificadas %d miniaturas',
                     repaired, attempted, inspected)

    @api.model
    def cron_index_public_catalog(self):
        """Keep public-shop discovery running, separately from repair.

        A lightweight round-robin crawler locates NEW SKU links. The dedicated
        two-minute cron above restores MISSING saved miniatures without waiting
        for public shop pagination or re-scanning whole catalog pages.
        """
        Snapshot = self.env['transcash.inventory.snapshot'].sudo()
        grouped = Snapshot.read_group([], ['company_id'], ['company_id'], lazy=False)
        company_ids = sorted(int(group['company_id'][0]) for group in grouped
                             if group.get('company_id'))
        if not company_ids:
            return
        params = self.env['ir.config_parameter'].sudo()
        key = 'transcash_inventory.photo_cron.last_company_id'
        try:
            last_company_id = int(params.get_param(key) or 0)
        except (TypeError, ValueError):
            last_company_id = 0
        rotated = ([cid for cid in company_ids if cid > last_company_id] +
                   [cid for cid in company_ids if cid <= last_company_id])
        now = fields.Datetime.now()
        for cid in rotated[:4]:
            try:
                with self.env.cr.savepoint():
                    company = self.env['res.company'].sudo().browse(cid)
                    sync = self.sudo().with_company(company).get_current()
                    if not sync.finished and (not sync.last_error or not sync.last_run or
                                              (now - sync.last_run) >= timedelta(hours=6)):
                        try:
                            with self.env.cr.savepoint():
                                sync.scan_pages(1)
                        except Exception:
                            _logger.exception('Transcash: fallo indexando catálogo de empresa %s', cid)
            except Exception:
                _logger.exception('Transcash: fallo aislado en fotos de empresa %s', cid)
            params.set_param(key, str(cid))

    def _download_listing(self, page):
        path = '/shop' if page == 1 else '/shop/page/%s' % page
        site_root = self._site_root()
        return _shop_html(site_root + path, site_root)

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
                links = extract_catalog_links(self._download_listing(page), self._site_root())
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
        return {'site_root': self._site_root(), 'next_page': self.next_page, 'examined': self.examined,
                'matched_last_scan': self.matched,
                'photos_linked': Photo.search_count(domain + [('status', '=', 'verified')]),
                'photos_pending': Photo.search_count(domain + [('status', 'in', ['queued', 'unchecked'])]),
                'photos_failed': Photo.search_count(domain + [('status', 'in', ['broken', 'error', 'not_found'])]),
                'finished': self.finished, 'last_error': self.last_error or '',
                'last_run': str(self.last_run or '')}
