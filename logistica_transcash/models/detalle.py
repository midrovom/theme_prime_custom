"""Renglones de ERP y roturas por producto: cantidades de unidades incompatibles no se suman."""
import math
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare


UNIDADES = [
    ('m2', 'm²'), ('pallet', 'Pallets'), ('caja', 'Cajas'),
    ('kg', 'kg'), ('unidad', 'Unidades'),
]


class GuiaLinea(models.Model):
    _name = 'transcash.guia.linea'
    _description = 'Detalle de producto en guía'
    _order = 'secuencia,id'

    guia_id = fields.Many2one('transcash.guia', required=True, ondelete='cascade', index=True)
    secuencia = fields.Integer(default=10)
    external_line_id = fields.Char('ID línea ERP', required=True, index=True)
    codigo = fields.Char('Código/SKU', required=True)
    producto = fields.Char('Descripción del producto', required=True)
    cantidad = fields.Float('Cantidad embarcada', digits=(16, 3), required=True)
    unidad = fields.Selection(UNIDADES, required=True, string='Unidad de medida')
    precio_unitario = fields.Monetary('Valor unitario de referencia', currency_field='moneda_id')
    moneda_id = fields.Many2one(related='guia_id.moneda_id', store=True)
    vigente_erp = fields.Boolean('Vigente en ERP', default=True)
    rotura_ids = fields.One2many('transcash.rotura', 'linea_id')
    cantidad_rota_aprobada = fields.Float('Rotura aprobada', compute='_compute_rotura', digits=(16, 3))
    cantidad_rota_pendiente = fields.Float('Rotura pendiente', compute='_compute_rotura', digits=(16, 3))

    _sql_constraints = [
        ('linea_externa_unica', 'unique(guia_id, external_line_id)', 'La línea ERP ya existe en la guía.'),
        ('cantidad_positiva', 'CHECK(cantidad > 0)', 'La cantidad del producto debe ser mayor que cero.'),
    ]

    @api.depends('rotura_ids.cantidad', 'rotura_ids.estado')
    def _compute_rotura(self):
        for ln in self:
            ln.cantidad_rota_aprobada = sum(ln.rotura_ids.filtered(lambda r: r.estado == 'aprobada').mapped('cantidad'))
            ln.cantidad_rota_pendiente = sum(ln.rotura_ids.filtered(lambda r: r.estado == 'pendiente').mapped('cantidad'))


