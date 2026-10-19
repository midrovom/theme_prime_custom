"""Liquidaciones documentales del transporte: NO genera asientos ni facturas Odoo.

El proveedor emite su factura en su propio sistema, entrega comprobante y Transcash
registra revisión y pagos reales (incluso parciales) con trazabilidad por embarque.
"""
import base64
import math
from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools import float_compare
from markupsafe import Markup, escape


def _is_pdf_or_image(blob):
    return blob.startswith(b'%PDF-') or blob.startswith(b'\xff\xd8\xff') or blob.startswith(b'\x89PNG\r\n\x1a\n')


class TranscashLiquidacion(models.Model):
    _name = 'transcash.pago.liquidacion'
    _description = 'Liquidación documental al proveedor de transporte'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc, id desc'

    name = fields.Char('Liquidación', required=True, default='Nuevo', copy=False, readonly=True)
    company_id = fields.Many2one('res.company', required=True, readonly=True)
    proveedor_id = fields.Many2one('res.partner', required=True, readonly=True)
    moneda_id = fields.Many2one('res.currency', related='company_id.currency_id', readonly=True)
    estado = fields.Selection([
        ('borrador', 'Preparando liquidación'),
        ('revision', 'Factura enviada / por revisar'),
        ('observada', 'Observada por Contabilidad'),
        ('proceso_pago', 'Aprobada / en proceso de pago'),
        ('parcial', 'Pagada parcialmente'),
        ('pagada', 'Pagada'),
    ], default='borrador', required=True, readonly=True, tracking=True)
    linea_ids = fields.One2many('transcash.pago.liquidacion.linea', 'liquidacion_id', string='Viajes liquidados', readonly=True)
    pago_ids = fields.One2many('transcash.pago.registro', 'liquidacion_id', string='Pagos', readonly=True)
    total_acordado = fields.Monetary(compute='_compute_totales', currency_field='moneda_id', string='Fletes aprobados')
    total_pagado = fields.Monetary(compute='_compute_totales', currency_field='moneda_id', string='Pagado')
    saldo_pendiente = fields.Monetary(compute='_compute_totales', currency_field='moneda_id', string='Saldo pendiente')
    factura_numero = fields.Char('Número de factura del proveedor', readonly=True, copy=False)
    factura_fecha = fields.Date('Fecha de factura', readonly=True, copy=False)
    factura_subtotal = fields.Monetary('Subtotal facturado', currency_field='moneda_id', readonly=True, copy=False)
    factura_impuestos = fields.Monetary('Impuestos declarados', currency_field='moneda_id', readonly=True, copy=False)
    factura_total = fields.Monetary('Total factura', compute='_compute_factura_total', currency_field='moneda_id')
    factura_archivo = fields.Binary('Factura adjunta (PDF/JPG/PNG)', attachment=True, readonly=True, copy=False)
    factura_nombre = fields.Char('Archivo factura', readonly=True, copy=False)
    observacion_proveedor = fields.Text('Observaciones del proveedor', readonly=True)
    observacion_contabilidad = fields.Text('Observaciones de Contabilidad', readonly=True)
    revisado_por_id = fields.Many2one('res.users', readonly=True, string='Revisado por')
    fecha_revision = fields.Datetime('Fecha de revisión', readonly=True)
    confirmacion_pagos = fields.Selection([
        ('sin_pagos', 'Sin transferencias'),
        ('pendiente', 'Por confirmar por proveedor'),
        ('parcial', 'Algunas transferencias confirmadas'),
        ('confirmada', 'Todas las transferencias confirmadas'),
        ('disputa', 'Discrepancia reportada por proveedor'),
    ], string='Confirmación bancaria del proveedor', compute='_compute_confirmacion_pagos')

    @api.depends('pago_ids.anulado', 'pago_ids.recepcion_estado')
    def _compute_confirmacion_pagos(self):
        for rec in self:
            payments = rec.pago_ids.filtered(lambda p: not p.anulado)
            states = payments.mapped('recepcion_estado')
            if not states:
                rec.confirmacion_pagos = 'sin_pagos'
            elif 'disputa' in states:
                rec.confirmacion_pagos = 'disputa'
            elif all(s == 'confirmada' for s in states):
                rec.confirmacion_pagos = 'confirmada'
            elif 'confirmada' in states:
                rec.confirmacion_pagos = 'parcial'
            else:
                rec.confirmacion_pagos = 'pendiente'

    def action_preview_invoice(self):
        self.ensure_one()
        if not (self.env.user.has_group('logistica_transcash.group_transcash_contabilidad') or
                self.env.user.has_group('logistica_transcash.group_logistica_manager')) or self.company_id not in self.env.user.company_ids:
            raise AccessError(_('No puede consultar facturas de esta compañía.'))
        if not self.factura_archivo:
            raise UserError(_('No hay factura adjunta.'))
        return {'type': 'ir.actions.act_url',
                'url': '/transcash/finanzas/liquidaciones/%d/factura' % self.id,
                'target': 'new'}


    _sql_constraints = [
        ('transcash_liq_nombre_company_unique','unique(name, company_id)', 'El número de liquidación ya existe.'),
        ('transcash_factura_proveedor_unica','unique(proveedor_id, factura_numero)', 'El proveedor ya registró ese número de factura en otra liquidación.'),
    ]

    @api.depends('linea_ids.monto', 'pago_ids.monto', 'pago_ids.anulado', 'factura_numero', 'factura_total')
    def _compute_totales(self):
        for rec in self:
            rec.total_acordado = sum(rec.linea_ids.mapped('monto'))
            rec.total_pagado = sum(rec.pago_ids.filtered(lambda p: not p.anulado).mapped('monto'))
            base = rec.factura_total if rec.factura_numero else rec.total_acordado
            rec.saldo_pendiente = base - rec.total_pagado

    @api.depends('factura_subtotal', 'factura_impuestos')
    def _compute_factura_total(self):
        for rec in self:
            rec.factura_total = rec.factura_subtotal + rec.factura_impuestos

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su:
            raise AccessError(_('Las liquidaciones se crean únicamente desde el flujo autorizado.'))
        for vals in vals_list:
            if vals.get('name', 'Nuevo') == 'Nuevo':
                vals['name'] = self.env['ir.sequence'].sudo().next_by_code('transcash.pago.liquidacion') or 'Nuevo'
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.su:
            raise AccessError(_('Cambie la liquidación desde las acciones correspondientes a su rol.'))
        return super().write(vals)

    def unlink(self):
        raise UserError(_('Las liquidaciones se conservan para auditoría.'))

    @api.model
    def create_supplier_liquidation(self, ids):
        """Sólo portal proveedor. Bloqueo de filas + unique(embarque_id) en detalle."""
        user = self.env.user
        if not user.has_group('logistica_transcash.group_transcash_transportista'):
            raise AccessError(_('Necesita un usuario Portal de proveedor de transporte.'))
        try:
            ids = list(dict.fromkeys(int(i) for i in ids))
        except (ValueError, TypeError):
            raise UserError(_('Seleccione los viajes correctamente.'))
        if not ids or len(ids) > 100:
            raise UserError(_('Seleccione entre 1 y 100 viajes.'))
        self.env.cr.execute('SELECT id FROM transcash_embarque WHERE id = ANY(%s) ORDER BY id FOR UPDATE', (ids,))
        trips = self.env['transcash.embarque'].sudo().browse(ids).exists()
        if len(trips) != len(ids):
            raise UserError(_('Actualice la lista, uno de los embarques no existe.'))
        trips.invalidate_recordset(['estado_aprobacion', 'liquidacion_linea_id', 'valor_acordado'])
        first = trips[0]
        allowed = self.env['transcash.acceso.proveedor']._allowed_companies_for(user)
        if allowed is not None and any(t.company_id.id not in allowed for t in trips):
            raise AccessError(_('No está habilitado para liquidar viajes de esa compañía.'))
        supplier = user.partner_id.commercial_partner_id
        if first.proveedor_id.commercial_partner_id != supplier:
            raise AccessError(_('No puede liquidar embarques de otra empresa de transporte.'))
        for trip in trips:
            if (trip.proveedor_id.commercial_partner_id != supplier or
                    trip.proveedor_id != first.proveedor_id or trip.company_id != first.company_id or
                    trip.estado_aprobacion != 'aprobado' or trip.liquidacion_linea_id or
                    trip.valor_acordado <= 0):
                raise UserError(_('El embarque %s debe estar aprobado, no liquidado y pertenecer al mismo proveedor y compañía.') % trip.name)
        doc = self.sudo().create({'company_id': first.company_id.id, 'proveedor_id': first.proveedor_id.id})
        Line = self.env['transcash.pago.liquidacion.linea'].sudo()
        for trip in trips:
            Line.create({'liquidacion_id': doc.id, 'embarque_id': trip.id, 'monto': trip.valor_acordado})
        return doc

    def action_open_guides(self):
        self.ensure_one()
        if not (self.env.user.has_group('logistica_transcash.group_transcash_contabilidad') or
                self.env.user.has_group('logistica_transcash.group_logistica_manager')):
            raise AccessError(_('Solo Contabilidad y Logística pueden consultar estas guías.'))
        if self.company_id not in self.env.user.company_ids:
            raise AccessError(_('Compañía no autorizada.'))
        ids = self.linea_ids.mapped('embarque_id').ids
        return {'type':'ir.actions.act_window', 'name':_('Guías y evidencias de la liquidación'),
                'res_model':'transcash.guia', 'view_mode':'list,form', 'domain':[('embarque_id','in',ids)],
                'context':{'create':False, 'edit':False, 'delete':False}}

    def action_open_trips(self):
        """Open the shipments making up this invoice, never detached guides.

        This is a read-only navigation action; server/company authorization is
        checked before returning an action, and record rules apply afterwards.
        """
        self.ensure_one()
        user = self.env.user
        if (user.share or
                not (user.has_group('logistica_transcash.group_transcash_contabilidad') or
                     user.has_group('logistica_transcash.group_logistica_manager')) or
                self.company_id not in user.company_ids):
            raise AccessError(_('No tiene autorización para ver los viajes de esta liquidación.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Viajes de %s') % self.name,
            'res_model': 'transcash.embarque',
            'view_mode': 'kanban,list,form',
            'domain': [('id', 'in', self.linea_ids.mapped('embarque_id').ids)],
            'context': {'create': False, 'edit': False, 'delete': False},
        }

    def action_open_payments(self):
        """Read-only reconciliation drill-down with the receipt viewer."""
        self.ensure_one()
        user = self.env.user
        if (user.share or
                not (user.has_group('logistica_transcash.group_transcash_contabilidad') or
                     user.has_group('logistica_transcash.group_logistica_manager')) or
                self.company_id not in user.company_ids):
            raise AccessError(_('No tiene autorización para ver estos pagos.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Transferencias de %s') % self.name,
            'res_model': 'transcash.pago.registro',
            'view_mode': 'list,form',
            'domain': [('liquidacion_id', '=', self.id)],
            'context': {'create': False, 'edit': False, 'delete': False},
        }

    def _check_supplier(self):
        user = self.env.user
        if (not user.share or not user.has_group('logistica_transcash.group_transcash_transportista') or
                user.has_group('logistica_transcash.group_transcash_chofer') or
                user.has_group('logistica_transcash.group_transcash_cliente')):
            raise AccessError(_('Solo el proveedor Portal de transporte puede ejecutar esta acción.'))
        allowed = self.env['transcash.acceso.proveedor']._allowed_companies_for(user)
        for rec in self:
            if rec.proveedor_id.commercial_partner_id != user.partner_id.commercial_partner_id:
                raise AccessError(_('Liquidación de otro proveedor.'))
            if allowed is not None and rec.company_id.id not in allowed:
                raise AccessError(_('Liquidación de compañía sin acceso Portal vigente.'))

    def _check_accountant(self):
        user = self.env.user
        if user.share or not user.has_group('logistica_transcash.group_transcash_contabilidad'):
            raise AccessError(_('Solo Contabilidad interna puede revisar o registrar pagos.'))
        for rec in self:
            if rec.company_id not in user.company_ids:
                raise AccessError(_('La compañía no está autorizada para este usuario.'))

    def action_supplier_submit(self, numero, fecha, subtotal, impuestos, archivo, filename, nota=''):
        self.ensure_one()
        self._check_supplier()
        if self.estado not in ('borrador','observada') or self.pago_ids.filtered(lambda p: not p.anulado):
            raise UserError(_('Esta liquidación ya no admite cambios de factura.'))
        self.env.cr.execute('SELECT id FROM transcash_pago_liquidacion WHERE id = %s FOR UPDATE', (self.id,))
        self.invalidate_recordset(['estado', 'pago_ids'])
        if self.estado not in ('borrador','observada'):
            raise UserError(_('Esta liquidación ya fue enviada.'))
        numero = (numero or '').strip()[:120]
        if not numero or not fecha or not archivo or not filename:
            raise UserError(_('Número, fecha y archivo de factura son obligatorios.'))
        try:
            subtotal, impuestos = float(subtotal), float(impuestos)
        except (TypeError, ValueError):
            raise UserError(_('Importes de factura incorrectos.'))
        if not math.isfinite(subtotal) or not math.isfinite(impuestos) or subtotal <= 0 or impuestos < 0:
            raise UserError(_('Subtotal positivo e impuestos no negativos son obligatorios.'))
        try:
            raw = base64.b64decode(archivo, validate=True)
        except (TypeError, ValueError):
            raise UserError(_('El archivo no pudo interpretarse.'))
        if len(raw) > 15 * 1024 * 1024 or not _is_pdf_or_image(raw):
            raise UserError(_('Factura: adjunte PDF, JPG o PNG de máximo 15 MB.'))
        if self.env['transcash.pago.liquidacion'].sudo().search_count([
                ('id', '!=', self.id), ('proveedor_id', '=', self.proveedor_id.id),
                ('factura_numero', '=', numero)]):
            raise UserError(_('Esta factura ya consta en otra liquidación del mismo proveedor.'))
        # Importe de fletes acordados corresponde al subtotal, IVA separado.
        # En caso de diferencias Contabilidad puede observar pero no se permite validar.
        self.sudo().write({
            'factura_numero': numero, 'factura_fecha': fecha,
            'factura_subtotal': subtotal, 'factura_impuestos': impuestos,
            'factura_archivo': archivo, 'factura_nombre': filename[:180],
            'observacion_proveedor': (nota or '')[:3000], 'estado': 'revision',
            'observacion_contabilidad': False, 'revisado_por_id': False,
            'fecha_revision': False,
        })
        self.sudo().message_post(body=Markup('Factura <b>%s</b> presentada por %s. Subtotal de fletes: %s %s; impuestos: %s; total declarado: %s.') % (
            escape(numero), escape(self.env.user.display_name), escape('%.2f' % subtotal),
            escape(self.moneda_id.name or ''), escape('%.2f' % impuestos), escape('%.2f' % (subtotal + impuestos))))
        return True

    def action_accounting_approve(self):
        self._check_accountant()
        for rec in self:
            if rec.estado != 'revision' or not rec.factura_archivo or not rec.factura_numero:
                raise UserError(_('Debe existir una factura presentada pendiente de revisión.'))
            if float_compare(rec.factura_subtotal, rec.total_acordado, precision_rounding=rec.moneda_id.rounding) != 0:
                raise UserError(_('El subtotal de la factura debe coincidir con la suma de fletes acordados. Solicite corrección al proveedor.'))
            if any(trip.estado_aprobacion != 'aprobado' for trip in rec.linea_ids.mapped('embarque_id')):
                raise UserError(_('Uno de los embarques dejó de estar aprobado.'))
            rec.sudo().write({'estado': 'proceso_pago', 'revisado_por_id': self.env.uid,
                              'fecha_revision': fields.Datetime.now(), 'observacion_contabilidad': False})
            rec.sudo().message_post(body=Markup('Factura aprobada por Contabilidad: <b>%s</b>. Pasa a proceso de pago.') % escape(self.env.user.display_name))
        return True

    def action_open_observe_wizard(self):
        self.ensure_one()
        self._check_accountant()
        return {'type':'ir.actions.act_window','res_model':'transcash.observar.pago.wizard',
                'view_mode':'form','target':'new','name':_('Observar factura'),
                'context':{'default_liquidacion_id':self.id}}

    def action_accounting_observe(self, note):
        self.ensure_one()
        self._check_accountant()
        if self.estado != 'revision' or not (note or '').strip():
            raise UserError(_('Ingrese el motivo de observación de una factura en revisión.'))
        self.sudo().write({'estado':'observada', 'observacion_contabilidad':note.strip()[:3000],
                           'revisado_por_id':self.env.uid, 'fecha_revision':fields.Datetime.now()})
        self.sudo().message_post(body=Markup('Factura observada por Contabilidad (%s): %s') % (
            escape(self.env.user.display_name), escape(note.strip()[:3000])))
        return True

    def action_register_payment(self, amount, date, reference, method, receipt=False, filename=False):
        self.ensure_one()
        self._check_accountant()
        if self.estado not in ('proceso_pago','parcial'):
            raise UserError(_('Contabilidad debe aprobar la factura antes de registrar pagos.'))
        try:
            amount = float(amount)
        except (TypeError, ValueError):
            raise UserError(_('Importe de pago no válido.'))
        if not math.isfinite(amount) or amount <= 0 or not (reference or '').strip() or not date:
            raise UserError(_('Indique importe positivo, fecha y referencia bancaria.'))
        if fields.Date.to_date(date) > fields.Date.today():
            raise UserError(_('No registre pagos futuros como ya efectuados.'))
        if not receipt:
            raise UserError(_('Adjunte el comprobante del pago realizado.'))
        try:
            file_bytes = base64.b64decode(receipt, validate=True)
        except (ValueError, TypeError):
            raise UserError(_('Comprobante incorrecto.'))
        if len(file_bytes) > 15 * 1024 * 1024 or not _is_pdf_or_image(file_bytes):
            raise UserError(_('El comprobante debe ser PDF/JPG/PNG hasta 15 MB.'))
        # Protege dos abonos simultáneos que excedan el saldo.
        self.env.cr.execute('SELECT id FROM transcash_pago_liquidacion WHERE id = %s FOR UPDATE', (self.id,))
        self.invalidate_recordset(['pago_ids'])
        current_paid = sum(self.pago_ids.filtered(lambda p: not p.anulado).mapped('monto'))
        if float_compare(current_paid + amount, self.factura_total, precision_rounding=self.moneda_id.rounding) > 0:
            raise UserError(_('El pago excede el total de la factura pendiente.'))
        vals = {'liquidacion_id':self.id, 'monto': amount, 'fecha_pago':date,
                'referencia':reference.strip()[:130], 'medio':method or 'transferencia',
                'comprobante':receipt, 'comprobante_nombre':filename}
        self.env['transcash.pago.registro'].sudo().create(vals)
        new_paid = current_paid + amount
        state = 'pagada' if float_compare(new_paid, self.factura_total, precision_rounding=self.moneda_id.rounding) == 0 else 'parcial'
        self.sudo().write({'estado':state})
        self.sudo().message_post(body=Markup('Transferencia documentada por <b>%s</b>: %s %s, referencia %s, fecha %s. Estado contable: %s. Pendiente de confirmación del proveedor.') % (
            escape(self.env.user.display_name), escape('%.2f' % amount),
            escape(self.moneda_id.name or ''), escape(reference.strip()[:130]),
            escape(str(date)), escape(state)))
        return True

    def action_open_payment_wizard(self):
        self.ensure_one()
        self._check_accountant()
        return {'type':'ir.actions.act_window','res_model':'transcash.registrar.pago.wizard',
                'view_mode':'form','target':'new', 'name':_('Registrar pago del proveedor'),
                'context':{'default_liquidacion_id':self.id}}

    def action_print(self):
        self.ensure_one()
        # Se expone solo a usuarios internos con ACL; el portal tiene ruta validada.
        if not self.env.user.has_group('logistica_transcash.group_transcash_contabilidad') and not self.env.user.has_group('logistica_transcash.group_logistica_manager'):
            raise AccessError(_('Sin acceso al reporte de liquidación.'))
        if self.company_id not in self.env.user.company_ids:
            raise AccessError(_('No dispone de acceso a esta compañía.'))
        return self.env.ref('logistica_transcash.action_report_pago_liquidacion').report_action(self)


