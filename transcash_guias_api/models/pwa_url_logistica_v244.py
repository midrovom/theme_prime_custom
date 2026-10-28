"""Canonical PWA URL /logistica with compatibility for /transcash.

Preserves Odoo's *original* route matching (auth, methods, CSRF, business checks)
by mapping only the incoming PWA prefix before route resolution. No controller
is reimplemented and no REST /api/transcash/v1 endpoint is affected.
"""
import json
from urllib.parse import urlsplit, urlunsplit

from odoo import models
from odoo.http import request


OLD_ROOT = '/transcash'
NEW_ROOT = '/logistica'


def _is_old_path(path):
    return path == OLD_ROOT or path.startswith(OLD_ROOT + '/')


def _is_new_path(path):
    return path == NEW_ROOT or path.startswith(NEW_ROOT + '/')


def _to_new_path(path):
    return NEW_ROOT + path[len(OLD_ROOT):] if _is_old_path(path) else path


def _to_old_path(path):
    return OLD_ROOT + path[len(NEW_ROOT):] if _is_new_path(path) else path


def _rewrite_local_redirect(value, host):
    """Rewrite *only* same-host PWA redirects; never change external URLs."""
    if not value:
        return value
    parsed = urlsplit(value)
    if parsed.netloc and parsed.netloc.lower() != (host or '').lower():
        return value
    if not _is_old_path(parsed.path):
        return value
    return urlunsplit(parsed._replace(path=_to_new_path(parsed.path)))


def _new_manifest(blob):
    manifest = json.loads(blob.decode('utf-8'))
    manifest['start_url'] = NEW_ROOT
    manifest['scope'] = NEW_ROOT + '/'
    # Preserve manifest['id'] to avoid creating a second installed application.
    for shortcut in manifest.get('shortcuts', []):
        if 'url' in shortcut:
            shortcut['url'] = _rewrite_local_redirect(shortcut['url'], '')
    return json.dumps(manifest, ensure_ascii=False, separators=(',', ':')).encode('utf-8')


def _new_service_worker(blob):
    text = blob.decode('utf-8').replace('/transcash/', '/logistica/')
    # Give the new scope its own app shell so legacy installations are untouched.
    text = text.replace('transcash-pwa-v5.26-shell-1', 'logistica-pwa-v2.44-shell-1')
    text = text.replace("k.indexOf('transcash-pwa-')", "k.indexOf('logistica-pwa-')")
    return text.encode('utf-8')


def _new_offline_shell(blob):
    text = blob.decode('utf-8').replace('/transcash/', '/logistica/')
    # Offline shell is static HTML and doesn't call mobile_head.
    text = text.replace('</head>',
        '  <script defer src="/transcash_guias_api/static/src/js/pwa_url_logistica_v244.js?v=244"></script>\n</head>', 1)
    return text.encode('utf-8')


class TranscashPwaLogisticaHttp(models.AbstractModel):
    _inherit = 'ir.http'

    @classmethod
    def _match(cls, path_info):
        # URL alias only: delegate to the exact original route; all permissions,
        # CSRF and method restrictions remain those of /transcash.
        return super()._match(_to_old_path(path_info))

    @classmethod
    def _dispatch(cls, endpoint):
        response = super()._dispatch(endpoint)
        path = request.httprequest.path
        assets = {
            NEW_ROOT + '/manifest.webmanifest': _new_manifest,
            NEW_ROOT + '/sw.js': _new_service_worker,
            NEW_ROOT + '/offline': _new_offline_shell,
        }
        convert = assets.get(path)
        if convert is not None and response is not None:
            response.set_data(convert(response.get_data()))
        return response

    @classmethod
    def _post_dispatch(cls, response):
        result = super()._post_dispatch(response)
        if _is_new_path(request.httprequest.path) and response is not None:
            location = response.headers.get('Location')
            if location:
                adjusted = _rewrite_local_redirect(location, request.httprequest.host)
                if adjusted != location:
                    response.headers['Location'] = adjusted
        return result
