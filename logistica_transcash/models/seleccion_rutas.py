"""V5.15: selector de guías, reasignación explícita y diagnóstico de bloqueo.

Evita depender de la búsqueda many2many_tags del formulario de Odoo y
permite diagnosticar rápidamente una lista de guías vacía.
"""
from odoo import api, fields, models, _
from odoo.exceptions import UserError, AccessError


MAX_GUIAS_EN_SELECTOR = 150


class SeleccionarGuiasRutaWizard(models.TransientModel):
    _name = 'transcash.seleccionar.guias.ruta.wizard'
    _description = 'Seleccionar guías para hoja de ruta'

    ruta_id = fields.Many2one('transcash.hoja.ruta', required=True, readonly=True)
    company_id = fields.Many2one('res.company', related='ruta_id.company_id', readonly=True)
    chofer_usuario_id = fields.Many2one('res.users', related='ruta_id.chofer_usuario_id', readonly=True)
    proveedor_id = fields.Many2one('res.partner', related='ruta_id.proveedor_id', readonly=True)
    chofer_inicial_id = fields.Many2one('res.users', readonly=True)
    proveedor_inicial_id = fields.Many2one('res.partner', readonly=True)
    destino_inicial_id = fields.Many2one('transcash.destino', readonly=True)
    permitir_reasignar = fields.Boolean('Confirmo cambiar el chofer y/o transportista según esta hoja de ruta')
    cantidad_reasignacion = fields.Integer('Guías que requieren revisión', readonly=True)
    buscar_numero = fields.Char('Buscar por número de guía o documento')
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
    def abrir_para_ruta(self, ruta, buscar_numero=False, ids_ya_marcados=None,
                        permitir_reasignar=None):
        ruta.ensure_one()
        ruta._check_operator()
        if ruta.company_id not in self.env.user.company_ids:
            raise AccessError(_('No puede modificar rutas de otra compañía.'))
        if ruta.state != 'borrador':
            raise UserError(_('Solo puede agregar guías cuando la hoja de ruta está en Borrador.'))
        if not ruta.destino_id or not ruta.chofer_usuario_id or not ruta.proveedor_id:
            raise UserError(_('Antes de agregar guías, indique destino, chofer y empresa transportista.'))
        Guia = self.env['transcash.guia']
        query = (buscar_numero or '').strip()
        base_domain = ruta._domain_guias_elegibles(validar_filtros=not bool(query))
        if query:
            from odoo.osv import expression
            filtro = ['|', ('name', 'ilike', query), ('numero_documento', 'ilike', query)]
            base_domain = expression.AND([base_domain, filtro])
        candidatas = Guia.search(base_domain, order='create_date desc,id desc',
                                 limit=MAX_GUIAS_EN_SELECTOR + 1)
        selected_before = ruta.seleccion_guia_ids
        # Incluir las seleccionadas aun si se busca otra guía distinta.
        if ids_ya_marcados is not None:
            selected_before = Guia.browse(ids_ya_marcados).exists()
        # Diagnóstico: incluir guías fuera del destino únicamente al buscar un
        # número concreto. No se debe mezclar una guía de otro destino por error.
        if query and len(candidatas) < MAX_GUIAS_EN_SELECTOR:
            otras = Guia.search([
                ('company_id', '=', ruta.company_id.id),
                '|', ('name', 'ilike', query), ('numero_documento', 'ilike', query)],
                limit=30)
            candidatas |= otras
        candidates = (selected_before | candidatas[:MAX_GUIAS_EN_SELECTOR]).sorted(
            key=lambda g: (not ruta._es_guia_elegible(g, permitir_reasignacion=True),
                           bool(ruta._motivos_reasignacion(g)), g.name or ''))
        reassign_count = len(candidates.filtered(lambda g:
            ruta._es_guia_elegible(g, permitir_reasignacion=True) and ruta._motivos_reasignacion(g)))
        visible_disponibles = len(candidates.filtered(lambda g:
            ruta._es_guia_elegible(g, permitir_reasignacion=True)))
        aviso = False
        if len(candidatas) > MAX_GUIAS_EN_SELECTOR:
            aviso = _('Hay más de %s guías pendientes. Busque por número de guía o documento para encontrarlas.') % MAX_GUIAS_EN_SELECTOR
        elif not visible_disponibles:
            aviso = _('No hay guías habilitadas. Compruebe el resultado del filtro en cada fila, '
                      'el destino de la ruta y que la guía no esté utilizada por otro embarque.')
        wizard = self.create({
            'ruta_id': ruta.id,
            'chofer_inicial_id': ruta.chofer_usuario_id.id,
            'proveedor_inicial_id': ruta.proveedor_id.id,
            'destino_inicial_id': ruta.destino_id.id,
            'total_disponibles': ruta.guias_disponibles,
            'guias_pendientes_destino': ruta.guias_pendientes_destino,
            'cantidad_reasignacion': reassign_count,
            'buscar_numero': query,
            'permitir_reasignar': ruta.reasignacion_autorizada if permitir_reasignar is None else permitir_reasignar,
            'seleccion_inicial_ids': [(6, 0, ruta.seleccion_guia_ids.ids)],
            'linea_ids': [(0, 0, {
                'guia_id': guia.id,
                'seleccionada': guia.id in selected_before.ids,
                'disponible': ruta._es_guia_elegible(guia, permitir_reasignacion=True),
                'requiere_reasignacion': bool(ruta._motivos_reasignacion(guia)) and
                    ruta._es_guia_elegible(guia, permitir_reasignacion=True),
                'motivo': self._motivo_guia(ruta, guia),
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
        if guia.company_id != ruta.company_id:
            return _('Bloqueada: otra compañía')
        if guia.state != 'registrada':
            return _('Bloqueada: estado %s (debe estar Registrada)') % dict(guia._fields['state'].selection).get(guia.state, guia.state)
        if guia.hoja_ruta_id or guia.embarque_id:
            return _('Bloqueada: ya pertenece a ruta o embarque')
        if not ruta._coincide_destino(guia):
            return _('Bloqueada: destino diferente o sin destino homologado')
        motivos = ruta._motivos_reasignacion(guia)
        if motivos:
            return _('Requiere autorización: %s') % ', '.join(motivos)
        return _('Disponible para agregar')

    def action_buscar(self):
        """Refrescar candidatos sin perder las casillas ya marcadas en el diálogo."""
        self.ensure_one()
        ids = self.linea_ids.filtered('seleccionada').mapped('guia_id').ids
        return self.abrir_para_ruta(self.ruta_id, self.buscar_numero, ids, self.permitir_reasignar)

    def action_aplicar(self):
        self.ensure_one()
        ruta = self.ruta_id
        ruta._check_operator()
        if ruta.company_id not in self.env.user.company_ids:
            raise AccessError(_('No puede modificar esta ruta.'))
        if ruta.state != 'borrador':
            raise UserError(_('La ruta ya fue confirmada; no puede modificar sus guías.'))
        if (ruta.chofer_usuario_id != self.chofer_inicial_id or
                ruta.proveedor_id != self.proveedor_inicial_id or
                ruta.destino_id != self.destino_inicial_id):
            raise UserError(_('Cambió el chofer, transportista o destino mientras el selector estaba abierto. Vuelva a abrirlo.'))
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
                if not ruta._es_guia_elegible(guia, permitir_reasignacion=True):
                    raise UserError(_('La guía %(guia)s no se puede agregar: %(motivo)s. '
                                      'Actualice el selector.') %
                                    {'guia': guia.name, 'motivo': self._motivo_guia(ruta, guia)})
            if not self.permitir_reasignar:
                diferentes = selected.filtered(lambda g: ruta._motivos_reasignacion(g))
                if diferentes:
                    raise UserError(_('La guía %s tiene otro chofer o transportista. '
                                      'Active la autorización de reasignación antes de guardar.') % diferentes[0].name)
        # Únicamente el asistente autorizado establece esta decisión, no la vista.
        ruta.sudo().write({
            'seleccion_guia_ids': [(6, 0, selected.ids)],
            'reasignacion_autorizada': bool(self.permitir_reasignar),
            'reasignacion_autorizada_por_id': self.env.user.id if self.permitir_reasignar else False,
        })
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
    requiere_reasignacion = fields.Boolean('Requiere reasignación', readonly=True)
    motivo = fields.Char('Resultado del filtro', readonly=True)
