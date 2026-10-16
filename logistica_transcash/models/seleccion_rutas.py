"""V5.14: selector explícito de guías para una hoja de ruta en borrador.

Evita depender de la búsqueda many2many_tags del formulario de Odoo y
permite diagnosticar rápidamente una lista de guías vacía.
"""
from odoo import api, fields, models, _
from odoo.exceptions import UserError, AccessError


MAX_GUIAS_EN_SELECTOR = 500


class SeleccionarGuiasRutaWizard(models.TransientModel):
    _name = 'transcash.seleccionar.guias.ruta.wizard'
    _description = 'Seleccionar guías para hoja de ruta'

    ruta_id = fields.Many2one('transcash.hoja.ruta', required=True, readonly=True)
    company_id = fields.Many2one('res.company', related='ruta_id.company_id', readonly=True)
    chofer_usuario_id = fields.Many2one('res.users', related='ruta_id.chofer_usuario_id', readonly=True)
    proveedor_id = fields.Many2one('res.partner', related='ruta_id.proveedor_id', readonly=True)
    destino_id = fields.Many2one('transcash.destino', related='ruta_id.destino_id', readonly=True)
    linea_ids = fields.One2many('transcash.seleccionar.guias.ruta.linea', 'wizard_id',
                                string='Guías para marcar')
    seleccion_inicial_ids = fields.Many2many('transcash.guia',
        'transcash_ruta_wizard_inicial_rel', 'wizard_id', 'guia_id',
        string='Selección inicial', readonly=True)
    total_disponibles = fields.Integer(readonly=True)
    guias_pendientes_destino = fields.Integer(readonly=True)
    aviso = fields.Text(readonly=True)

    @api.model
    def abrir_para_ruta(self, ruta):
        ruta.ensure_one()
        ruta._check_operator()
        if ruta.company_id not in self.env.user.company_ids:
            raise AccessError(_('No puede modificar rutas de otra compañía.'))
        if ruta.state != 'borrador':
            raise UserError(_('Solo puede agregar guías cuando la hoja de ruta está en Borrador.'))
        if not ruta.destino_id or not ruta.chofer_usuario_id or not ruta.proveedor_id:
            raise UserError(_('Antes de agregar guías, indique destino, chofer y empresa transportista.'))
        available = self.env['transcash.guia'].search(ruta._domain_guias_elegibles(),
                                                      order='name asc', limit=MAX_GUIAS_EN_SELECTOR + 1)
        selected_before = ruta.seleccion_guia_ids
        # Incluir una muestra de guías bloqueadas, con el motivo claro, cuando
        # aparentemente no hay nada seleccionable (o algunas no coinciden).
        Guia = self.env['transcash.guia']
        otras = Guia.search(ruta._domain_guias_elegibles(validar_filtros=False), limit=80)
        if len(otras) < 50:
            otras |= Guia.search([('company_id', '=', ruta.company_id.id),
                                   ('state', '=', 'registrada'),
                                   ('embarque_id', '=', False),
                                   ('hoja_ruta_id', '=', False)], limit=80)
        # No perder una guía ya seleccionada al reabrir el asistente.
        selected_ids = set(selected_before.ids)
        candidates = (selected_before | available[:MAX_GUIAS_EN_SELECTOR] | otras).sorted('name')
        # Las coincidencias primero; el resto aparece para diagnóstico.
        candidates = candidates.sorted(key=lambda g: (not ruta._es_guia_elegible(g), g.name or ''))
        aviso = False
        total = ruta.guias_disponibles
        if total > MAX_GUIAS_EN_SELECTOR:
            aviso = _('Se muestran como máximo %s guías en el selector. Si necesita otras, '\
                      'confirme esta selección y vuelva a abrirlo.') % MAX_GUIAS_EN_SELECTOR
        elif not available and not selected_before:
            aviso = _('No hay guías para seleccionar. Revise que estén en estado Registrada, '\
                      'tengan el mismo destino, chofer y transportista (o estén sin asignar), '\
                      'y no pertenezcan a otra ruta o embarque. Guías pendientes para el destino: %s.') % ruta.guias_pendientes_destino
        elif selected_before and len(selected_before) > MAX_GUIAS_EN_SELECTOR:
            aviso = _('Esta ruta ya contiene más de %s guías. Revise el volumen antes de añadir otras.') % MAX_GUIAS_EN_SELECTOR
        wizard = self.create({
            'ruta_id': ruta.id,
            'total_disponibles': total,
            'guias_pendientes_destino': ruta.guias_pendientes_destino,
            'seleccion_inicial_ids': [(6, 0, selected_before.ids)],
            'linea_ids': [(0, 0, {
                'guia_id': guia.id,
                'seleccionada': guia.id in selected_ids,
                'disponible': guia.id in selected_ids or ruta._es_guia_elegible(guia),
                'motivo': (self._motivo_guia(ruta, guia) + (_(' — desmarque esta guía') if guia.id in selected_ids and not ruta._es_guia_elegible(guia) else '')),
            }) for guia in candidates],
            'aviso': aviso,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _('Agregar guías a %s') % ruta.name,
            'res_model': self._name,
            'view_mode': 'form',
            'res_id': wizard.id,
            'target': 'new',
        }

    @api.model
    def _motivo_guia(self, ruta, guia):
        if ruta._es_guia_elegible(guia):
            return _('Disponible')
        if guia.company_id != ruta.company_id:
            return _('Otra compañía')
        if guia.state != 'registrada':
            return _('Guía no está registrada')
        if guia.hoja_ruta_id or guia.embarque_id:
            return _('Ya asignada a ruta o embarque')
        if (guia.destino_id != ruta.destino_id if guia.destino_id else
                (guia.destino_codigo or '').strip().upper() != ruta.destino_id.codigo):
            return _('Otro destino')
        if guia.chofer_usuario_id and guia.chofer_usuario_id != ruta.chofer_usuario_id:
            return _('Otro chofer')
        if guia.proveedor_id and guia.proveedor_id != ruta.proveedor_id:
            return _('Otra empresa transportista')
        return _('No disponible')

    def action_aplicar(self):
        self.ensure_one()
        ruta = self.ruta_id
        ruta._check_operator()
        if ruta.company_id not in self.env.user.company_ids:
            raise AccessError(_('No puede modificar esta ruta.'))
        if ruta.state != 'borrador':
            raise UserError(_('La ruta ya fue confirmada; no puede modificar sus guías.'))
        # Bloquear la fila de la ruta para evitar sobrescrituras entre dos operadores.
        self.env.cr.execute('SELECT id FROM transcash_hoja_ruta WHERE id = %s FOR UPDATE', (ruta.id,))
        ruta.invalidate_recordset(['seleccion_guia_ids', 'state'])
        if set(ruta.seleccion_guia_ids.ids) != set(self.seleccion_inicial_ids.ids):
            raise UserError(_('Otro operador cambió las guías de esta ruta. Cierre el selector y vuelva a abrirlo.'))
        selected = self.linea_ids.filtered('seleccionada').mapped('guia_id')
        if len(selected) != len(self.linea_ids.filtered('seleccionada')):
            raise UserError(_('La selección contiene guías repetidas. Vuelva a abrir el selector.'))
        if selected:
            # No bloqueamos filas de guías aquí: siguen siendo una selección
            # en borrador. Confirmar ruta las bloqueará y validará de nuevo,
            # evitando interbloqueos con la acción de confirmación.
            selected.invalidate_recordset(['state', 'embarque_id', 'hoja_ruta_id', 'chofer_usuario_id',
                                           'proveedor_id', 'destino_id', 'destino_codigo', 'company_id'])
            for guia in selected:
                if not ruta._es_guia_elegible(guia):
                    raise UserError(_('La guía %s dejó de estar disponible o tiene otro chofer, '\
                                      'empresa de transporte o destino. Actualice la selección.') % guia.name)
        ruta.write({'seleccion_guia_ids': [(6, 0, selected.ids)]})
        return {
            'type': 'ir.actions.act_window',
            'name': _('Hoja de ruta'),
            'res_model': 'transcash.hoja.ruta',
            'view_mode': 'form',
            'res_id': ruta.id,
            'target': 'current',
        }


class SeleccionarGuiasRutaLinea(models.TransientModel):
    _name = 'transcash.seleccionar.guias.ruta.linea'
    _description = 'Guía elegible para seleccionar en ruta'
    _order = 'id'

    wizard_id = fields.Many2one('transcash.seleccionar.guias.ruta.wizard',
                                required=True, ondelete='cascade')
    guia_id = fields.Many2one('transcash.guia', required=True, readonly=True)
    seleccionada = fields.Boolean(string='Agregar')
    numero_documento = fields.Char(related='guia_id.numero_documento', readonly=True)
    destinatario_id = fields.Many2one(related='guia_id.destinatario_id', readonly=True)
    chofer_usuario_id = fields.Many2one(related='guia_id.chofer_usuario_id', readonly=True)
    proveedor_id = fields.Many2one(related='guia_id.proveedor_id', readonly=True)
    peso_kg = fields.Float(related='guia_id.peso_kg', readonly=True)
    disponible = fields.Boolean('Disponible', readonly=True)
    motivo = fields.Char('Resultado del filtro', readonly=True)