class TranscashLiquidacionLinea(models.Model):
    _name = 'transcash.pago.liquidacion.linea'
    _description = 'Embarque incluido en liquidación'
    _order = 'id'

    liquidacion_id = fields.Many2one('transcash.pago.liquidacion', required=True, ondelete='restrict', index=True)
    embarque_id = fields.Many2one('transcash.embarque', required=True, ondelete='restrict', index=True, readonly=True)
    monto = fields.Monetary('Flete aprobado', currency_field='moneda_id', required=True, readonly=True)
    moneda_id = fields.Many2one('res.currency', related='liquidacion_id.moneda_id', readonly=True)
    _sql_constraints = [('viaje_liquidado_una_vez', 'unique(embarque_id)', 'Este embarque ya figura en una liquidación.')]

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su:
            raise AccessError(_('Las líneas se crean solo desde el flujo autorizado.'))
        records = super().create(vals_list)
        for line in records:
            if (line.embarque_id.estado_aprobacion != 'aprobado' or line.embarque_id.legado_liquidacion_bloqueada or
                    line.embarque_id.proveedor_id != line.liquidacion_id.proveedor_id or
                    line.embarque_id.company_id != line.liquidacion_id.company_id or
                    float_compare(line.monto, line.embarque_id.valor_acordado, precision_rounding=line.moneda_id.rounding) != 0):
                raise ValidationError(_('Los viajes deben estar aprobados y el valor acordado debe ser inmutable.'))
        return records

    def write(self, vals):
        raise AccessError(_('No está permitido modificar líneas de una liquidación.'))

    def unlink(self):
        raise UserError(_('Las líneas no se eliminan por auditoría; solicite corrección a Administración.'))


