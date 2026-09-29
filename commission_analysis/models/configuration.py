from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class CommissionOperator(models.Model):
    _name = 'commission.operator'
    _description = 'Operador'
    _order = 'name'

    name = fields.Char(required=True)
    code = fields.Char(required=True)
    icc_match_length = fields.Integer(
        string='Longitud clave ICC',
        default=18,
        required=True,
        help='Cantidad de dígitos que se usarán para normalizar y cruzar el ICC/SIMCARD. '
             'Para los archivos analizados de Claro/Telecity se usan los primeros 18 dígitos.',
    )
    maturity_days = fields.Integer(
        string='Días para SIM madura',
        default=90,
        required=True,
        help='Antigüedad mínima desde la compra para considerar una SIM madura en los KPI '
             'de improductividad y capital sin recuperar. Es un parámetro analítico y no '
             'modifica las reglas contractuales de comisión.',
    )
    roi_cost_basis = fields.Selection(
        [
            ('cost', 'Costo fuente'),
            ('net', 'Costo - descuento'),
            ('gross', 'Costo - descuento + impuesto'),
        ],
        string='Base de costo para ROI',
        default='cost',
        required=True,
        help='Define qué importe de la compra se considera inversión para margen y ROI. '
             'El archivo fuente conserva siempre costo, descuento e impuesto por separado.',
    )
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('code_uniq', 'unique(code)', 'El código del operador debe ser único.'),
    ]

    @api.constrains('icc_match_length')
    def _check_icc_match_length(self):
        for rec in self:
            if rec.icc_match_length <= 0 or rec.icc_match_length > 32:
                raise ValidationError(_('La longitud de la clave ICC debe estar entre 1 y 32.'))

    @api.constrains('maturity_days')
    def _check_maturity_days(self):
        for rec in self:
            if rec.maturity_days <= 0 or rec.maturity_days > 730:
                raise ValidationError(_('Los días para SIM madura deben estar entre 1 y 730.'))

    def write(self, vals):
        if 'icc_match_length' in vals:
            for rec in self:
                new_length = vals.get('icc_match_length')
                if new_length != rec.icc_match_length:
                    has_data = (
                        bool(self.env['commission.sim'].search([('operator_id', '=', rec.id)], limit=1))
                        or bool(self.env['commission.settlement.batch'].search([('operator_id', '=', rec.id)], limit=1))
                        or bool(self.env['commission.purchase.batch'].search([('operator_id', '=', rec.id)], limit=1))
                    )
                    if has_data:
                        raise UserError(_(
                            'No se puede cambiar la longitud de la clave ICC después de cargar datos. '
                            'Esto alteraría los cruces históricos. Cree un operador nuevo o realice una migración controlada.'
                        ))
        return super().write(vals)

    def _roi_cost_value(self, cost=0.0, discount=0.0, tax=0.0):
        self.ensure_one()
        cost = cost or 0.0
        discount = discount or 0.0
        tax = tax or 0.0
        if self.roi_cost_basis == 'gross':
            return cost - discount + tax
        if self.roi_cost_basis == 'net':
            return cost - discount
        return cost


class CommissionRegion(models.Model):
    _name = 'commission.region'
    _description = 'Región de Comisión'
    _order = 'name'

    name = fields.Char(required=True)
    code = fields.Char()
    active = fields.Boolean(default=True)


class CommissionZone(models.Model):
    _name = 'commission.zone'
    _description = 'Zona de Comisión'
    _order = 'region_id, name'

    name = fields.Char(required=True)
    code = fields.Char()
    region_id = fields.Many2one('commission.region', required=True, ondelete='restrict')
    active = fields.Boolean(default=True)


