# -*- coding: utf-8 -*-
"""Fotografías referenciadas desde catálogo público Transcash.

No descarga ni modifica las fichas reales de product.template/product.product.
Se vincula al código SKU que usa el snapshot de Inventario Inteligente.
"""
import json
import logging
from datetime import timedelta
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from urllib.parse import urlparse

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError

from ..services.photo_matcher import (SITE_ROOT, ALLOWED_HOSTS, extract_catalog_links,
                                      index_by_sku, match_slug_prefix, product_image_url,
                                      is_safe_photo_url, is_safe_shop_url)

_logger = logging.getLogger(__name__)


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
    image_url = fields.Char('Imagen principal')
    template_id_remote = fields.Integer('ID de producto web', readonly=True)
    match_type = fields.Selection([
        ('sku', 'SKU exacto en URL'),
        ('manual', 'Validado manualmente'),
    ], default='manual', required=True)
    enabled = fields.Boolean('Mostrar imagen', default=True)
    checked_on = fields.Datetime('Última asociación', readonly=True)
    note = fields.Text('Observaciones')

    _sql_constraints = [
        ('sku_company_unique', 'unique(company_id,sku)',
         'Ya existe una imagen asociada a este código SKU en esta empresa.'),
    ]

    @api.constrains('image_url', 'website_url')
    def _check_public_urls(self):
        for rec in self:
            if rec.image_url and not is_safe_photo_url(rec.image_url):
                raise ValidationError(_('La imagen debe ser una URL HTTPS de transcash.ec/web/image o web/content.'))
            if rec.website_url and not is_safe_shop_url(rec.website_url):
                raise ValidationError(_('La ficha debe pertenecer a https://transcash.ec/shop/...'))

    @api.model
    def images_for_skus(self, skus):
        """Restringir a los SKU solicitados; nunca entregar el snapshot entero."""
        codes = list(dict.fromkeys([str(s).strip()[:120] for s in skus if str(s).strip()]))[:80]
        if not codes:
            return {}
        rows = self.search([('company_id', '=', self.env.company.id),
                            ('sku', 'in', codes), ('enabled', '=', True)])
        return {rec.sku: {'image_url': rec.image_url, 'website_url': rec.website_url,
                          'match_type': rec.match_type}
                for rec in rows if rec.image_url}