class TranscashPagoRegistro(models.Model):
    _name = 'transcash.pago.registro'
    _description = 'Pago manual documentado a transportista'
    _order = 'fecha_pago desc, id desc'

    _sql_constraints = [('transcash_pago_referencia_unica', 'unique(liquidacion_id, referencia)',
                         'La referencia de pago ya fue registrada en esta liquidación.')]

    liquidacion_id = fields.Many2one('transcash.pago.liquidacion', required=True, ondelete='restrict', index=True)
    company_id = fields.Many2one('res.company', related='liquidacion_id.company_id', readonly=True)
    moneda_id = fields.Many2one('res.currency', related='liquidacion_id.moneda_id', readonly=True)
    monto = fields.Monetary('Monto transferido', currency_field='moneda_id', required=True, readonly=True)
    fecha_pago = fields.Date('Fecha pago', required=True, readonly=True)
    referencia = fields.Char('Referencia de transferencia', required=True, readonly=True)
    medio = fields.Selection([('transferencia','Transferencia'),('cheque','Cheque'),('otro','Otro')], default='transferencia', readonly=True)
    comprobante = fields.Binary('Comprobante de pago', attachment=True, readonly=True)
    comprobante_nombre = fields.Char('Archivo de pago', readonly=True)
    anulado = fields.Boolean('Anulado', default=False, readonly=True)
    motivo_anulacion = fields.Text('Motivo de anulación', readonly=True)
    recepcion_estado = fields.Selection([
        ('pendiente', 'Pendiente de confirmar por proveedor'),
        ('confirmada', 'Recepción confirmada'),
        ('disputa', 'Diferencia reportada'),
    ], default='pendiente', readonly=True, required=True, copy=False, string='Recepción por proveedor')
    recepcion_por_id = fields.Many2one('res.users', string='Confirmado / objetado por', readonly=True, copy=False)
    recepcion_fecha = fields.Datetime('Fecha de confirmación', readonly=True, copy=False)
    recepcion_nota = fields.Text('Detalle de confirmación o diferencia', readonly=True, copy=False)

    def action_supplier_receipt(self, decision, note=''):
        '''Acuse de recibo exclusivamente del proveedor; NUNCA cambia el pago contable.

        Contabilidad conserva autoridad sobre estado pagada y anulaciones. Una
        discrepancia sólo dispara alerta; no elimina la transferencia.
        '''
        self.ensure_one()
        user = self.env.user
        if (not user.share or not user.has_group('logistica_transcash.group_transcash_transportista') or
                user.has_group('logistica_transcash.group_transcash_chofer') or
                user.has_group('logistica_transcash.group_transcash_cliente') or
                self.liquidacion_id.proveedor_id.commercial_partner_id != user.partner_id.commercial_partner_id):
            raise AccessError(_('Solo el proveedor titular puede confirmar u objetar sus transferencias.'))
        allowed = self.env['transcash.acceso.proveedor']._allowed_companies_for(user)
        if allowed is not None and self.liquidacion_id.company_id.id not in allowed:
            raise AccessError(_('No tiene acceso vigente a los pagos de esta compañía.'))
        if decision not in ('confirmada', 'disputa'):
            raise UserError(_('Acción de confirmación incorrecta.'))
        note = (note or '').strip()[:2000]
        if decision == 'disputa' and len(note) < 10:
            raise UserError(_('Explique la diferencia encontrada (mínimo 10 caracteres).'))
        self.env.cr.execute('SELECT id FROM transcash_pago_registro WHERE id = %s FOR UPDATE', (self.id,))
        self.invalidate_recordset(['recepcion_estado', 'anulado'])
        if self.anulado or self.recepcion_estado != 'pendiente':
            raise UserError(_('Esta transferencia ya fue confirmada, objetada o anulada.'))
        self.sudo().write({'recepcion_estado':decision, 'recepcion_por_id':user.id,
                           'recepcion_fecha':fields.Datetime.now(), 'recepcion_nota':note})
        self.liquidacion_id.sudo().message_post(body=Markup('<b>%s</b> por el proveedor %s. Referencia: %s, importe %s %s. %s') % (
            escape('RECEPCIÓN CONFIRMADA' if decision == 'confirmada' else 'DISCREPANCIA DE PAGO'),
            escape(user.display_name), escape(self.referencia), escape('%.2f' % self.monto),
            escape(self.moneda_id.name or ''), escape(note)))
        return True

    def action_preview_receipt(self):
        self.ensure_one()
        if not (self.env.user.has_group('logistica_transcash.group_transcash_contabilidad') or
                self.env.user.has_group('logistica_transcash.group_logistica_manager')) or self.company_id not in self.env.user.company_ids:
            raise AccessError(_('No puede consultar estos comprobantes.'))
        if not self.comprobante:
            raise UserError(_('No existe comprobante.'))
        return {'type': 'ir.actions.act_url',
                'url': '/transcash/finanzas/pagos/%d/comprobante' % self.id, 'target': 'new'}

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su:
            raise AccessError(_('Los pagos solo se crean desde la aprobación de Contabilidad.'))
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.su:
            raise AccessError(_('No se pueden editar pagos; documente una anulación.'))
        return super().write(vals)

    def unlink(self):
        raise UserError(_('Los pagos no se eliminan por auditoría.'))

    def action_void(self, reason):
        self.ensure_one()
        rec = self.liquidacion_id
        rec._check_accountant()
        if self.anulado or not (reason or '').strip():
            raise UserError(_('Se necesita motivo para anular un registro de pago vigente.'))
        self.sudo().write({'anulado':True, 'motivo_anulacion':reason.strip()[:1000]})
        paid = sum(rec.pago_ids.filtered(lambda p: not p.anulado).mapped('monto'))
        rec.sudo().write({'estado': 'proceso_pago' if not paid else 'parcial'})
        rec.sudo().message_post(body=Markup('Transferencia %s ANULADA por Contabilidad (%s). Motivo: %s.') % (
            escape(self.referencia), escape(self.env.user.display_name), escape(reason.strip()[:1000])))
        return True