class CommissionScheme(models.Model):
    _name = 'commission.scheme'
    _description = 'Esquema de Comisión'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_from desc, id desc'

    name = fields.Char(required=True, tracking=True)
    operator_id = fields.Many2one('commission.operator', required=True, tracking=True)
    product = fields.Char(required=True, default='Prepago')
    product_match_pattern = fields.Char(
        string='Patrón producto liquidación',
        help='Texto que debe aparecer en el producto reportado por el operador. '
             'Déjelo vacío o use * para aplicar a cualquier producto.',
    )
    date_from = fields.Date(required=True, tracking=True)
    date_to = fields.Date(tracking=True)
    state = fields.Selection(
        [('draft', 'Borrador'), ('active', 'Activo'), ('closed', 'Cerrado')],
        default='draft', tracking=True,
    )
    line_ids = fields.One2many('commission.scheme.line', 'scheme_id', copy=True)
    notes = fields.Text()

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for rec in self:
            if rec.date_to and rec.date_from and rec.date_to < rec.date_from:
                raise ValidationError(_('La fecha hasta no puede ser anterior a la fecha desde.'))

    @api.constrains('operator_id', 'product', 'date_from', 'date_to', 'state')
    def _check_active_overlap(self):
        for rec in self:
            if rec.state in ('active', 'closed'):
                if rec.state == 'closed' and not rec.date_to:
                    raise ValidationError(_('Una versión cerrada debe tener Fecha hasta.'))
                if self.search_count(rec._overlap_domain()):
                    raise ValidationError(_(
                        'Existe otra versión activa/cerrada del mismo operador y producto con vigencia superpuesta.'
                    ))

    def write(self, vals):
        protected = {'operator_id', 'product', 'product_match_pattern', 'date_from'}
        for rec in self:
            if protected.intersection(vals) and rec.state != 'draft':
                raise UserError(_(
                    'Una versión activa o cerrada no puede cambiar operador, producto, patrón o fecha inicial. '
                    'Duplique el esquema para crear una nueva versión.'
                ))
            if 'date_to' in vals and rec.state == 'closed':
                raise UserError(_(
                    'La vigencia de una versión cerrada está bloqueada. Duplique el esquema si necesita una corrección.'
                ))
        return super().write(vals)

    def unlink(self):
        if self.filtered(lambda r: r.state != 'draft'):
            raise UserError(_(
                'No se puede eliminar una versión activa o cerrada porque forma parte del historial de auditoría.'
            ))
        return super().unlink()

    def _overlap_domain(self):
        self.ensure_one()
        domain = [
            ('id', '!=', self.id),
            ('operator_id', '=', self.operator_id.id),
            ('product', '=', self.product),
            ('state', 'in', ('active', 'closed')),
            '|', ('date_to', '=', False), ('date_to', '>=', self.date_from),
        ]
        if self.date_to:
            domain += [('date_from', '<=', self.date_to)]
        return domain

    def _validate_rule_ranges(self):
        """Evita reglas ambiguas que podrían producir cálculos distintos por prioridad.

        Solo se consideran conflictivas las reglas que comparten el mismo patrón efectivo
        de concepto y la misma base de cálculo. Patrones diferentes pueden solaparse porque
        representan conceptos distintos.
        """
        for scheme in self:
            active_rules = scheme.line_ids.filtered('active')
            if not active_rules:
                raise UserError(_('No se puede activar un esquema sin reglas activas.'))
            groups = {}
            for rule in active_rules:
                if not rule.no_upper_limit and rule.max_amount == rule.min_amount and not (rule.min_inclusive and rule.max_inclusive):
                    raise UserError(_(
                        'La regla %s tiene un rango vacío: cuando mínimo y máximo son iguales, ambos límites deben ser inclusivos.'
                    ) % (rule.concept_name or rule.concept_code))
                pattern = (rule.match_pattern or rule.concept_code or rule.concept_name or '*').strip().casefold()
                key = (pattern, rule.base_field)
                groups.setdefault(key, []).append(rule)
            for (pattern, base_field), rules in groups.items():
                ordered = sorted(rules, key=lambda r: (r.min_amount, r.priority, r.id))
                previous = None
                for rule in ordered:
                    if previous:
                        if previous.no_upper_limit:
                            raise UserError(_(
                                'El esquema tiene rangos superpuestos para el patrón "%s". '
                                'Una regla sin límite superior no puede tener otra regla posterior.'
                            ) % pattern)
                        same_boundary = rule.min_amount == previous.max_amount
                        overlaps = (
                            rule.min_amount < previous.max_amount
                            or (same_boundary and previous.max_inclusive and rule.min_inclusive)
                        )
                        if overlaps:
                            raise UserError(_(
                                'El esquema tiene rangos superpuestos para el patrón "%s" y base "%s": '
                                '%s-%s se cruza con %s-%s.'
                            ) % (
                                pattern, base_field, previous.min_amount, previous.max_amount,
                                rule.min_amount, '∞' if rule.no_upper_limit else rule.max_amount,
                            ))
                    previous = rule
        return True

    def action_activate(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Solo una versión en borrador puede activarse.'))
        self._validate_rule_ranges()
        for rec in self:
            if self.search_count(rec._overlap_domain()):
                raise UserError(_(
                    'Ya existe un esquema activo para el mismo operador/producto con vigencia superpuesta. '
                    'Cierre o limite la vigencia anterior antes de activar esta versión.'
                ))
        self.write({'state': 'active'})
        return True

    def action_close(self):
        for rec in self:
            if not rec.date_to:
                raise UserError(_(
                    'Antes de cerrar una versión indique Fecha hasta. '
                    'Una versión cerrada se conserva para recalcular períodos históricos.'
                ))
        self.write({'state': 'closed'})
        return True

    def action_duplicate_version(self):
        self.ensure_one()
        today = fields.Date.today()
        new = self.copy({
            'name': _('%s (Nueva versión)') % self.name,
            'state': 'draft',
            'date_from': today,
            'date_to': False,
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': new.id,
            'view_mode': 'form',
            'target': 'current',
        }


class CommissionSchemeLine(models.Model):
    _name = 'commission.scheme.line'
    _description = 'Regla de Comisión'
    _order = 'priority, concept_code, evaluation_day, min_amount, id'

    scheme_id = fields.Many2one('commission.scheme', required=True, ondelete='cascade')
    concept_code = fields.Char(required=True, help='Código/identificador del concepto de Claro o interno.')
    concept_name = fields.Char(required=True)
    match_pattern = fields.Char(
        help='Texto que debe aparecer en el concepto de la liquidación. Use * para regla genérica.'
    )
    evaluation_day = fields.Integer(help='Día de evaluación de referencia, p.ej. 60 o 90. La coincidencia ejecutable se determina por patrón de concepto, producto, vigencia y rango.')
    calculation_type = fields.Selection(
        [('percentage', 'Porcentaje'), ('fixed', 'Valor fijo')],
        default='percentage', required=True,
    )
    base_field = fields.Selection(
        [
            ('consumption', 'Consumo evaluado'),
            ('consumptions', 'Consumos'),
            ('recharges', 'Recargas'),
            ('tariff', 'Tarifa básica'),
        ],
        default='consumption', required=True,
    )
    min_amount = fields.Monetary(default=0)
    min_inclusive = fields.Boolean(string='Incluir mínimo', default=True)
    max_amount = fields.Monetary(help='Límite superior. Para infinito marque explícitamente Sin límite superior.')
    max_inclusive = fields.Boolean(string='Incluir máximo', default=True)
    no_upper_limit = fields.Boolean(string='Sin límite superior')
    percentage = fields.Float(digits=(16, 4))
    fixed_amount = fields.Monetary()
    currency_id = fields.Many2one(
        'res.currency', default=lambda self: self.env.company.currency_id.id, required=True
    )
    active = fields.Boolean(default=True)
    priority = fields.Integer(default=10)

    @api.model_create_multi
    def create(self, vals_list):
        scheme_ids = {vals.get('scheme_id') for vals in vals_list if vals.get('scheme_id')}
        locked = self.env['commission.scheme'].browse(scheme_ids).filtered(lambda s: s.state != 'draft')
        if locked:
            raise UserError(_('Las reglas solo pueden agregarse a esquemas en borrador.'))
        return super().create(vals_list)

    def write(self, vals):
        if self.filtered(lambda r: r.scheme_id.state != 'draft'):
            raise UserError(_(
                'Las reglas de una versión activa o cerrada están bloqueadas. '
                'Use Duplicar esquema para modificar parámetros.'
            ))
        return super().write(vals)

    def unlink(self):
        if self.filtered(lambda r: r.scheme_id.state != 'draft'):
            raise UserError(_(
                'No se pueden eliminar reglas de una versión activa o cerrada. '
                'Use Duplicar esquema para una nueva versión.'
            ))
        return super().unlink()

    @api.constrains(
        'min_amount', 'max_amount', 'no_upper_limit', 'percentage', 'fixed_amount', 'calculation_type'
    )
    def _check_values(self):
        for rec in self:
            if not rec.no_upper_limit and rec.max_amount < rec.min_amount:
                raise ValidationError(_('El límite máximo no puede ser menor al mínimo.'))
            if rec.percentage < 0:
                raise ValidationError(_('El porcentaje no puede ser negativo.'))
            if rec.fixed_amount < 0:
                raise ValidationError(_('El valor fijo no puede ser negativo.'))


class CommissionWarehouseMapping(models.Model):
    _name = 'commission.warehouse.mapping'
    _description = 'Mapeo Bodega a Región/Zona'
    _order = 'warehouse_name'

    warehouse_code = fields.Char(index=True)
    warehouse_name = fields.Char(required=True, index=True)
    region_id = fields.Many2one('commission.region', required=True, ondelete='restrict')
    zone_id = fields.Many2one(
        'commission.zone', required=True, ondelete='restrict', domain="[('region_id', '=', region_id)]"
    )
    active = fields.Boolean(default=True)

    @api.constrains('region_id', 'zone_id')
    def _check_zone_region(self):
        for rec in self:
            if rec.zone_id and rec.region_id and rec.zone_id.region_id != rec.region_id:
                raise ValidationError(_('La zona seleccionada no pertenece a la región indicada.'))