class TranscashInventoryPhotoSync(models.Model):
    _name = 'transcash.inventory.photo.sync'
    _description = 'Seguimiento del índice público de fotografías Transcash'
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
    _sql_constraints = [
        ('company_photo_sync_unique', 'unique(company_id)', 'Ya existe sincronización para esta empresa.'),
    ]

    @api.model
    def cron_index_public_catalog(self):
        """Indexar pocos enlaces públicos sin bloquear el panel web.

        Se limita a UNA empresa por ejecución para proteger los workers Odoo
        y evitar peticiones masivas al sitio de comercio electrónico.
        """
        snapshots = self.env['transcash.inventory.snapshot'].sudo().search([], order='create_date desc, id desc', limit=250)
        checked = set()
        now = fields.Datetime.now()
        for snap in snapshots:
            cid = snap.company_id.id
            if cid in checked:
                continue
            checked.add(cid)
            sync = self.sudo().with_company(snap.company_id).get_current()
            if sync.finished:
                continue
            # No martillar el catálogo cuando está caído / bloqueado.
            if sync.last_error and sync.last_run and (now - sync.last_run) < timedelta(hours=6):
                continue
            try:
                sync.scan_pages(2)
            except Exception:
                _logger.exception('Transcash: no se pudo indexar imágenes públicas de la empresa %s', cid)
            break

    @api.model
    def get_current(self):
        rec = self.search([('company_id', '=', self.env.company.id)], limit=1)
        if not rec:
            rec = self.create({'company_id': self.env.company.id})
        return rec

    def reset_scan(self):
        self.ensure_one()
        self.write({'next_page': 1, 'examined': 0, 'matched': 0,
                    'finished': False, 'empty_pages': 0, 'last_page_fingerprint': False, 'last_error': False})

    @api.model
    def _get_latest_sku_map(self):
        snapshot = self.env['transcash.inventory.snapshot'].search([
            ('company_id', '=', self.env.company.id)], limit=1,
            order='create_date desc, id desc')
        if not snapshot:
            raise UserError(_('Primero importe el Excel de inventario desde Cargar archivos.'))
        dataset = json.loads(snapshot.get_dashboard_json())
        items = [(str(p[0]), str(p[1])) for p in dataset.get('products', []) if len(p) > 1]
        return index_by_sku([sku for sku, name in items]), dict(items)

    def _download_listing(self, page):
        path = '/shop' if page == 1 else '/shop/page/%s' % page
        url = SITE_ROOT + path
        headers = {'User-Agent': 'TranscashInventoryPhotoCatalog/1.3 (ERP; catalog-index)',
                   'Accept': 'text/html,application/xhtml+xml',
                   'Accept-Language': 'es-EC,es;q=0.9'}
        req = Request(url, headers=headers)
        # Redirecciones a otros dominios están prohibidas.
        with urlopen(req, timeout=12) as response:
            parsed = urlparse(response.geturl())
            if parsed.scheme != 'https' or parsed.hostname not in ALLOWED_HOSTS:
                raise ValueError('Redirección a dominio no permitido')
            if 'text/html' not in (response.headers.get('Content-Type') or ''):
                raise ValueError('La tienda no devolvió HTML')
            raw = response.read(3 * 1024 * 1024 + 1)
            if len(raw) > 3 * 1024 * 1024:
                raise ValueError('Página demasiado grande')
            return raw.decode('utf-8', errors='replace')

    def scan_pages(self, amount=2):
        self.ensure_one()
        if self.finished:
            return self.public_stats()
        sku_index, names = self._get_latest_sku_map()
        Photo = self.env['transcash.inventory.photo']
        pages = max(1, min(int(amount), 4))
        found = 0
        for _ in range(pages):
            page = self.next_page
            if page > 90:
                self.write({'finished': True, 'last_error': 'Límite de 90 páginas alcanzado. Revise el catálogo.'})
                break
            try:
                links = extract_catalog_links(self._download_listing(page))
            except (HTTPError, URLError, TimeoutError, ValueError, OSError) as exc:
                msg = 'No se pudo consultar %s/shop/page/%d: %s' % (SITE_ROOT, page, str(exc)[:180])
                self.write({'last_error': msg, 'last_run': fields.Datetime.now()})
                _logger.warning('Transcash: %s', msg)
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
                    break
                continue
            self.write({'empty_pages': 0, 'last_page_fingerprint': fingerprint})
            for link in links:
                sku = match_slug_prefix(link['slug'], sku_index)
                if not sku:
                    continue
                existing = Photo.search([('company_id', '=', self.env.company.id),
                                         ('sku', '=', sku)], limit=1)
                # No sobrescribir enlaces curados manualmente.
                if existing and existing.match_type == 'manual':
                    continue
                vals = {'company_id': self.env.company.id, 'sku': sku,
                        'description': names.get(sku, sku), 'website_url': link['url'],
                        'template_id_remote': link['template_id'],
                        'image_url': product_image_url(link['template_id']),
                        'match_type': 'sku', 'checked_on': fields.Datetime.now()}
                if existing:
                    existing.write(vals)
                else:
                    Photo.create(vals)
                found += 1
            self.write({'next_page': page + 1, 'examined': self.examined + len(links),
                        'matched': self.matched + found, 'last_error': False,
                        'last_run': fields.Datetime.now()})
            found = 0
        return self.public_stats()

    def public_stats(self):
        self.ensure_one()
        count = self.env['transcash.inventory.photo'].search_count([
            ('company_id', '=', self.env.company.id), ('enabled', '=', True)])
        return {'next_page': self.next_page, 'examined': self.examined,
                'matched_last_scan': self.matched, 'photos_linked': count,
                'finished': self.finished, 'last_error': self.last_error or '',
                'last_run': str(self.last_run or '')}