class TranscashPagoWizard(models.TransientModel):
    _name = 'transcash.registrar.pago.wizard'
    _description = 'Registrar transferencia al proveedor'

    liquidacion_id = fields.Many2one('transcash.pago.liquidacion', required=True, readonly=True)
    monto = fields.Monetary(required=True, currency_field='moneda_id')
    moneda_id = fields.Many2one('res.currency', related='liquidacion_id.moneda_id')
    fecha_pago = fields.Date(required=True, default=fields.Date.today)
    referencia = fields.Char(required=True)
    medio = fields.Selection([('transferencia','Transferencia'),('cheque','Cheque'),('otro','Otro')], default='transferencia', required=True)
    comprobante = fields.Binary('Comprobante (PDF/imagen)', attachment=True)
    comprobante_nombre = fields.Char('Nombre archivo')

    def action_confirm(self):
        self.ensure_one()
        self.liquidacion_id.action_register_payment(self.monto,self.fecha_pago,self.referencia,self.medio,
                                                     self.comprobante,self.comprobante_nombre)
        return {'type':'ir.actions.act_window_close'}


class TranscashObserveWizard(models.TransientModel):
    _name = 'transcash.observar.pago.wizard'
    _description = 'Observar factura del proveedor'

    liquidacion_id = fields.Many2one('transcash.pago.liquidacion', required=True, readonly=True)
    observacion = fields.Text(required=True)

    def action_confirm(self):
        self.ensure_one()
        self.liquidacion_id.action_accounting_observe(self.observacion)
        return {'type':'ir.actions.act_window_close'}