class Rotura(models.Model):
    _name = 'transcash.rotura'
    _description = 'Rotura o daño documentado por producto'
    _order = 'create_date desc,id desc'

    guia_id = fields.Many2one('transcash.guia', required=True, ondelete='cascade', index=True)
    linea_id = fields.Many2one('transcash.guia.linea', required=True, ondelete='restrict', index=True)
    codigo = fields.Char(related='linea_id.codigo', readonly=True)
    producto = fields.Char(related='linea_id.producto', readonly=True)
    unidad = fields.Selection(related='linea_id.unidad', readonly=True)
    cantidad = fields.Float('Cantidad dañada', digits=(16, 3), required=True)
    observacion = fields.Text('Descripción del daño', required=True)
    estado = fields.Selection([('pendiente','Pendiente de aprobación'),
                               ('aprobada','Aprobada'), ('rechazada','Rechazada')],
                              default='pendiente', required=True, index=True)
    reportado_por_id = fields.Many2one('res.users', readonly=True)
    revisado_por_id = fields.Many2one('res.users', readonly=True)
    fecha_revision = fields.Datetime(readonly=True)
    motivo_rechazo = fields.Text('Motivo de rechazo')
    evidencia_ids = fields.One2many('transcash.evidencia', 'rotura_id', string='Fotografías y videos')
    fecha_captura_dispositivo = fields.Char('Fecha informada por el teléfono', readonly=True)
    moneda_id = fields.Many2one(related='guia_id.moneda_id')
    monto_referencial = fields.Monetary(compute='_compute_monto', currency_field='moneda_id',
                                       string='Valor estimado')

    _sql_constraints = [('cantidad_positiva', 'CHECK(cantidad > 0)',
                         'La cantidad dañada debe ser mayor que cero.')]

    @api.depends('cantidad', 'linea_id.precio_unitario')
    def _compute_monto(self):
        for r in self:
            r.monto_referencial = r.cantidad * r.linea_id.precio_unitario

    @api.constrains('linea_id', 'guia_id')
    def _check_guia(self):
        for r in self:
            if r.linea_id.guia_id != r.guia_id:
                raise ValidationError(_('El producto no pertenece a esta guía.'))

    @api.model
    def register_damage(self, guia, linea, cantidad, observacion, archivos):
        """Archivos: lista de (base64, nombre, mime). Operación atómica con bloqueo por renglón."""
        user = self.env.user
        if user != guia.chofer_usuario_id and not guia._is_recipient(user) and not guia._is_seller(user):
            raise UserError(_('No está asignado a esta guía.'))
        if not linea or linea.guia_id != guia or not linea.vigente_erp:
            raise UserError(_('Seleccione un producto vigente de esta guía.'))
        if user == guia.chofer_usuario_id or guia._is_seller(user):
            if guia.state not in ('embarque', 'ruta', 'destino', 'revision'):
                raise UserError(_('El chofer no puede reportar daños en este estado.'))
        elif guia.state not in ('destino', 'revision', 'entregada'):
            raise UserError(_('El destinatario todavía no puede reportar daños.'))
        if guia.aprobacion_global == 'aprobada':
            raise UserError(_('La guía ya fue aprobada; solicite reapertura administrativa.'))
        if not (observacion or '').strip():
            raise UserError(_('Describa el daño.'))
        if not archivos:
            raise UserError(_('Cada rotura debe tener al menos una fotografía o video.'))
        try:
            cantidad = float(str(cantidad).replace(',', '.'))
        except (ValueError, TypeError):
            raise UserError(_('Cantidad inválida.'))
        if not math.isfinite(cantidad) or cantidad <= 0:
            raise UserError(_('La cantidad rota debe ser mayor a cero.'))
        # Evita que dos reportes simultáneos sobrepasen la cantidad despachada.
        self.env.cr.execute('SELECT id FROM transcash_guia_linea WHERE id = %s FOR UPDATE', (linea.id,))
        acumulado = sum(self.sudo().search([
            ('linea_id', '=', linea.id), ('estado', '!=', 'rechazada')]).mapped('cantidad'))
        if float_compare(acumulado + cantidad, linea.cantidad, precision_digits=3) > 0:
            raise UserError(_('Roturas reportadas (%s %s) superan lo embarcado (%s %s).') % (
                acumulado + cantidad, linea.unidad, linea.cantidad, linea.unidad))
        rotura = self.sudo().create({
            'guia_id': guia.id, 'linea_id': linea.id, 'cantidad': cantidad,
            'observacion': observacion.strip()[:4000], 'reportado_por_id': user.id,
        })
        tipo = ('novedad' if guia._is_seller(user) and user != guia.chofer_usuario_id else
                'cliente' if guia._is_recipient(user) and user != guia.chofer_usuario_id else
                'carga' if guia.state == 'embarque' else 'llegada' if guia.state in ('destino', 'revision') else 'novedad')
        for b64, name, mime in archivos:
            self.env['transcash.evidencia'].register_evidence(
                guia, tipo, observacion, b64, name, mime, 'rotura', rotura_id=rotura.id)
        guia._open_incident('Rotura en %s: %s %s' % (linea.producto, cantidad, linea.unidad))
        guia._track_event('Rotura reportada', '%s - %s %s - reporte #%s' % (
            linea.codigo, cantidad, linea.unidad, rotura.id))
        return rotura

    def _check_manager(self):
        if not self.env.user.has_group('logistica_transcash.group_transcash_ventas_admin'):
            raise UserError(_('Solo administración logística puede aprobar las roturas.'))

    def write(self, vals):
        protected = {'guia_id','linea_id','cantidad','observacion','reportado_por_id','estado'}
        if protected.intersection(vals) and not self.env.su:
            raise UserError(_('Los reportes de rotura no pueden editarse; utilice Aprobar o Rechazar.'))
        if not self.env.su and set(vals) - {'motivo_rechazo'}:
            raise UserError(_('Solo se permite editar el motivo de rechazo antes de decidir.'))
        if not self.env.su and (not self.env.user.has_group('logistica_transcash.group_transcash_ventas_admin') or
                               any(r.estado != 'pendiente' for r in self)):
            raise UserError(_('Solo Ventas puede escribir el motivo de una rotura pendiente.'))
        return super().write(vals)

    def unlink(self):
        raise UserError(_('No se pueden borrar reportes de rotura.'))

    def action_approve(self):
        self._check_manager()
        for r in self:
            if r.estado != 'pendiente':
                raise UserError(_('Solo puede aprobar reportes pendientes.'))
            if not r.evidencia_ids or any(not e.archivo for e in r.evidencia_ids):
                raise UserError(_('El reporte debe conservar sus evidencias.'))
            if r.guia_id.aprobacion_global == 'aprobada':
                raise UserError(_('La guía ya está aprobada.'))
            r.sudo().write({'estado':'aprobada','revisado_por_id':self.env.user.id,
                     'fecha_revision':fields.Datetime.now()})
            r.guia_id._track_event('Rotura aprobada', '#%d / %s %s' % (r.id, r.cantidad, r.unidad))
        return True

    def action_reject(self):
        self._check_manager()
        for r in self:
            if r.estado != 'pendiente' or not (r.motivo_rechazo or '').strip():
                raise UserError(_('Ingrese un motivo de rechazo y mantenga la rotura pendiente.'))
            r.sudo().write({'estado':'rechazada','revisado_por_id':self.env.user.id,
                     'fecha_revision':fields.Datetime.now()})
            r.guia_id._track_event('Rotura rechazada', '#%d: %s' % (r.id, r.motivo_rechazo[:200]))
        return True
