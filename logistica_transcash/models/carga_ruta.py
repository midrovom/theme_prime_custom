"""Bitácora inmutable de fotos y videos de carga capturados por Logística."""
import base64
from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


class EvidenciaCargaRuta(models.Model):
    _name = 'transcash.carga.evidencia.ruta'
    _description = 'Bitácora de evidencia de carga por hoja de ruta'
    _order = 'fecha desc, id desc'

    ruta_id = fields.Many2one('transcash.hoja.ruta', required=True, index=True, ondelete='restrict', readonly=True)
    company_id = fields.Many2one('res.company', related='ruta_id.company_id', store=True, readonly=True)
    embarque_id = fields.Many2one('transcash.embarque', related='ruta_id.embarque_id', store=True, readonly=True)
    usuario_id = fields.Many2one('res.users', string='Registrado por', readonly=True, default=lambda self: self.env.user)
    fecha = fields.Datetime('Fecha y hora', readonly=True, default=fields.Datetime.now)
    tipo = fields.Selection([('foto', 'Fotografía'), ('video', 'Video')], readonly=True, required=True)
    archivo = fields.Binary('Archivo privado', required=True, readonly=True, attachment=True, copy=False)
    nombre = fields.Char('Archivo', readonly=True, required=True)
    mime = fields.Char('Tipo de archivo', readonly=True, required=True)
    observacion = fields.Char('Detalle de la carga', readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        self.env['transcash.hoja.ruta']._check_operator()
        for vals in vals_list:
            route = self.env['transcash.hoja.ruta'].browse(vals.get('ruta_id')).exists()
            if route and route.embarque_id:
                trip = route.embarque_id
                trip._lock_driver_operation(trip.chofer_usuario_id.id)
                self.env.cr.execute('SELECT id FROM transcash_embarque WHERE id=%s FOR UPDATE', (trip.id,))
                trip.invalidate_recordset(['state'])
                route.invalidate_recordset(['state', 'embarque_id'])
            if (not route or route.company_id not in self.env.user.company_ids or
                    route.state not in ('planificada', 'cargada') or not route.embarque_id or
                    route.embarque_id.state != 'preparacion'):
                raise UserError(_('Solo registre evidencia en una ruta de un embarque en preparación.'))
            try:
                content = base64.b64decode(vals.get('archivo') or '', validate=True)
            except (ValueError, TypeError, base64.binascii.Error):
                raise ValidationError(_('El archivo recibido no es válido.'))
            if content.startswith(b'\xff\xd8\xff'):
                mime = 'image/jpeg'
            elif content.startswith(b'\x89PNG\r\n\x1a\n'):
                mime = 'image/png'
            elif content.startswith(b'RIFF') and content[8:12] == b'WEBP':
                mime = 'image/webp'
            elif len(content) >= 12 and content[4:8] == b'ftyp' and content[8:12] in (b'heic',b'heix',b'hevc',b'hevx'):
                mime = 'image/heic'
            elif len(content) >= 12 and content[4:8] == b'ftyp' and content[8:12] in (b'mif1',b'msf1'):
                mime = 'image/heif'
            elif len(content) >= 12 and content[4:8] == b'ftyp' and content[8:12] == b'qt  ':
                mime = 'video/quicktime'
            elif len(content) >= 12 and content[4:8] == b'ftyp' and content[8:12] in (
                    b'isom',b'iso2',b'iso4',b'iso5',b'iso6',b'mp41',b'mp42',b'avc1',b'M4V ',b'M4A ',b'dash'):
                mime = 'video/mp4'
            elif content.startswith(b'\x1a\x45\xdf\xa3') and b'webm' in content[:128].lower():
                mime = 'video/webm'
            else:
                mime = False
            allowed = ('image/jpeg', 'image/png', 'image/webp', 'image/heic', 'image/heif', 'video/mp4', 'video/webm', 'video/quicktime')
            if mime not in allowed or mime != vals.get('mime'):
                raise ValidationError(_('Utilice una fotografía JPG/PNG/WebP/HEIC o video MP4/WebM/MOV válido.'))
            if len(content) < 12 or len(content) > (20 if mime.startswith('image/') else 75) * 1024 * 1024:
                raise ValidationError(_('Fotografía máximo 20 MB; video máximo 75 MB.'))
            if vals.get('tipo') != ('foto' if mime.startswith('image/') else 'video'):
                raise ValidationError(_('El tipo de evidencia no corresponde al archivo.'))
            # El usuario y la hora NO se aceptan del formulario ni del cliente HTTP.
            vals['usuario_id'] = self.env.user.id
            vals['fecha'] = fields.Datetime.now()
            vals['nombre'] = (vals.get('nombre') or 'evidencia')[:160]
            vals['observacion'] = (vals.get('observacion') or '')[:500]
        records = super().create(vals_list)
        for rec in records:
            if rec.ruta_id.state == 'planificada':
                rec.ruta_id.sudo().write({'state':'cargada'})
            rec.ruta_id.message_post(body=_('Evidencia de carga registrada: %(tipo)s · %(archivo)s · Responsable: %(usuario)s.') % {
                'tipo':dict(self._fields['tipo'].selection).get(rec.tipo),
                'archivo':rec.nombre,'usuario':rec.usuario_id.display_name})
        return records

    def write(self, vals):
        raise AccessError(_('La bitácora no se modifica. Registre una nueva evidencia si necesita complementar la carga.'))

    def unlink(self):
        raise AccessError(_('No puede borrar evidencias de la bitácora de carga.'))
