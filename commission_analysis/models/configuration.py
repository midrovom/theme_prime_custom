from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class CommissionOperator(models.Model):
    _name = 'commission.operator'
    _description = 'Operador'
    _order = 'name'
    name = fields.Char(required=True)
    code = fields.Char(required=True)
    active = fields.Boolean(default=True)
    _sql_constraints = [('code_uniq','unique(code)','El código del operador debe ser único.')]

class CommissionRegion(models.Model):
    _name = 'commission.region'
    _description = 'Región de Comisión'
    name = fields.Char(required=True)
    code = fields.Char()
    active = fields.Boolean(default=True)

class CommissionZone(models.Model):
    _name = 'commission.zone'
    _description = 'Zona de Comisión'
    name = fields.Char(required=True)
    code = fields.Char()
    region_id = fields.Many2one('commission.region', required=True, ondelete='restrict')
    active = fields.Boolean(default=True)

class CommissionScheme(models.Model):
    _name = 'commission.scheme'
    _description = 'Esquema de Comisión'
    _inherit = ['mail.thread','mail.activity.mixin']
    _order = 'date_from desc, id desc'
    name = fields.Char(required=True, tracking=True)
    operator_id = fields.Many2one('commission.operator', required=True, tracking=True)
    product = fields.Char(required=True, default='Prepago')
    date_from = fields.Date(required=True, tracking=True)
    date_to = fields.Date(tracking=True)
    state = fields.Selection([('draft','Borrador'),('active','Activo'),('closed','Cerrado')], default='draft', tracking=True)
    line_ids = fields.One2many('commission.scheme.line','scheme_id', copy=True)
    notes = fields.Text()

    def action_activate(self): self.write({'state':'active'})
    def action_close(self): self.write({'state':'closed'})
    def action_duplicate_version(self):
        self.ensure_one()
        new = self.copy({'name': _('%s (Copia)') % self.name, 'state':'draft', 'date_from': fields.Date.today(), 'date_to': False})
        return {'type':'ir.actions.act_window','res_model':self._name,'res_id':new.id,'view_mode':'form'}

class CommissionSchemeLine(models.Model):
    _name = 'commission.scheme.line'
    _description = 'Regla de Comisión'
    _order = 'concept_code, evaluation_day, min_amount'
    scheme_id = fields.Many2one('commission.scheme', required=True, ondelete='cascade')
    concept_code = fields.Char(required=True, help='Código/identificador del concepto de Claro o interno.')
    concept_name = fields.Char(required=True)
    match_pattern = fields.Char(help='Texto que debe aparecer en el concepto de la liquidación. Use * para regla genérica.')
    evaluation_day = fields.Integer(help='Día de evaluación desde la activación, p.ej. 60 o 90.')
    calculation_type = fields.Selection([('percentage','Porcentaje'),('fixed','Valor fijo')], default='percentage', required=True)
    base_field = fields.Selection([('consumption','Consumo evaluado'),('consumptions','Consumos'),('recharges','Recargas'),('tariff','Tarifa básica')], default='consumption', required=True)
    min_amount = fields.Monetary(default=0)
    max_amount = fields.Monetary(help='Vacío/0 con Sin límite superior = infinito.')
    no_upper_limit = fields.Boolean()
    percentage = fields.Float(digits=(16,4))
    fixed_amount = fields.Monetary()
    currency_id = fields.Many2one('res.currency', default=lambda s:s.env.company.currency_id.id, required=True)
    active = fields.Boolean(default=True)
    priority = fields.Integer(default=10)

    @api.constrains('min_amount','max_amount','no_upper_limit','percentage')
    def _check_values(self):
        for r in self:
            if not r.no_upper_limit and r.max_amount and r.max_amount < r.min_amount:
                raise ValidationError(_('El límite máximo no puede ser menor al mínimo.'))
            if r.percentage < 0:
                raise ValidationError(_('El porcentaje no puede ser negativo.'))

class CommissionWarehouseMapping(models.Model):
    _name='commission.warehouse.mapping'
    _description='Mapeo Bodega a Región/Zona'
    _order='warehouse_name'
    warehouse_code=fields.Char(index=True)
    warehouse_name=fields.Char(required=True,index=True)
    region_id=fields.Many2one('commission.region',required=True,ondelete='restrict')
    zone_id=fields.Many2one('commission.zone',required=True,ondelete='restrict',domain="[('region_id','=',region_id)]")
    active=fields.Boolean(default=True)
