# -*- coding: utf-8 -*-
from datetime import date
from time import monotonic
from uuid import uuid4
import logging

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.float_utils import float_compare


_logger = logging.getLogger(__name__)

MONTHS = [(str(index), name) for index, name in enumerate((
    'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
    'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre',
), start=1)]
MONTH_NAMES = dict(MONTHS)


class ExpenseBudgetCategory(models.Model):
    _name = 'expense.budget.category'
    _description = 'Rubro presupuestario de gastos'
    _order = 'code, name'
    _rec_name = 'name'
    _check_company_auto = True

    # Código generado para permitir crear rubros directamente desde Presupuesto.
    # Quien necesite un código externo puede reemplazarlo en el formulario.
    code = fields.Char(string='Código de rubro', required=True, index=True,
                       default=lambda self: 'RUB-' + uuid4().hex[:12].upper())
    name = fields.Char(string='Rubro', required=True)
    company_id = fields.Many2one('res.company', string='Empresa', required=True,
                                 default=lambda self: self.env.company, index=True)
    active = fields.Boolean(default=True)
    cost_center_ids = fields.Many2many(
        'expense.budget.cost.center', compute='_compute_cost_center_ids',
        string='Centros detectados en consumos',
        help='Centros encontrados en consumos reales de las cuentas seleccionadas; una cuenta puede tener varios.',
    )

    @api.depends('account_ids', 'account_ids.expense_ids.cost_center_id')
    def _compute_cost_center_ids(self):
        for rec in self:
            rec.cost_center_ids = rec.account_ids.mapped('expense_ids.cost_center_id')

    account_ids = fields.One2many('expense.budget.account', 'category_id', string='Cuentas')
    # Selector de cuentas existentes. El vínculo persistente sigue siendo
    # expense.budget.account.category_id, de modo que Excel, informes y gastos
    # consultan exactamente los mismos datos (sin tabla paralela de relaciones).
    account_selection_ids = fields.Many2many(
        'expense.budget.account', string='Cuentas controladas',
        compute='_compute_account_selection_ids', inverse='_inverse_account_selection_ids',
        help='Seleccione varias cuentas existentes de la empresa. Una cuenta puede pertenecer a un solo rubro; solo se permite reasignar o quitar cuentas sin proyecciones presupuestarias registradas.',
    )

    @api.depends('account_ids', 'account_ids.category_id')
    def _compute_account_selection_ids(self):
        for category in self:
            category.account_selection_ids = category.account_ids

    def _inverse_account_selection_ids(self):
        # Registro puede crear un rubro y asociar cuentas sin obtener permiso
        # general de edición sobre el catálogo de cuentas.
        if not (self.env.su or self.env.user.has_group(
                'expense_budget_control.group_expense_budget_manager') or
                self.env.user.has_group(
                    'expense_budget_control.group_expense_budget_registrar')):
            raise AccessError(_('No tiene permiso para relacionar cuentas con rubros.'))
        for category in self:
            selected = category.account_selection_ids
            current = category.account_ids
            if any(account.company_id != category.company_id for account in selected):
                raise ValidationError(_(
                    'Todas las cuentas seleccionadas deben pertenecer a la empresa del rubro.'
                ))
            added = selected - current
            removed = current - selected
            # La búsqueda en el formulario incluye TODAS las cuentas existentes
            # de la empresa, incluso las ya asignadas a otro rubro. Es una
            # relación real uno-a-muchos mediante account.category_id: mover una
            # cuenta cambia su rubro, no crea una segunda relación paralela.
            # Los consumos ERP sin presupuesto no impiden organizar los rubros.
            # Sí se bloquea la reasignación cuando hay líneas históricas,
            # para no alterar presupuestos ni reportes ya registrados.
            reassigned = added.filtered(lambda account: account.category_id)
            if reassigned and self.env['expense.budget.line'].sudo().search_count([
                    ('account_id', 'in', reassigned.ids),
            ]):
                raise ValidationError(_(
                    'No puede cambiar de rubro una cuenta que ya tiene '
                    'proyecciones presupuestarias registradas.'
                ))
            # No dejar presupuestos históricos apuntando a una cuenta desligada
            # de su rubro: solo se pueden quitar cuentas nunca presupuestadas.
            if removed and self.env['expense.budget.line'].sudo().search_count([
                ('account_id', 'in', removed.ids),
            ]):
                raise ValidationError(_(
                    'No puede quitar una cuenta que ya tiene proyecciones presupuestarias registradas.'
                ))
            if removed:
                removed.sudo().write({'category_id': False})
            if added:
                added.sudo().write({'category_id': category.id})

    _sql_constraints = [
        ('category_company_code_unique', 'unique(company_id, code)',
         'El código del rubro ya existe para esta empresa.'),
    ]

    @api.constrains('company_id', 'code')
    def _check_code_unique_case_insensitive(self):
        # El código (no el nombre del rubro) es su identificador funcional.
        # La UNIQUE SQL mantiene el bloqueo para inserciones concurrentes
        # con código idéntico; esta validación también evita códigos que
        # solo cambian en mayúsculas o espacios.
        for rec in self:
            code = (rec.code or '').strip().casefold()
            if not code:
                raise ValidationError(_('El código del rubro no puede estar vacío.'))
            others = self.sudo().with_context(active_test=False).search([
                ('company_id', '=', rec.company_id.id), ('id', '!=', rec.id),
            ])
            if any((other.code or '').strip().casefold() == code for other in others):
                raise ValidationError(_(
                    'Ya existe un rubro con el código "%(code)s" en la empresa "%(company)s".'
                ) % {'code': rec.code, 'company': rec.company_id.display_name})

    def name_get(self):
        return [(rec.id, '%s - %s' % (rec.code, rec.name)) for rec in self]


class ExpenseBudgetAccount(models.Model):
    _name = 'expense.budget.account'
    _description = 'Cuenta de gasto controlada'
    _order = 'code, name'
    _check_company_auto = True

    code = fields.Char(string='Código de cuenta', required=True, index=True)
    name = fields.Char(string='Cuenta de gasto', required=True)
    category_id = fields.Many2one('expense.budget.category', string='Rubro',
                                  ondelete='restrict', check_company=True)
    company_id = fields.Many2one('res.company', string='Empresa', required=True,
                                 default=lambda self: self.env.company, index=True)
    active = fields.Boolean(default=True)
    expense_ids = fields.One2many('expense.budget.expense', 'account_id', string='Consumos ERP')
    cost_center_ids = fields.Many2many(
        'expense.budget.cost.center', compute='_compute_cost_center_ids',
        string='Centros detectados',
    )

    @api.depends('expense_ids.cost_center_id')
    def _compute_cost_center_ids(self):
        for rec in self:
            rec.cost_center_ids = rec.expense_ids.mapped('cost_center_id')

    note = fields.Text(string='Observaciones')

    _sql_constraints = [
        ('account_company_code_unique', 'unique(company_id, code)',
         'El código de cuenta ya existe para esta empresa.'),
    ]

    @api.constrains('company_id', 'category_id')
    def _check_category_company(self):
        for rec in self:
            if rec.category_id and rec.category_id.company_id != rec.company_id:
                raise ValidationError(_('El rubro debe pertenecer a la misma empresa que la cuenta.'))

    def name_get(self):
        return [(rec.id, '%s - %s' % (rec.code, rec.name)) for rec in self]


class ExpenseBudget(models.Model):
    _name = 'expense.budget'
    _description = 'Presupuesto anual de gastos'
    _order = 'year desc, id desc'
    _check_company_auto = True

    # Cada presupuesto corresponde a UN rubro, dentro de una empresa y año.
    # Se mantiene nullable a nivel de columna para no romper presupuestos
    # históricos de versiones anteriores que mezclaban varios rubros.
    # Todos los presupuestos NUEVOS deben indicar un rubro.
    name = fields.Char(string='Presupuesto', required=True)
    category_id = fields.Many2one(
        'expense.budget.category', string='Rubro del presupuesto',
        ondelete='restrict', check_company=True, index=True,
    )
    year = fields.Integer(string='Año', required=True,
                          default=lambda self: fields.Date.context_today(self).year, index=True)

    # Selector de la ficha. No sustituye el Integer histórico: informes, APIs,
    # reglas de unicidad y líneas siguen usando exactamente el campo "year".
    # El modelo ya limita el año al intervalo 2000-2100.
    @api.model
    def _budget_year_choices(self):
        return [(str(year), str(year)) for year in range(2000, 2101)]

    year_selector = fields.Selection(
        selection='_budget_year_choices', string='Año',
        compute='_compute_year_selector', inverse='_inverse_year_selector',
        help='Seleccione el año del presupuesto. Al crear, se propone el año actual.',
    )

    @api.depends('year')
    def _compute_year_selector(self):
        for budget in self:
            budget.year_selector = str(budget.year) if budget.year else False

    def _inverse_year_selector(self):
        for budget in self:
            if budget.year_selector:
                budget.year = int(budget.year_selector)

    @api.onchange('year_selector')
    def _onchange_year_selector(self):
        # Sincronizar inmediatamente el Integer antes del guardado, de forma
        # que los dominios y validaciones de rubro/empresa usen el año elegido.
        for budget in self:
            if budget.year_selector and budget.year != int(budget.year_selector):
                budget.year = int(budget.year_selector)

    company_id = fields.Many2one('res.company', string='Empresa', required=True,
                                 default=lambda self: self.env.company, index=True)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', store=True)
    state = fields.Selection([
        ('draft', 'Borrador'), ('to_approve', 'Pendiente de aprobación'),
        ('approved', 'Aprobado'), ('rejected', 'Rechazado'),
    ], default='draft', required=True, string='Estado')
    annual_target_ids = fields.One2many(
        'expense.budget.annual.target', 'budget_id',
        string='Presupuesto anual por cuenta y centro de costo',
    )
    line_ids = fields.One2many('expense.budget.line', 'budget_id', string='Proyecciones mensuales')
    # Captura temporal de proyecciones: una sola fila en la cabecera.
    # Se limpia después de Agregar. Los objetivos históricos reales permanecen
    # almacenados en annual_target_ids; no se borra ni se duplica su información.
    quick_account_id = fields.Many2one(
        'expense.budget.account', string='Cuenta controlada',
        ondelete='set null', check_company=True,
    )
    quick_cost_center_id = fields.Many2one(
        'expense.budget.cost.center', string='Centro de costo',
        ondelete='set null', check_company=True,
    )
    quick_month_ids = fields.Many2many(
        'expense.budget.comparison.month',
        'expense_budget_header_quick_month_rel', 'budget_id', 'month_id',
        string='Meses', help='Seleccione los meses por nombre (Enero, Febrero, etc.).',
    )
    quick_available_month_ids = fields.Many2many(
        'expense.budget.comparison.month',
        compute='_compute_quick_available_month_ids', string='Meses disponibles',
    )
    quick_annual_amount = fields.Monetary(
        string='Presupuesto anual', currency_field='currency_id',
        help='Importe a distribuir por partes iguales entre los meses seleccionados.',
    )

    @api.depends('quick_account_id', 'quick_cost_center_id', 'company_id', 'year',
                 'line_ids.month', 'line_ids.account_id', 'line_ids.cost_center_id',
                 'line_ids.approval_state')
    def _compute_quick_available_month_ids(self):
        Month = self.env['expense.budget.comparison.month'].sudo()
        Line = self.env['expense.budget.line'].sudo()
        months = Month.search([])
        for budget in self:
            if not (budget.quick_account_id and budget.quick_cost_center_id and
                    budget.company_id and budget.year):
                budget.quick_available_month_ids = months
                continue
            domain = [
                ('company_id', '=', budget.company_id.id),
                ('year', '=', budget.year),
                ('account_id', '=', budget.quick_account_id.id),
                ('cost_center_id', '=', budget.quick_cost_center_id.id),
            ]
            lines = Line.search(domain + [('month', '!=', False)])
            used = {int(line.month) for line in lines if line.month}
            approved_through = Line._get_approved_through_month_for_pair_values(
                budget.company_id.id, budget.year, budget.quick_account_id.id,
                budget.quick_cost_center_id.id,
            )
            budget.quick_available_month_ids = months.filtered(
                lambda month: month.number not in used
                and (not approved_through or month.number > approved_through)
            )

    @api.onchange('quick_account_id', 'quick_cost_center_id')
    def _onchange_quick_budget_filters(self):
        # Cambio de cuenta/centro: no arrastrar meses ni importes del anterior.
        for budget in self:
            budget.quick_month_ids = [(5, 0, 0)]
            budget.quick_annual_amount = 0.0
            if not (budget.quick_account_id and budget.quick_cost_center_id
                    and budget.company_id and budget.year):
                continue
            target = self.env['expense.budget.annual.target'].sudo().search([
                ('company_id', '=', budget.company_id.id),
                ('year', '=', budget.year),
                ('account_id', '=', budget.quick_account_id.id),
                ('cost_center_id', '=', budget.quick_cost_center_id.id),
            ], limit=1)
            if target:
                budget.quick_annual_amount = target.annual_amount

    def action_add_quick_monthly_lines(self):
        """Usar el asistente existente para no alterar las reglas de aprobación.

        El botón crea inmediatamente las proyecciones y deja limpia la fila.
        """
        self.ensure_one()
        if self.state not in ('draft', 'approved'):
            raise UserError(_('Solo puede agregar proyecciones en borrador o aprobado.'))
        if not (self.env.user.has_group('expense_budget_control.group_expense_budget_registrar')
                or self.env.user.has_group('expense_budget_control.group_expense_budget_manager')):
            raise AccessError(_('No tiene permisos para agregar proyecciones.'))
        if not self.quick_account_id:
            raise UserError(_('Seleccione una cuenta controlada.'))
        if not self.quick_cost_center_id:
            raise UserError(_('Seleccione un centro de costo.'))
        # Ningún mes seleccionado = distribuir entre los 12 meses del año.
        # No se modifica la selección guardada hasta que la operación termina.
        months_to_add = self.quick_month_ids
        if not months_to_add:
            months_to_add = self.env['expense.budget.comparison.month'].sudo().search([
                ('number', '>=', 1), ('number', '<=', 12),
            ], order='number')
            if set(months_to_add.mapped('number')) != set(range(1, 13)):
                raise UserError(_(
                    'No están configurados los 12 meses del año. '
                    'Revise el catálogo de meses antes de agregar las proyecciones.'
                ))
        if self.quick_annual_amount <= 0:
            raise UserError(_('El presupuesto anual debe ser mayor que cero.'))
        if (self.quick_account_id.company_id != self.company_id
                or self.quick_account_id.category_id != self.category_id):
            raise ValidationError(_('La cuenta debe pertenecer al rubro y a la empresa del presupuesto.'))
        if self.quick_cost_center_id.company_id != self.company_id:
            raise ValidationError(_('El centro de costo debe pertenecer a la misma empresa.'))
        # El asistente existente valida de nuevo los meses disponibles, objetivos
        # aprobados, duplicados y genera las líneas usando el modelo oficial.
        wizard = self.env['expense.budget.quick.add.wizard'].create({
            'budget_id': self.id,
            'account_id': self.quick_account_id.id,
            'cost_center_id': self.quick_cost_center_id.id,
            'month_ids': [(6, 0, months_to_add.ids)],
            'annual_amount': self.quick_annual_amount,
        })
        action = wizard.action_add_lines()
        self.write({
            'quick_account_id': False,
            'quick_cost_center_id': False,
            'quick_month_ids': [(5, 0, 0)],
            'quick_annual_amount': 0.0,
        })
        return action

    planned_amount = fields.Monetary(string='Total proyectado', compute='_compute_totals',
                                     store=True, currency_field='currency_id')
    actual_amount = fields.Monetary(string='Total consumido', compute='_compute_totals',
                                    store=True, currency_field='currency_id')
    variance_amount = fields.Monetary(string='Saldo disponible', compute='_compute_totals',
                                      store=True, currency_field='currency_id')
    execution_percentage = fields.Float(string='Ejecución (%)', compute='_compute_totals',
                                        store=True, digits=(16, 2))
    note = fields.Text(string='Observaciones')

    approved_through_month = fields.Selection(
        MONTHS, string='Aprobado hasta', compute='_compute_approval_progress',
        help='Último mes representado cuyas líneas están aprobadas, antes de encontrar líneas sin aprobar.',
    )
    months_pending_approval = fields.Char(
        string='Meses pendientes', compute='_compute_approval_progress',
        help='Meses que contienen líneas en borrador, pendientes de aprobación o rechazadas.',
    )
    has_lines_to_submit = fields.Boolean(
        string='Tiene líneas para enviar', compute='_compute_approval_progress',
    )

    _sql_constraints = [
        ('budget_company_year_category_unique',
         'unique(company_id, year, category_id)',
         'Ya existe un presupuesto de ese rubro para la empresa y el año seleccionados.'),
    ]

    # Distintos rubros de un año se pueden registrar simultáneamente,
    # sin esperar a que los anteriores sean aprobados.

    @api.model
    def _find_duplicate_rubro_code(self, company_id, year, category, exclude_id=False):
        """Buscar por CÓDIGO del rubro de cabecera y no por nombre o estado.

        Dos rubros con el mismo código normalizado pertenecen al mismo
        presupuesto anual, incluso si fueran IDs diferentes legados.
        No ejecutar llamadas al ERP ni examinar las líneas de proyección.
        """
        if not category or not category.code:
            return self.browse()
        domain = [
            ('company_id', '=', company_id), ('year', '=', year),
            ('category_id', '!=', False),
        ]
        if exclude_id:
            domain.append(('id', '!=', exclude_id))
        other_budgets = self.sudo().with_context(active_test=False).search(domain)
        code = category.code.strip().casefold()
        return other_budgets.filtered(
            lambda budget: (budget.category_id.code or '').strip().casefold() == code
        )[:1]

    @api.constrains('company_id', 'year', 'category_id')
    def _check_unique_budget_per_rubro(self):
        for rec in self:
            if not rec.category_id:
                # Presupuesto legado sin rubro único: no alterar ni borrar.
                continue
            duplicate = rec._find_duplicate_rubro_code(
                rec.company_id.id, rec.year, rec.category_id, exclude_id=rec.id,
            )
            if duplicate:
                raise ValidationError(_(
                    'Ya existe el presupuesto "%(budget)s" para el rubro "%(rubro)s" '
                    'en el año %(year)s y la empresa "%(company)s". '
                    'Solo se permite un presupuesto por rubro y año.'
                ) % {
                    'budget': duplicate.name, 'rubro': '%s (%s)' % (rec.category_id.name, rec.category_id.code),
                    'year': rec.year, 'company': rec.company_id.display_name,
                })

    @api.model
    def _legacy_budget_containing_rubro(self, company_id, year, category_id, exclude_id=False):
        # Los antiguos presupuestos multirrubro pueden tener cabecera sin
        # categoría (o distinta de alguna de sus líneas). No considerar libre
        # un rubro que ya se presupuestó allí.
        domain = [
            ('budget_id.company_id', '=', company_id),
            ('budget_id.year', '=', year),
            ('account_id.category_id', '=', category_id),
            '|', ('budget_id.category_id', '=', False),
                 ('budget_id.category_id', '!=', category_id),
        ]
        if exclude_id:
            domain.append(('budget_id', '!=', exclude_id))
        line = self.env['expense.budget.line'].sudo().search(domain, limit=1)
        return line.budget_id

    @api.depends('line_ids.planned_amount', 'line_ids.actual_amount')
    def _compute_totals(self):
        for rec in self:
            rec.planned_amount = sum(rec.line_ids.mapped('planned_amount'))
            rec.actual_amount = sum(rec.line_ids.mapped('actual_amount'))
            rec.variance_amount = rec.planned_amount - rec.actual_amount
            rec.execution_percentage = (rec.actual_amount / rec.planned_amount * 100.0
                                        if rec.planned_amount else 0.0)

    @api.depends('line_ids.month', 'line_ids.approval_state')
    def _compute_approval_progress(self):
        # Resume el avance de aprobación por mes y por línea. Si hay un mes
        # pendiente, el indicador se detiene antes de ese primer mes.
        for rec in self:
            by_month = {}
            pending_months = set()
            for line in rec.line_ids:
                month_number = int(line.month) if line.month else 0
                if not month_number:
                    continue
                by_month.setdefault(month_number, []).append(line.approval_state)
                if line.approval_state != 'approved':
                    pending_months.add(month_number)

            approved_through = False
            if by_month:
                first_pending = min(pending_months) if pending_months else None
                approved_months = [
                    month_number for month_number, states in by_month.items()
                    if all(state == 'approved' for state in states)
                    and (first_pending is None or month_number < first_pending)
                ]
                if approved_months:
                    approved_through = str(max(approved_months))
                elif not pending_months:
                    approved_through = str(max(by_month))

            rec.approved_through_month = approved_through
            rec.months_pending_approval = ', '.join(
                MONTH_NAMES[str(month_number)]
                for month_number in sorted(pending_months)
            ) or False
            rec.has_lines_to_submit = any(
                line.approval_state in ('draft', 'rejected') for line in rec.line_ids
            )

    @api.onchange('company_id')
    def _onchange_budget_company(self):
        if self.category_id and self.category_id.company_id != self.company_id:
            self.category_id = False

    @api.constrains('category_id', 'company_id')
    def _check_budget_category_company(self):
        for rec in self:
            if rec.category_id and rec.category_id.company_id != rec.company_id:
                raise ValidationError(_('El rubro del presupuesto debe pertenecer a su empresa.'))

    @api.constrains('year')
    def _check_year(self):
        for rec in self:
            if not 2000 <= rec.year <= 2100:
                raise ValidationError(_('El año debe estar entre 2000 y 2100.'))

    @api.model_create_multi
    def create(self, vals_list):
        started = monotonic()
        if any(vals.get('state', 'draft') != 'draft' for vals in vals_list):
            raise UserError(_('Los presupuestos nuevos deben registrarse en borrador.'))
        # Una empresa/año admite distintos rubros en paralelo, pero nunca un
        # segundo presupuesto para el mismo rubro, incluso si el primero está
        # aprobado o rechazado. También se detectan repetidos en create_multi.
        new_keys = set()
        for vals in vals_list:
            category_id = vals.get('category_id')
            if not category_id:
                raise ValidationError(_(
                    'Seleccione el rubro del presupuesto. Solo se permite un '
                    'presupuesto por rubro, año y empresa.'
                ))
            category = self.env['expense.budget.category'].browse(category_id).exists()
            if not category:
                raise ValidationError(_('El rubro seleccionado ya no existe.'))
            if not vals.get('name'):
                vals['name'] = category.name
            company_id = vals.get('company_id') or self.env.company.id
            year = vals.get('year') or fields.Date.context_today(self).year
            if category.company_id.id != company_id:
                raise ValidationError(_('El rubro debe pertenecer a la empresa del presupuesto.'))
            key = (company_id, year, (category.code or '').strip().casefold())
            if key in new_keys or self._find_duplicate_rubro_code(
                company_id, year, category,
            ):
                raise ValidationError(_(
                    'Ya existe un presupuesto para el rubro "%(rubro)s" en el '
                    'año %(year)s y la empresa "%(company)s". '
                    'Seleccione otro rubro o abra el presupuesto existente.'
                ) % {
                    'rubro': '%s (%s)' % (category.name, category.code), 'year': year,
                    'company': category.company_id.display_name,
                })
            legacy_budget = self._legacy_budget_containing_rubro(company_id, year, category.id)
            if legacy_budget:
                raise ValidationError(_(
                    'El presupuesto histórico "%(budget)s" ya contiene líneas '
                    'del rubro "%(rubro)s" en %(year)s. Revise ese presupuesto '
                    'anterior antes de registrar uno nuevo para el mismo rubro.'
                ) % {'budget': legacy_budget.name, 'rubro': category.display_name, 'year': year})
            new_keys.add(key)
        # Las líneas anidadas no deben llamar a la API una vez por cada fila;
        # consultar una sola vez tras guardar el presupuesto completo.
        checked_at = monotonic()
        budgets = super(ExpenseBudget, self.with_context(
            skip_expense_budget_consumption_on_save=True,
        )).create(vals_list)
        saved_at = monotonic()
        lines = budgets.mapped('line_ids') if not self.env.context.get(
            'skip_expense_budget_consumption_on_save') else self.env['expense.budget.line']
        # NO hacer llamadas al ERP para presupuestos vacíos. El servicio
        # getconsumosgastos/2 se consulta solo cuando se registran líneas.
        if lines:
            self.env['expense.budget.inventory.sync']._sync_saved_lines(lines)
        _logger.info(
            '[PRESUPUESTOS GUARDADO] create ids=%s proyecciones=%s '
            'validacion=%.3fs orm=%.3fs consumos=%.3fs total=%.3fs',
            budgets.ids, len(lines), checked_at - started,
            saved_at - checked_at, monotonic() - saved_at,
            monotonic() - started,
        )
        return budgets

    def _is_allowed_non_draft_line_command(self, command):
        # Validar comandos One2many permitidos en presupuestos no borrador.
        Line = self.env['expense.budget.line']
        if not isinstance(command, (tuple, list)) or not command:
            return False
        command_type = command[0]
        if command_type == 0:
            # Crear una línea nueva en un presupuesto aprobado; create() la
            # fuerza a borrador, nunca permite que nazca aprobada.
            values = command[2] if len(command) > 2 and isinstance(command[2], dict) else {}
            if values.get('approval_state') not in (None, False, 'draft'):
                return False
            if values.get('budget_id') and int(values['budget_id']) not in self.ids:
                return False
            return all(budget.state == 'approved' for budget in self)
        if command_type == 1 and len(command) > 2 and isinstance(command[2], dict):
            line = Line.browse(command[1]).exists()
            if not line or line.budget_id not in self:
                return False
            values = command[2]
            if set(values) == {'actual_amount'}:
                # Se conserva la función existente de ajuste manual de consumo.
                return True
            editable_fields = {
                'account_id', 'category_id', 'cost_center_id', 'subcenter_id',
                'subcenter_code', 'month', 'consumption_date', 'planned_amount', 'annual_amount',
            }
            return (
                line.budget_id.state == 'approved'
                and line.approval_state in ('draft', 'rejected')
                and bool(values)
                and set(values).issubset(editable_fields)
            )
        # No permitir borrar/desvincular/reemplazar líneas desde una cabecera no borrador.
        return False

    def _is_allowed_non_draft_target_command(self, command):
        Target = self.env['expense.budget.annual.target']
        if not isinstance(command, (tuple, list)) or not command:
            return False
        command_type = command[0]
        if command_type == 0:
            values = command[2] if len(command) > 2 and isinstance(command[2], dict) else {}
            if values.get('budget_id') and int(values['budget_id']) not in self.ids:
                return False
            return all(budget.state == 'approved' for budget in self)
        if command_type == 1 and len(command) > 2 and isinstance(command[2], dict):
            target = Target.browse(command[1]).exists()
            return bool(target and target.budget_id in self and command[2])
        if command_type == 2 and len(command) > 1:
            target = Target.browse(command[1]).exists()
            return bool(target and target.budget_id in self)
        return False

    def write(self, vals):
        started = monotonic()
        if 'category_id' in vals:
            if not vals['category_id']:
                raise ValidationError(_('Debe seleccionar el rubro del presupuesto.'))
            # Al guardar/imprimir, algunos clientes reenvían el mismo valor.
            # No interpretarlo como un cambio real del rubro en cabecera.
            if any(rec.category_id.id != vals['category_id'] and
                   (rec.state != 'draft' or rec.line_ids) for rec in self):
                raise UserError(_('No puede cambiar el rubro de un presupuesto con líneas o enviado.'))
            vals = dict(vals)
            category = self.env['expense.budget.category'].browse(vals['category_id']).exists()
            if category:
                if any(rec.company_id != category.company_id for rec in self) and 'company_id' not in vals:
                    raise ValidationError(_('El rubro debe pertenecer a la empresa del presupuesto.'))
            # Cambiar el rubro opcional no reemplaza el nombre del presupuesto.
        # El registrador puede editar el borrador, pero no cambiar su estado
        # mediante escritura directa ni mediante llamadas RPC.
        if 'state' in vals and not (
            self.env.su or self.env.user.has_group(
                'expense_budget_control.group_expense_budget_manager')
        ):
            raise AccessError(_('Solo el aprobador puede aprobar desde el botón correspondiente.'))
        if not self.env.su and not self.env.user.has_group(
            'expense_budget_control.group_expense_budget_manager'):
            if vals and any(rec.state != 'draft' for rec in self):
                # Después de aprobar, Registro puede agregar/editar solo líneas
                # aún no aprobadas. Las líneas aprobadas siguen bloqueadas.
                registrar = self.env.user.has_group(
                    'expense_budget_control.group_expense_budget_registrar'
                )
                allowed_fields = {'line_ids', 'annual_target_ids'}
                quick_fields = {
                    'quick_account_id', 'quick_cost_center_id',
                    'quick_month_ids', 'quick_annual_amount',
                }
                only_quick_filters = (
                    bool(vals) and set(vals).issubset(quick_fields)
                    and all(rec.state == 'approved' for rec in self)
                )
                only_budget_lines = bool(vals.get('line_ids')) and set(vals) == {'line_ids'}
                line_commands_allowed = only_budget_lines and all(
                    self._is_allowed_non_draft_line_command(command)
                    for command in vals.get('line_ids', ())
                )
                target_commands_allowed = (
                    bool(vals.get('annual_target_ids')) and set(vals) == {'annual_target_ids'}
                    and all(self._is_allowed_non_draft_target_command(command)
                            for command in vals.get('annual_target_ids', ()))
                )
                mixed_commands_allowed = (
                    bool(vals.get('line_ids')) and bool(vals.get('annual_target_ids'))
                    and set(vals) == allowed_fields
                    and all(self._is_allowed_non_draft_line_command(command)
                            for command in vals.get('line_ids', ()))
                    and all(self._is_allowed_non_draft_target_command(command)
                            for command in vals.get('annual_target_ids', ()))
                )
                if not registrar or not (only_quick_filters or line_commands_allowed or target_commands_allowed or mixed_commands_allowed):
                    raise UserError(_(
                        'En un presupuesto enviado o aprobado solo puede actualizar el consumido, '
                        'agregar/editar presupuestos anuales aún no bloqueados o gestionar nuevas líneas no aprobadas.'
                    ))
        if any(
            (('year' in vals and vals['year'] != rec.year) or
             ('company_id' in vals and vals['company_id'] != rec.company_id.id))
            and (rec.state != 'draft' or rec.line_ids) for rec in self
        ):
            raise UserError(_('No puede cambiar el año o la empresa de un presupuesto con líneas o aprobado.'))
        # Validación anticipada al editar rubro/año/empresa, para devolver un
        # mensaje funcional antes de intentar escribir el índice único SQL.
        if {'category_id', 'year', 'company_id'}.intersection(vals):
            changed_keys = set()
            for rec in self:
                company_id = vals.get('company_id', rec.company_id.id)
                year = vals.get('year', rec.year)
                category_id = vals.get('category_id', rec.category_id.id)
                if not category_id:
                    raise ValidationError(_('Debe seleccionar el rubro del presupuesto.'))
                category = self.env['expense.budget.category'].browse(category_id).exists()
                if not category:
                    raise ValidationError(_('El rubro seleccionado no existe.'))
                key = (company_id, year, (category.code or '').strip().casefold())
                duplicate = self._find_duplicate_rubro_code(
                    company_id, year, category, exclude_id=rec.id,
                )
                if key in changed_keys or duplicate:
                    raise ValidationError(_(
                        'Ya existe un presupuesto para el código de rubro "%(code)s" '
                        'en la empresa "%(company)s" y el año %(year)s. '
                        'Abra el existente o seleccione otro rubro.'
                    ) % {'code': category.code, 'company': category.company_id.name, 'year': year})
                legacy_budget = self._legacy_budget_containing_rubro(
                    company_id, year, category_id, exclude_id=rec.id,
                )
                if legacy_budget:
                    raise ValidationError(_(
                        'El presupuesto histórico "%s" ya contiene líneas '
                        'de este rubro en el año seleccionado.'
                    ) % legacy_budget.name)
                changed_keys.add(key)
        # El formulario envía comandos One2many incluso cuando el usuario solo
        # cambia un importe proyectado. No descargar todo el ERP en ese caso.
        matching_fields = {'account_id', 'cost_center_id', 'subcenter_id',
                           'subcenter_code', 'month', 'consumption_date', 'budget_id'}
        commands = vals.get('line_ids') or []
        previous_lines = {budget.id: set(budget.line_ids.ids) for budget in self} if commands else {}
        changed_line_ids = set()
        for command in commands:
            if not isinstance(command, (tuple, list)) or not command:
                continue
            if command[0] == 1 and len(command) > 2 and matching_fields.intersection(command[2] or {}):
                changed_line_ids.add(command[1])
        result = super(ExpenseBudget, self.with_context(
            skip_expense_budget_consumption_on_save=True,
        )).write(vals)
        saved_at = monotonic()
        consulted_lines = 0
        if commands and not self.env.context.get('skip_expense_budget_consumption_on_save'):
            for budget in self:
                changed_line_ids.update(set(budget.line_ids.ids) - previous_lines[budget.id])
            if changed_line_ids:
                lines = self.env['expense.budget.line'].browse(list(changed_line_ids)).exists()
                consulted_lines = len(lines)
                self.env['expense.budget.inventory.sync']._sync_saved_lines(lines)
        _logger.info(
            '[PRESUPUESTOS GUARDADO] write ids=%s lineas_consultadas=%s '
            'orm=%.3fs consumos=%.3fs total=%.3fs',
            self.ids, consulted_lines, saved_at - started,
            monotonic() - saved_at, monotonic() - started,
        )
        return result

    def action_submit(self):
        # Enviar el borrador inicial o las nuevas líneas de un presupuesto aprobado.
        if not (self.env.su or self.env.user.has_group(
                'expense_budget_control.group_expense_budget_registrar') or
                self.env.user.has_group('expense_budget_control.group_expense_budget_manager')):
            raise AccessError(_('Solo Registro de presupuestos o Administrador pueden enviar a aprobar.'))
        self.check_access('write')
        for rec in self:
            if rec.state not in ('draft', 'approved'):
                raise UserError(_(
                    'Solo se puede enviar un presupuesto en borrador o las nuevas líneas de uno aprobado.'
                ))
            if not rec.category_id:
                raise UserError(_('Seleccione el rubro del presupuesto antes de enviarlo a aprobación.'))
            lines_to_submit = rec.line_ids.filtered(
                lambda line: line.approval_state in ('draft', 'rejected')
            )
            if not lines_to_submit:
                raise UserError(_('No hay líneas nuevas o pendientes para enviar a aprobación.'))
            if any(not line.account_id or not line.month for line in lines_to_submit):
                raise UserError(_('Complete la cuenta y el mes de todas las nuevas líneas antes de enviar.'))
        # Solo cambia el estado del lote actual; las líneas aprobadas no se tocan.
        for rec in self.sudo():
            rec.line_ids.filtered(
                lambda line: line.approval_state in ('draft', 'rejected')
            ).with_context(allow_budget_line_approval_state=True).write({
                'approval_state': 'to_approve',
            })
            rec.write({'state': 'to_approve'})
        return True

    def action_approve(self):
        # Validar permisos antes de elevar privilegios para la transición.
        is_manager = self.env.su or self.env.user.has_group(
            'expense_budget_control.group_expense_budget_manager')
        is_approver = self.env.user.has_group(
            'expense_budget_control.group_expense_budget_approver')
        if not (is_manager or is_approver):
            raise AccessError(_('Solo el aprobador o el administrador pueden aprobar presupuestos.'))
        self.check_access('read')
        for rec in self:
            if rec.state != 'to_approve':
                raise UserError(_('Solo puede aprobar presupuestos enviados a aprobación.'))
            if not rec.category_id:
                raise UserError(_('El presupuesto debe tener un rubro antes de aprobarlo.'))
            if not rec.line_ids.filtered(lambda line: line.approval_state == 'to_approve'):
                raise UserError(_('No hay líneas pendientes de aprobación en este presupuesto.'))
            if not is_manager and rec.create_uid == self.env.user:
                raise AccessError(_('No puede aprobar un presupuesto registrado por usted mismo.'))
        # Aprobar únicamente las líneas del lote enviado. Las aprobadas en rondas
        # anteriores conservan su estado y nunca se reescriben.
        for rec in self.sudo():
            rec.line_ids.filtered(
                lambda line: line.approval_state == 'to_approve'
            ).with_context(allow_budget_line_approval_state=True).write({
                'approval_state': 'approved',
            })
            rec.write({'state': 'approved'})
        return True

    def action_reject(self):
        # Rechazar solo el lote enviado y mantener intacto el historial aprobado.
        is_manager = self.env.su or self.env.user.has_group(
            'expense_budget_control.group_expense_budget_manager')
        is_approver = self.env.user.has_group(
            'expense_budget_control.group_expense_budget_approver')
        if not (is_manager or is_approver):
            raise AccessError(_('Solo un aprobador o administrador puede rechazar presupuestos.'))
        self.check_access('read')
        for rec in self:
            if rec.state != 'to_approve':
                raise UserError(_('Solo se pueden rechazar presupuestos pendientes de aprobación.'))
            if not rec.line_ids.filtered(lambda line: line.approval_state == 'to_approve'):
                raise UserError(_('No hay líneas pendientes de aprobación para rechazar.'))
            if not is_manager and rec.create_uid == self.env.user:
                raise AccessError(_('No puede rechazar un presupuesto creado por usted mismo.'))
        for rec in self.sudo():
            had_approved_lines = any(
                line.approval_state == 'approved' for line in rec.line_ids
            )
            rec.line_ids.filtered(
                lambda line: line.approval_state == 'to_approve'
            ).with_context(allow_budget_line_approval_state=True).write({
                'approval_state': 'rejected',
            })
            # Si se rechazó una ampliación, la cabecera vuelve a aprobado y las
            # líneas del lote quedan editables para corregirlas y reenviarlas.
            rec.write({'state': 'approved' if had_approved_lines else 'rejected'})
        return True

    def action_reopen(self):
        if not (self.env.su or self.env.user.has_group(
            'expense_budget_control.group_expense_budget_manager')):
            raise AccessError(_('Solo el administrador puede volver el presupuesto a borrador.'))
        for rec in self:
            if rec.category_id and rec._find_duplicate_rubro_code(
                rec.company_id.id, rec.year, rec.category_id, exclude_id=rec.id,
            ):
                raise UserError(_(
                    'Ya existe otro presupuesto para este rubro, empresa y año.'
                ))
        self.write({'state': 'draft'})

    def action_reconcile_expenses(self):
        if not (self.env.user.has_group('expense_budget_control.group_expense_budget_manager')
                or self.env.user.has_group('expense_budget_control.group_expense_budget_registrar')):
            raise AccessError(_('No tiene permiso para conciliar gastos.'))
        # Comprueba el acceso a cada presupuesto antes de modificar los gastos vinculados.
        self.check_access('read')
        reconciled = 0
        for budget in self:
            expenses = self.env['expense.budget.expense'].search([
                ('company_id', '=', budget.company_id.id),
                ('date', '>=', '%04d-01-01' % budget.year),
                ('date', '<=', '%04d-12-31' % budget.year),
                ('budget_line_id', '=', False),
            ])
            for expense in expenses:
                line = self.env['expense.budget.expense']._find_budget_line(
                    budget.company_id.id, expense.account_id.id, expense.date,
                    expense.cost_center_id.id, expense.subcenter_code,
                )
                if line and line.budget_id != budget:
                    continue
                if line:
                    # El registrador no puede editar gastos; este botón solo concilia
                    # movimientos ya visibles para él con líneas del mismo presupuesto.
                    expense.sudo().write({'budget_line_id': line.id})
                    reconciled += 1
        return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
            'title': _('Conciliación completada'),
            'message': _('%s gastos asignados a sus líneas presupuestarias.') % reconciled,
            'type': 'success', 'sticky': False,
        }}

    @api.model
    def cron_sync_all(self):
        """Cron técnico: el usuario de la tarea debe ser administrador del sistema."""
        if not (self.env.is_superuser() or self.env.user.has_group('base.group_system')):
            raise AccessError(_('Solo el administrador del sistema puede ejecutar la tarea API.'))
        return self.env['expense.budget.api.sync'].cron_sync_all()

    def action_open_quick_add_wizard(self):
        """Open the guided multi-month projection creator for this budget."""
        self.ensure_one()
        if self.state not in ('draft', 'approved'):
            raise UserError(_('Solo puede agregar líneas cuando el presupuesto está en borrador o aprobado.'))
        if not (self.env.user.has_group('expense_budget_control.group_expense_budget_registrar')
                or self.env.user.has_group('expense_budget_control.group_expense_budget_manager')):
            raise AccessError(_('No tiene permisos para agregar líneas al presupuesto.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Agregar líneas por meses'),
            'res_model': 'expense.budget.quick.add.wizard',
            'view_mode': 'form',
            'view_id': self.env.ref(
                'expense_budget_control.view_expense_budget_quick_add_wizard_form'
            ).id,
            'target': 'new',
            'context': {'default_budget_id': self.id},
        }

    def action_print_annual_pdf(self):
        """Imprime el presupuesto actual en PDF, por rubro, cuenta y mes."""
        self.ensure_one()
        return self.env.ref(
            'expense_budget_control.action_report_expense_budget_annual'
        ).report_action(self)

    def action_sync_api(self):
        if not (self.env.user.has_group('expense_budget_control.group_expense_budget_manager')
                or self.env.user.has_group('expense_budget_control.group_expense_budget_registrar')):
            raise AccessError(_('No tiene permisos para sincronizar gastos.'))
        self.ensure_one()
        self.check_access('read')
        # Primero catálogos ERP y luego consumos; el botón sigue llamándose Sincronizar.
        api_config = self.env['expense.budget.api.config'].sudo().search([
            ('company_id', '=', self.company_id.id),
        ], limit=1)
        result = self.env['expense.budget.inventory.sync']._sync_company(
            self.company_id,  # importa TODOS los años, también al pulsar Sincronizar
        )
        return self.env['expense.budget.inventory.sync']._notification(result)


class ExpenseBudgetAnnualTarget(models.Model):
    _name = 'expense.budget.annual.target'
    _description = 'Presupuesto anual por cuenta controlada y centro de costo'
    _order = 'account_id, cost_center_id'
    _check_company_auto = True

    budget_id = fields.Many2one(
        'expense.budget', string='Presupuesto', required=True,
        ondelete='cascade', check_company=True, index=True,
    )
    company_id = fields.Many2one('res.company', related='budget_id.company_id', store=True, index=True)
    year = fields.Integer(related='budget_id.year', store=True, index=True)
    currency_id = fields.Many2one('res.currency', related='budget_id.currency_id', store=True)
    account_id = fields.Many2one(
        'expense.budget.account', string='Cuenta controlada', required=True,
        ondelete='restrict', check_company=True, index=True,
    )
    cost_center_id = fields.Many2one(
        'expense.budget.cost.center', string='Centro de costo',
        ondelete='restrict', check_company=True, index=True,
        help='Cada combinación de cuenta y centro puede tener su propio presupuesto anual.',
    )
    annual_amount = fields.Monetary(
        string='Presupuesto anual', required=True, default=0.0,
        currency_field='currency_id',
        help='Monto total de referencia para la cuenta y centro de costo. El asistente lo distribuye entre los meses seleccionados.',
    )
    distribution_month_count = fields.Integer(
        string='Meses para distribuir', required=True, default=12,
        help='Cantidad de meses entre los que se distribuye el monto anual. Los presupuestos existentes conservan 12 como valor predeterminado.',
    )
    monthly_amount = fields.Monetary(
        string='Proyectado mensual', compute='_compute_monthly_amount',
        currency_field='currency_id',
    )
    locked = fields.Boolean(
        string='Bloqueado por aprobación', compute='_compute_locked',
        help='Se bloquea cuando ya hay meses aprobados o pendientes de aprobación para esta combinación.',
    )

    @api.depends('annual_amount', 'currency_id', 'distribution_month_count')
    def _compute_monthly_amount(self):
        Line = self.env['expense.budget.line']
        for target in self:
            target.monthly_amount = Line._monthly_amount_from_annual(
                target.annual_amount, target.currency_id, target.distribution_month_count,
            )

    @api.depends('budget_id', 'account_id', 'cost_center_id', 'budget_id.line_ids.approval_state',
                 'budget_id.line_ids.account_id', 'budget_id.line_ids.cost_center_id')
    def _compute_locked(self):
        Line = self.env['expense.budget.line'].sudo()
        for target in self:
            # Let the user complete a new target before it is first saved.
            if not isinstance(target.id, int) or not target.budget_id or not target.account_id:
                target.locked = False
                continue
            target.locked = bool(Line.search([
                ('company_id', '=', target.company_id.id),
                ('year', '=', target.year),
                ('account_id', '=', target.account_id.id),
                ('cost_center_id', '=', target.cost_center_id.id or False),
                ('approval_state', 'in', ('approved', 'to_approve')),
            ], limit=1))

    def _has_protected_months(self):
        """Check directly in the database so RPC writes cannot rely on a stale compute cache."""
        self.ensure_one()
        return bool(self.env['expense.budget.line'].sudo().search_count([
            ('company_id', '=', self.company_id.id),
            ('year', '=', self.year),
            ('account_id', '=', self.account_id.id),
            ('cost_center_id', '=', self.cost_center_id.id or False),
            ('approval_state', 'in', ('approved', 'to_approve')),
        ]))

    @api.onchange('account_id')
    def _onchange_account_id(self):
        for target in self:
            if target.account_id and not target.cost_center_id:
                centers = target.account_id.cost_center_ids.filtered(
                    lambda center: center.company_id == target.company_id
                )
                if len(centers) == 1:
                    target.cost_center_id = centers

    @api.onchange('annual_amount', 'distribution_month_count', 'account_id', 'cost_center_id')
    def _onchange_annual_amount(self):
        Line = self.env['expense.budget.line']
        for target in self:
            if not target.budget_id or not target.account_id:
                continue
            amount = target.annual_amount or 0.0
            monthly = Line._monthly_amount_from_annual(
                amount, target.currency_id, target.distribution_month_count,
            )
            # Reflect the header target immediately in any unapproved lines
            # already loaded in the form. Approved months remain untouched.
            for line in target.budget_id.line_ids:
                if (line.account_id == target.account_id
                        and (line.cost_center_id.id or False) == (target.cost_center_id.id or False)
                        and line.approval_state in ('draft', 'rejected')):
                    line.annual_amount = amount
                    line.allocation_month_count = target.distribution_month_count
                    line.planned_amount = monthly

    @api.constrains('budget_id', 'account_id', 'cost_center_id', 'annual_amount', 'distribution_month_count')
    def _check_target_identity_and_amount(self):
        for target in self:
            if not target.budget_id or not target.account_id:
                continue
            if target.annual_amount < 0:
                raise ValidationError(_('El presupuesto anual no puede ser negativo.'))
            if not 1 <= target.distribution_month_count <= 12:
                raise ValidationError(_('La cantidad de meses para distribuir debe estar entre 1 y 12.'))
            if target.account_id.company_id != target.company_id:
                raise ValidationError(_('La cuenta controlada debe pertenecer a la empresa del presupuesto.'))
            if target.budget_id.category_id and target.account_id.category_id != target.budget_id.category_id:
                raise ValidationError(_('La cuenta controlada debe pertenecer al rubro del presupuesto.'))
            if target.cost_center_id and target.cost_center_id.company_id != target.company_id:
                raise ValidationError(_('El centro de costo debe pertenecer a la empresa del presupuesto.'))
            duplicate = self.sudo().search([
                ('id', '!=', target.id),
                ('company_id', '=', target.company_id.id),
                ('year', '=', target.year),
                ('account_id', '=', target.account_id.id),
                ('cost_center_id', '=', target.cost_center_id.id or False),
            ], limit=1)
            if duplicate:
                raise ValidationError(_(
                    'Ya existe un presupuesto anual para la cuenta "%(account)s" y el centro de costo "%(center)s" en %(year)s. '
                    'Edite el presupuesto anual existente en lugar de crear otro.'
                ) % {
                    'account': target.account_id.display_name,
                    'center': target.cost_center_id.display_name or _('Sin centro de costo'),
                    'year': target.year,
                })

    @api.model_create_multi
    def create(self, vals_list):
        budgets = self.env['expense.budget']
        for vals in vals_list:
            budget = budgets.browse(vals.get('budget_id')).exists()
            if not budget:
                raise ValidationError(_('Seleccione el presupuesto antes de definir el monto anual.'))
            if (budget.state not in ('draft', 'approved')
                    and not self.env.context.get('allow_annual_target_migration')):
                raise UserError(_('Solo se pueden definir montos anuales cuando el presupuesto está en borrador o aprobado.'))
            if vals.get('account_id'):
                account = self.env['expense.budget.account'].browse(vals['account_id']).exists()
                if not account:
                    raise ValidationError(_('La cuenta controlada seleccionada no existe.'))
                if budget.category_id and account.category_id != budget.category_id:
                    raise ValidationError(_('La cuenta controlada debe pertenecer al rubro del presupuesto.'))
                if account.company_id != budget.company_id:
                    raise ValidationError(_('La cuenta controlada debe pertenecer a la empresa del presupuesto.'))
            if vals.get('cost_center_id'):
                center = self.env['expense.budget.cost.center'].browse(vals['cost_center_id']).exists()
                if center and center.company_id != budget.company_id:
                    raise ValidationError(_('El centro de costo debe pertenecer a la empresa del presupuesto.'))
            # If a legacy approved projection already carried an annual target,
            # the header value must agree with it. Approved projected amounts
            # themselves are never modified by this migration to the header UI.
            amount = float(vals.get('annual_amount') or 0.0)
            count = int(vals.get('distribution_month_count') or 12)
            if not 1 <= count <= 12:
                raise ValidationError(_('La cantidad de meses para distribuir debe estar entre 1 y 12.'))
            vals['distribution_month_count'] = count
            if vals.get('account_id'):
                legacy_approved = self.env['expense.budget.line'].sudo().search([
                    ('company_id', '=', budget.company_id.id),
                    ('year', '=', budget.year),
                    ('account_id', '=', vals['account_id']),
                    ('cost_center_id', '=', vals.get('cost_center_id') or False),
                    ('approval_state', '=', 'approved'),
                    ('annual_amount', '>', 0),
                ], order='id desc', limit=1)
                if legacy_approved and float_compare(
                        legacy_approved.annual_amount, amount,
                        precision_rounding=budget.currency_id.rounding) != 0:
                    raise UserError(_(
                        'El monto anual no puede diferir del objetivo que ya fue aprobado para esta cuenta y centro de costo.'
                    ))
        targets = super().create(vals_list)
        if not self.env.context.get('skip_annual_target_sync'):
            targets._sync_unapproved_monthly_lines()
        return targets

    def _sync_unapproved_monthly_lines(self):
        Line = self.env['expense.budget.line'].sudo()
        for target in self:
            if not (target.company_id and target.year and target.account_id):
                continue
            lines = Line.search([
                ('company_id', '=', target.company_id.id),
                ('year', '=', target.year),
                ('account_id', '=', target.account_id.id),
                ('cost_center_id', '=', target.cost_center_id.id or False),
                ('approval_state', 'in', ('draft', 'rejected')),
                ('budget_id.state', 'in', ('draft', 'approved')),
            ])
            if lines:
                lines.with_context(
                    skip_annual_amount_propagation=True,
                    skip_expense_budget_consumption_on_save=True,
                ).write({
                    'annual_amount': target.annual_amount,
                    'allocation_month_count': target.distribution_month_count,
                    'planned_amount': target.monthly_amount,
                })

    def write(self, vals):
        vals = dict(vals)
        protected_identity = {'budget_id', 'account_id', 'cost_center_id'}
        for target in self:
            if target.budget_id.state not in ('draft', 'approved'):
                raise UserError(_('No puede modificar el presupuesto anual mientras el presupuesto está enviado a aprobación o rechazado.'))
            if protected_identity.intersection(vals):
                has_monthly_lines = self.env['expense.budget.line'].sudo().search_count([
                    ('company_id', '=', target.company_id.id),
                    ('year', '=', target.year),
                    ('account_id', '=', target.account_id.id),
                    ('cost_center_id', '=', target.cost_center_id.id or False),
                ])
                if has_monthly_lines:
                    raise UserError(_('No puede cambiar la cuenta, centro o cabecera de un objetivo anual que ya tiene proyecciones mensuales.'))
            if 'distribution_month_count' in vals and not 1 <= int(vals['distribution_month_count'] or 0) <= 12:
                raise ValidationError(_('La cantidad de meses para distribuir debe estar entre 1 y 12.'))
            if {'annual_amount', 'distribution_month_count'}.intersection(vals) and target._has_protected_months():
                new_amount = float(vals.get('annual_amount', target.annual_amount) or 0.0)
                new_count = int(vals.get('distribution_month_count', target.distribution_month_count) or 12)
                amount_changed = float_compare(
                    new_amount, target.annual_amount,
                    precision_rounding=target.currency_id.rounding,
                ) != 0
                count_changed = new_count != target.distribution_month_count
                if amount_changed or count_changed:
                    raise UserError(_(
                        'Este presupuesto anual ya tiene meses aprobados o pendientes de aprobación. '
                        'No puede cambiar el importe ni la distribución; las nuevas proyecciones deben conservarlos.'
                    ))
        result = super().write(vals)
        if {'annual_amount', 'distribution_month_count', 'account_id', 'cost_center_id', 'budget_id'}.intersection(vals):
            self._sync_unapproved_monthly_lines()
        return result

    def unlink(self):
        for target in self:
            if target._has_protected_months():
                raise UserError(_('No puede eliminar un presupuesto anual con meses aprobados o pendientes de aprobación.'))
            lines = self.env['expense.budget.line'].sudo().search([
                ('company_id', '=', target.company_id.id),
                ('year', '=', target.year),
                ('account_id', '=', target.account_id.id),
                ('cost_center_id', '=', target.cost_center_id.id or False),
                ('approval_state', 'in', ('draft', 'rejected')),
                ('budget_id.state', 'in', ('draft', 'approved')),
            ])
            if lines:
                lines.with_context(
                    skip_annual_amount_propagation=True,
                    skip_expense_budget_consumption_on_save=True,
                ).write({'annual_amount': 0.0})
        return super().unlink()


class ExpenseBudgetLine(models.Model):
    _name = 'expense.budget.line'
    _description = 'Presupuesto mensual por cuenta'
    _order = 'budget_id, month, account_id'
    _check_company_auto = True

    budget_id = fields.Many2one('expense.budget', string='Presupuesto', required=True,
                                ondelete='cascade', check_company=True, index=True)
    company_id = fields.Many2one('res.company', related='budget_id.company_id',
                                 store=True, index=True)
    currency_id = fields.Many2one('res.currency', related='budget_id.currency_id', store=True)
    account_id = fields.Many2one('expense.budget.account', string='Cuenta controlada',
                                 required=True, ondelete='restrict', check_company=True)
    cost_center_id = fields.Many2one(
        'expense.budget.cost.center', string='Centro de costo', ondelete='restrict',
        check_company=True, index=True,
        help='Opcional para presupuestos anteriores; seleccione para distribuir por centro.',
    )
    # El nombre que muestra el Many2one puede no coincidir con la cuenta
    # referida por el ERP. Mostrar el código real evita imputaciones falsas
    # (por ejemplo, un movimiento de Sueldos visto desde una cuenta Agua).
    erp_account_code = fields.Char(
        string='Código', related='account_id.code', readonly=True,
        help='El consumo se asocia por este código y no por el nombre de la cuenta.',
    )
    subcenter_code = fields.Char(
        string='Subcentro (legado)', index=True,
        help='Filtro de subcentro de líneas anteriores. Se conserva para no '
             'alterar presupuestos existentes, pero ya no se solicita al crear líneas.',
    )
    # Selector alimentado del ERP. No crea un segundo dato contable: el
    # valor persistente sigue siendo subcenter_code, compatible con gastos
    # históricos, índices únicos y la conciliación existente.
    subcenter_id = fields.Many2one(
        'expense.budget.subcenter', string='Subcentro',
        compute='_compute_subcenter_id', inverse='_inverse_subcenter_id',
        readonly=False,
        help='Seleccione un subcentro detectado por getconsumosgastos/2 para '
             'el centro de costo. Se conservan los consumos históricos.',
    )

    @api.depends('subcenter_code', 'cost_center_id')
    def _compute_subcenter_id(self):
        Subcenter = self.env['expense.budget.subcenter'].sudo()
        for line in self:
            if line.subcenter_code and line.cost_center_id:
                line.subcenter_id = Subcenter.search([
                    ('company_id', '=', line.cost_center_id.company_id.id),
                    ('center_id', '=', line.cost_center_id.id),
                    ('code', '=', line.subcenter_code.strip().upper()),
                ], limit=1)
            else:
                line.subcenter_id = False

    def _inverse_subcenter_id(self):
        for line in self:
            selected = line.subcenter_id
            if selected and selected.center_id != line.cost_center_id:
                raise ValidationError(_('El subcentro debe pertenecer al centro de costo seleccionado.'))
            line.subcenter_code = selected.code if selected else False

    @api.onchange('subcenter_id')
    def _onchange_subcenter_id(self):
        for line in self:
            line.subcenter_code = line.subcenter_id.code if line.subcenter_id else False

    @api.onchange('cost_center_id')
    def _onchange_cost_center_for_subcenter(self):
        for line in self:
            line.subcenter_id = False
            line.subcenter_code = False
            line._clear_month_if_unavailable_for_pair()
            line._apply_existing_annual_amount_for_pair()

    erp_subcenter_codes = fields.Char(
        string='Subcentro', compute='_compute_erp_subcenter_codes', readonly=True,
        help='Subcentro(s) reales devueltos por getconsumosgastos/2, obtenidos '
             'de los gastos vinculados a esta cuenta, centro, año y mes. '
             'Si el ERP devuelve varios subcentros, se muestran separados por comas.',
    )
    # El rubro se define en la CABECERA del presupuesto. La línea conserva
    # category_id almacenado por compatibilidad con reportes y búsqueda.
    # En presupuestos históricos sin rubro de cabecera se usa el de la cuenta.
    category_id = fields.Many2one(
        'expense.budget.category', string='Rubro',
        compute='_compute_category_id', inverse='_inverse_category_id',
        store=True, readonly=False, index=True, check_company=True,
    )

    @api.depends('budget_id.category_id', 'account_id', 'account_id.category_id')
    def _compute_category_id(self):
        for line in self:
            line.category_id = (line.budget_id.category_id or line.account_id.category_id)

    def _inverse_category_id(self):
        # Elegir un rubro en una línea NO reasigna la cuenta a otro rubro.
        # Si se eligió una cuenta, ambas selecciones deben corresponder.
        for line in self:
            if line.account_id and line.category_id != line.account_id.category_id:
                raise ValidationError(_(
                    'La cuenta controlada no pertenece al rubro seleccionado. '
                    'Seleccione una cuenta de ese rubro.'
                ))

    @api.onchange('category_id')
    def _onchange_category_id(self):
        for line in self:
            if line.account_id and line.account_id.category_id != line.category_id:
                selected_category = line.category_id
                line.account_id = False
                line.category_id = selected_category

    @api.model
    def _monthly_amount_from_annual(self, annual_amount, currency=False, months_count=12):
        """Distribute an annual amount across the selected month count."""
        divisor = int(months_count or 12)
        if not 1 <= divisor <= 12:
            divisor = 12
        value = (annual_amount or 0.0) / float(divisor)
        currency = currency or self.env.company.currency_id
        return currency.round(value) if currency else round(value, 2)

    @api.model
    def _annual_pair_identity_domain(self, company_id, year, account_id, cost_center_id=False):
        return [
            ('company_id', '=', company_id),
            ('year', '=', year),
            ('account_id', '=', account_id),
            ('cost_center_id', '=', cost_center_id or False),
        ]

    @api.model
    def _annual_pair_domain(self, company_id, year, account_id, cost_center_id=False):
        return self._annual_pair_identity_domain(
            company_id, year, account_id, cost_center_id,
        ) + [('annual_amount', '>', 0)]

    @api.model
    def _get_distribution_month_count_for_pair(self, company_id, year, account_id, cost_center_id=False):
        """Return the stored allocation divisor, keeping legacy records at 12."""
        if not (company_id and year and account_id):
            return 12
        target = self.env['expense.budget.annual.target'].sudo().search([
            ('company_id', '=', company_id),
            ('year', '=', year),
            ('account_id', '=', account_id),
            ('cost_center_id', '=', cost_center_id or False),
        ], order='id desc', limit=1)
        if target and target.distribution_month_count:
            return target.distribution_month_count
        source = self.sudo().search(
            self._annual_pair_identity_domain(company_id, year, account_id, cost_center_id),
            order='id desc', limit=1,
        )
        return source.allocation_month_count or 12 if source else 12

    @api.model
    def _get_annual_amount_for_pair(self, company_id, year, account_id, cost_center_id=False):
        """Read the annual target from the budget header; fall back to legacy line data."""
        if not (company_id and year and account_id):
            return 0.0
        target = self.env['expense.budget.annual.target'].sudo().search([
            ('company_id', '=', company_id),
            ('year', '=', year),
            ('account_id', '=', account_id),
            ('cost_center_id', '=', cost_center_id or False),
        ], order='id desc', limit=1)
        if target:
            return target.annual_amount
        source = self.sudo().search(
            self._annual_pair_domain(company_id, year, account_id, cost_center_id),
            order='id desc', limit=1,
        )
        return source.annual_amount if source else 0.0

    @api.depends(
        'approval_state', 'annual_amount', 'account_id', 'cost_center_id',
        'budget_id', 'budget_id.year', 'budget_id.line_ids.approval_state',
        'budget_id.line_ids.annual_amount', 'budget_id.line_ids.account_id',
        'budget_id.line_ids.cost_center_id',
    )
    def _compute_annual_amount_readonly(self):
        Line = self.env['expense.budget.line'].sudo()
        for line in self:
            locked = line.approval_state in ('approved', 'to_approve')
            if not locked and line.budget_id and line.account_id:
                domain = Line._annual_pair_domain(
                    line.budget_id.company_id.id, line.budget_id.year,
                    line.account_id.id, line.cost_center_id.id or False,
                ) + [('approval_state', '=', 'approved')] + ([('id', '!=', line.id)] if isinstance(line.id, int) else [])
                # Historical approved lines created before this field was added
                # have annual_amount=0; allow the first annual target to be set
                # on a future line without altering those approved projections.
                locked = bool(Line.search(domain, limit=1))
            line.annual_amount_readonly = locked

    def _apply_existing_annual_amount_for_pair(self):
        """Prefill the annual target from another month of the same pair."""
        Line = self.env['expense.budget.line'].sudo()
        for line in self:
            if not (line.account_id and line.budget_id):
                continue
            center_id = line.cost_center_id.id or False
            # Prefer a sibling in the current unsaved One2many, if one has already
            # received the annual target. This supports adding several months at once.
            sibling = line.budget_id.line_ids.filtered(lambda other: (
                other != line and other.account_id == line.account_id
                and (other.cost_center_id.id or False) == center_id
                and other.annual_amount > 0
            ))[:1]
            header_target = line.budget_id.annual_target_ids.filtered(lambda target: (
                target.account_id == line.account_id
                and (target.cost_center_id.id or False) == center_id
            ))[:1]
            amount = (
                header_target.annual_amount if header_target else
                sibling.annual_amount if sibling else
                self._get_annual_amount_for_pair(
                    line.budget_id.company_id.id, line.budget_id.year,
                    line.account_id.id, center_id,
                )
            )
            divisor = (
                header_target.distribution_month_count if header_target else
                sibling.allocation_month_count if sibling else
                self._get_distribution_month_count_for_pair(
                    line.budget_id.company_id.id, line.budget_id.year,
                    line.account_id.id, center_id,
                )
            )
            if amount > 0:
                line.annual_amount = amount
                line.allocation_month_count = divisor or 12
                line.planned_amount = line._monthly_amount_from_annual(
                    amount, line.currency_id, line.allocation_month_count,
                )
            elif line.annual_amount > 0:
                # The account/center pair changed and no annual target exists for
                # the new pair: do not carry the old pair's amount forward.
                line.annual_amount = 0.0
                line.planned_amount = 0.0

    @api.onchange('annual_amount')
    def _onchange_annual_amount(self):
        for line in self:
            if not line.annual_amount or line.annual_amount <= 0:
                continue
            count = line.allocation_month_count or line._get_distribution_month_count_for_pair(
                line.company_id.id, line.year, line.account_id.id, line.cost_center_id.id or False,
            )
            monthly = line._monthly_amount_from_annual(
                line.annual_amount, line.currency_id, count,
            )
            line.allocation_month_count = count
            line.planned_amount = monthly
            # Keep unapproved sibling months aligned to the same annual target.
            # Approved months are deliberately never changed.
            for sibling in line.budget_id.line_ids:
                if (sibling != line and sibling.account_id == line.account_id
                        and sibling.cost_center_id == line.cost_center_id
                        and sibling.approval_state in ('draft', 'rejected')):
                    sibling.annual_amount = line.annual_amount
                    sibling.allocation_month_count = count
                    sibling.planned_amount = monthly

    @api.onchange('account_id')
    def _onchange_account_id(self):
        for line in self:
            if line.account_id:
                line.category_id = line.account_id.category_id
                centers = line.account_id.cost_center_ids
                if not line.cost_center_id and len(centers) == 1:
                    line.cost_center_id = centers.id
            line._clear_month_if_unavailable_for_pair()
            line._apply_existing_annual_amount_for_pair()

    def _clear_month_if_unavailable_for_pair(self):
        """Clear a selected month when it is used for this account + center pair.

        Approval progression is scoped to the selected account and cost center,
        never to the whole budget. This lets another center start in January.
        """
        for line in self:
            if not line.account_id or not line.month or not line.budget_id:
                continue
            used_months = line._get_used_month_numbers_for_account_center()
            approved_through = line._get_approved_through_month_for_pair()
            month_num = int(line.month)
            if str(month_num) in used_months or (approved_through and month_num <= approved_through):
                line.month = False
                line.month_option_id = False
    year = fields.Integer(string='Año', related='budget_id.year', store=True, index=True,
                          aggregator='max')
    # Campo legado: conservar las fechas de versiones anteriores sin eliminarlas.
    # Nunca usar este dato oculto para filtrar Consumido: el criterio vigente es
    # el MES completo del año del presupuesto.
    consumption_date = fields.Date(
        string='Fecha de consumo (histórica)', index=True, copy=False,
        help='Dato histórico de versiones anteriores. El consumo actual se calcula '
             'por el mes completo y el año del presupuesto.',
    )
    # El almacenamiento histórico sigue siendo `month` (Selection) para no
    # romper informes, importaciones ni integraciones existentes. En el formulario
    # usamos un Many2one contra el catálogo de meses para filtrar las opciones.
    month = fields.Selection(MONTHS, string='Mes', required=True, index=True)
    month_option_id = fields.Many2one(
        'expense.budget.comparison.month', string='Mes',
        compute='_compute_month_option_id', inverse='_inverse_month_option_id',
        readonly=False,
    )
    available_month_option_ids = fields.Many2many(
        'expense.budget.comparison.month', string='Meses disponibles',
        compute='_compute_available_month_option_ids',
    )
    approval_state = fields.Selection([
        ('draft', 'Pendiente de envío'),
        ('to_approve', 'Pendiente de aprobación'),
        ('approved', 'Aprobado'),
        ('rejected', 'Rechazado'),
    ], string='Estado de aprobación', default='draft', required=True, index=True, copy=False)
    @api.depends('month')
    def _compute_month_option_id(self):
        month_model = self.env['expense.budget.comparison.month'].sudo()
        options = month_model.search([])
        options_by_number = {str(option.number): option for option in options}
        for line in self:
            line.month_option_id = options_by_number.get(str(line.month)) if line.month else False

    def _inverse_month_option_id(self):
        for line in self:
            line.month = str(line.month_option_id.number) if line.month_option_id else False

    @api.model
    def _get_approved_through_month_for_pair_values(self, company_id, year, account_id, cost_center_id=False):
        """Server-side equivalent for create(), before the new line exists."""
        if not (company_id and year and account_id):
            return False
        lines = self.sudo().search([
            ('company_id', '=', company_id),
            ('year', '=', year),
            ('account_id', '=', account_id),
            ('cost_center_id', '=', cost_center_id or False),
            ('approval_state', '=', 'approved'),
            ('month', '!=', False),
        ])
        months = [int(month) for month in lines.mapped('month') if month]
        return max(months) if months else False

    def _get_approved_through_month_for_pair(self):
        """Latest approved month for this account + cost center + company + year.

        The header-level ``approved_through_month`` is only a budget summary;
        it must not block a different center from starting at January.
        """
        self.ensure_one()
        if not self.budget_id or not self.account_id:
            return False
        lines = self.env['expense.budget.line'].sudo().search([
            ('company_id', '=', self.budget_id.company_id.id),
            ('year', '=', self.budget_id.year),
            ('account_id', '=', self.account_id.id),
            ('cost_center_id', '=', self.cost_center_id.id or False),
            ('approval_state', '=', 'approved'),
            ('month', '!=', False),
        ])
        months = [int(month) for month in lines.mapped('month') if month]
        return max(months) if months else False

    def _get_used_month_numbers_for_account_center(self):
        """Months used by this account + cost center for this company and year.

        Includes persisted lines from other budgets and unsaved lines currently
        being edited in this budget. A month used by another center does not
        block this combination.
        """
        self.ensure_one()
        if not self.budget_id or not self.account_id:
            return set()

        domain = [
            ('company_id', '=', self.budget_id.company_id.id),
            ('year', '=', self.budget_id.year),
            ('account_id', '=', self.account_id.id),
            ('cost_center_id', '=', self.cost_center_id.id or False),
            ('month', '!=', False),
        ]
        record_id = self.id if isinstance(self.id, int) else False
        if not record_id and self._origin and isinstance(self._origin.id, int):
            record_id = self._origin.id
        if record_id:
            domain.append(('id', '!=', record_id))

        used_lines = self.env['expense.budget.line'].sudo().search(domain)
        used_months = {str(other.month) for other in used_lines if other.month}

        # Include not-yet-saved One2many rows in the form editor.
        for other in self.budget_id.line_ids:
            if (other != self and other.account_id == self.account_id
                    and other.cost_center_id == self.cost_center_id and other.month):
                used_months.add(str(other.month))
        return used_months

    @api.depends(
        'account_id', 'cost_center_id', 'budget_id', 'budget_id.company_id', 'budget_id.year',
        'month', 'budget_id.line_ids.account_id', 'budget_id.line_ids.cost_center_id',
        'budget_id.line_ids.month', 'budget_id.line_ids.approval_state',
    )
    def _compute_available_month_option_ids(self):
        MonthOption = self.env['expense.budget.comparison.month'].sudo()
        all_months = MonthOption.search([])
        for line in self:
            available = all_months
            if line.account_id and line.budget_id:
                used_months = line._get_used_month_numbers_for_account_center()
                available = available.filtered(lambda option: str(option.number) not in used_months)
                # Approval progression is specific to account + cost center.
                # For an approved Agua/Quito line through May, Quito starts in
                # June; Agua/Guayaquil can still start in January if unused.
                approved_through = line._get_approved_through_month_for_pair()
                if approved_through:
                    available = available.filtered(lambda option: option.number > approved_through)
            # Keep the current month visible on existing lines so records can
            # be displayed, while onchange/server validations protect edits.
            current = all_months.filtered(lambda option: str(option.number) == str(line.month))
            line.available_month_option_ids = available | current

    @api.onchange('month_option_id')
    def _onchange_month_option_id(self):
        for line in self:
            line.month = str(line.month_option_id.number) if line.month_option_id else False

    consultation_date_label = fields.Char(
        string='Fecha interpretada', compute='_compute_consultation_date_label',
        help='Texto informativo del mes y año usado para sumar gastos del ERP.',
    )

    @api.depends('consumption_date', 'month', 'budget_id.year')
    def _compute_consultation_date_label(self):
        for line in self:
            if line.month and line.budget_id:
                month_name = MONTH_NAMES.get(str(line.month), '')
                line.consultation_date_label = 'Mes completo: %s de %s' % (
                    month_name.lower(), line.budget_id.year,
                )
            else:
                line.consultation_date_label = False

    @api.constrains('consumption_date', 'budget_id')
    def _check_consumption_date(self):
        # Conservar la comprobación de año de los registros heredados. Al
        # editar el Mes se limpia su fecha histórica (véase write()).
        for line in self:
            if (line.consumption_date and line.budget_id
                    and line.consumption_date.year != line.budget_id.year):
                raise ValidationError(_(
                    'La fecha histórica debe corresponder al año del presupuesto (%s).'
                ) % line.budget_id.year)
    annual_amount = fields.Monetary(
        string='Presupuesto anual', default=0.0, currency_field='currency_id',
        help='Importe total de referencia para esta cuenta y centro de costo. El asistente lo distribuye entre los meses seleccionados; los presupuestos históricos conservan su distribución original.',
    )
    allocation_month_count = fields.Integer(
        string='Meses para distribuir', default=12, required=True, copy=False,
        help='Número de meses usado para calcular Proyectado. Los registros anteriores mantienen 12 por compatibilidad.',
    )
    annual_amount_readonly = fields.Boolean(
        string='Presupuesto anual bloqueado', compute='_compute_annual_amount_readonly',
    )
    planned_amount = fields.Monetary(string='Proyectado', required=True, default=0,
                                     currency_field='currency_id')
    expense_ids = fields.One2many('expense.budget.expense', 'budget_line_id', string='Gastos reales')
    erp_checked_at = fields.Datetime(
        string='Última consulta de consumo ERP', readonly=True, copy=False,
        help='Evita consultar todo el historial ERP repetidamente al guardar la misma proyección.',
    )
    # El ajuste manual conserva el cálculo automático de gastos Excel/API.
    manual_actual_amount = fields.Monetary(
        string='Ajuste manual del consumido', default=0.0,
        currency_field='currency_id', copy=False)
    actual_amount = fields.Monetary(string='Consumido', compute='_compute_actual_amount',
                                    inverse='_inverse_actual_amount',
                                    store=True, currency_field='currency_id')
    variance_amount = fields.Monetary(string='Disponible', compute='_compute_variance_execution',
                                      store=True, currency_field='currency_id')
    execution_percentage = fields.Float(string='Ejecución (%)', compute='_compute_variance_execution',
                                        store=True, digits=(16, 2))

    _sql_constraints = [
        ('planned_amount_nonnegative', 'check(planned_amount >= 0)',
         'La proyección no puede ser negativa.'),
        ('annual_amount_nonnegative', 'check(annual_amount >= 0)',
         'El presupuesto anual no puede ser negativo.'),
        ('allocation_month_count_valid', 'check(allocation_month_count >= 1 and allocation_month_count <= 12)',
         'La cantidad de meses para distribuir debe estar entre 1 y 12.'),
    ]

    def init(self):
        # Legado: la restricción account/mes no distinguía centros de costo.
        # Odoo conserva constraints SQL antiguos al actualizar el modelo;
        # sustituirla por un índice único compatible con los registros sin centro.
        self.env.cr.execute('''
            ALTER TABLE expense_budget_line
            DROP CONSTRAINT IF EXISTS expense_budget_line_budget_month_account_unique
        ''')
        self.env.cr.execute('''
            DROP INDEX IF EXISTS expense_budget_line_cc_month_uniq
        ''')
        self.env.cr.execute('''
            DROP INDEX IF EXISTS expense_budget_line_cc_sub_month_uniq
        ''')
        self.env.cr.execute('''
            CREATE UNIQUE INDEX IF NOT EXISTS expense_budget_line_cc_sub_date_uniq
            ON expense_budget_line (budget_id, account_id, month,
                COALESCE(cost_center_id, 0), COALESCE(subcenter_code, ''),
                COALESCE(consumption_date, DATE '1900-01-01'))
        ''')

    def _period_expenses(self):
        """Consumos de TODO el mes seleccionado y del año del presupuesto.

        Nunca filtrar por consumption_date (dato histórico oculto). La API
        envía Fecha con día exacto, pero la proyección es mensual. Se agregan
        los movimientos de todos los días del mes con cuenta y centro,
        sin filtrar por subcentro y sin incluir otros meses ni años.
        """
        self.ensure_one()
        if not self.month or not self.account_id or not self.budget_id:
            return self.env['expense.budget.expense']
        year, month = int(self.budget_id.year), int(self.month)
        return self.expense_ids.filtered(lambda expense: (
            expense.account_id == self.account_id and
            expense.company_id == self.company_id and
            expense.cost_center_id == self.cost_center_id and
            bool(expense.date) and expense.date.year == year and
            expense.date.month == month
        ))

    @api.depends('expense_ids.subcenter_code', 'expense_ids.date',
                 'expense_ids.account_id', 'expense_ids.cost_center_id',
                 'account_id', 'cost_center_id', 'month', 'consumption_date',
                 'budget_id.year', 'subcenter_code')
    def _compute_erp_subcenter_codes(self):
        """Mostrar el subcentro recibido del ERP, nunca pedirlo al usuario.

        Una proyección sin filtro de subcentro puede sumar gastos de GDE,
        OTRO, etc. Mostrar todos evita etiquetar erróneamente el total.
        Los gastos ya están conciliados con cuenta/centro/año/mes de la línea.
        """
        for rec in self:
            codes = sorted({(expense.subcenter_code or '').strip().upper()
                            for expense in rec._period_expenses() if expense.subcenter_code})
            rec.erp_subcenter_codes = ', '.join(codes) or False

    @api.depends('expense_ids.amount', 'expense_ids.date', 'expense_ids.account_id',
                 'expense_ids.cost_center_id', 'expense_ids.subcenter_code',
                 'manual_actual_amount', 'account_id', 'cost_center_id',
                 'month', 'consumption_date', 'budget_id.year', 'subcenter_code')
    def _compute_actual_amount(self):
        for rec in self:
            rec.actual_amount = sum(rec._period_expenses().mapped('amount')) + rec.manual_actual_amount

    erp_matching_moves = fields.Integer(
        string='Movimientos coincidentes', compute='_compute_erp_matching_moves',
        help='Cantidad de gastos reales vinculados que coinciden con cuenta, '
             'centro, subcentro y mes del presupuesto; no ejecuta llamadas a la API.',
    )

    @api.depends('expense_ids', 'expense_ids.amount', 'expense_ids.date',
                 'expense_ids.account_id', 'expense_ids.cost_center_id',
                 'expense_ids.subcenter_code', 'account_id', 'cost_center_id',
                 'month', 'consumption_date', 'budget_id.year', 'subcenter_code')
    def _compute_erp_matching_moves(self):
        for line in self:
            line.erp_matching_moves = len(line._period_expenses())

    @api.depends('planned_amount', 'actual_amount')
    def _compute_variance_execution(self):
        """Recalcular indicadores cuando se edita el consumido o el proyectado.

        La función inversa de actual_amount modifica manual_actual_amount;
        esta dependencia separada asegura la recomputación tras guardar.
        """
        for rec in self:
            rec.variance_amount = rec.planned_amount - rec.actual_amount
            rec.execution_percentage = (rec.actual_amount / rec.planned_amount * 100.0
                                        if rec.planned_amount else 0.0)

    def _inverse_actual_amount(self):
        """Guardar el consumo escrito a mano sin alterar gastos de API/Excel.

        El importe visible es gastos vinculados + ajuste manual. Al escribir
        un nuevo total, solo cambia el ajuste; el origen de los gastos se conserva.
        """
        for rec in self:
            rec.manual_actual_amount = rec.actual_amount - sum(rec._period_expenses().mapped('amount'))

    @api.constrains('cost_center_id', 'account_id', 'budget_id', 'month', 'consumption_date', 'subcenter_code')
    def _check_cost_center_and_uniqueness(self):
        for rec in self:
            if rec.cost_center_id and rec.cost_center_id.company_id != rec.company_id:
                raise ValidationError(_('El centro de costo debe pertenecer a la empresa del presupuesto.'))
            if rec.budget_id and rec.account_id and rec.month:
                duplicate = self.sudo().search([
                    ('id', '!=', rec.id), ('budget_id', '=', rec.budget_id.id),
                    ('account_id', '=', rec.account_id.id), ('month', '=', rec.month),
                    ('cost_center_id', '=', rec.cost_center_id.id or False),
                ], limit=1)
                if duplicate:
                    raise ValidationError(_(
                        'La cuenta controlada "%s" ya tiene una proyección para %s en el centro de costo "%s". '
                        'Seleccione un mes libre para esa combinación de cuenta y centro.'
                    ) % (
                        rec.account_id.display_name,
                        MONTH_NAMES.get(str(rec.month), rec.month),
                        rec.cost_center_id.display_name or _('Sin centro de costo'),
                    ))

    @api.constrains('account_id', 'budget_id', 'category_id')
    def _check_account_company(self):
        for rec in self:
            if rec.account_id.company_id != rec.budget_id.company_id:
                raise ValidationError(_('La cuenta debe pertenecer a la empresa del presupuesto.'))
            # Solo las líneas de presupuestos nuevos/con rubro definido están
            # sujetas a esta regla; no reescribir históricos multirrubro.
            if (rec.budget_id.category_id and
                    rec.account_id.category_id != rec.budget_id.category_id):
                raise ValidationError(_(
                    'La cuenta "%(account)s" pertenece al rubro "%(actual)s", '
                    'pero el presupuesto corresponde a "%(expected)s". '
                    'Solo se admiten líneas del rubro del presupuesto.'
                ) % {
                    'account': rec.account_id.display_name,
                    'actual': rec.account_id.category_id.display_name or _('Sin rubro'),
                    'expected': rec.budget_id.category_id.display_name,
                })

    @api.constrains('budget_id', 'account_id', 'month', 'consumption_date', 'cost_center_id', 'subcenter_code')
    def _check_unique_account_month_across_budgets(self):
        # Una cuenta + centro + mes no debe duplicarse en distintos presupuestos
        # del mismo año, para no imputar un consumo dos veces.
        for rec in self:
            existing = self.sudo().search([
                ('id', '!=', rec.id),
                ('budget_id', '!=', rec.budget_id.id),
                ('budget_id.company_id', '=', rec.budget_id.company_id.id),
                ('budget_id.year', '=', rec.budget_id.year),
                ('account_id', '=', rec.account_id.id),
                ('month', '=', rec.month),
                ('cost_center_id', '=', rec.cost_center_id.id or False),
            ], limit=1)
            if existing:
                raise ValidationError(_(
                    'Esta cuenta y centro ya están presupuestados para el mismo mes y año '
                    'en otro presupuesto de la empresa.'
                ))

    @api.model_create_multi
    def create(self, vals_list):
        budgets = self.env['expense.budget']
        MonthOption = self.env['expense.budget.comparison.month'].sudo()
        # Resolve annual targets supplied in the same batch first, so one entry
        # applies consistently to all months of that account/center/year.
        batch_targets = {}
        for vals in vals_list:
            budget = budgets.browse(vals.get('budget_id')).exists()
            account_id = vals.get('account_id')
            if not (budget and account_id):
                continue
            amount = float(vals.get('annual_amount') or 0.0)
            if amount <= 0:
                continue
            key = (budget.company_id.id, budget.year, account_id, vals.get('cost_center_id') or False)
            count = int(vals.get('allocation_month_count') or self._get_distribution_month_count_for_pair(*key))
            prior = batch_targets.get(key)
            if prior is not None and (
                    float_compare(prior[0], amount, precision_rounding=budget.currency_id.rounding) != 0
                    or prior[1] != count):
                raise ValidationError(_(
                    'El presupuesto anual y la cantidad de meses de distribución deben ser iguales para todas las líneas de la misma cuenta y centro de costo.'
                ))
            batch_targets[key] = (amount, count)
        for vals in vals_list:
            # El selector visual many2one se traduce al valor Selection histórico.
            if 'month_option_id' in vals:
                option_id = vals.pop('month_option_id')
                option = MonthOption.browse(option_id).exists() if option_id else MonthOption.browse()
                vals['month'] = str(option.number) if option else False
            # Fecha heredada solo se permite desde integraciones antiguas:
            # no impone el mes cuando el usuario proporciona uno explícito.
            if vals.get('consumption_date') and not vals.get('month'):
                vals['month'] = str(fields.Date.to_date(vals['consumption_date']).month)
            if 'subcenter_code' in vals:
                vals['subcenter_code'] = (vals['subcenter_code'] or '').strip().upper() or False
            budget = budgets.browse(vals.get('budget_id')).exists()
            if budget and vals.get('account_id'):
                pair_key = (budget.company_id.id, budget.year, vals.get('account_id'),
                            vals.get('cost_center_id') or False)
                batch_target = batch_targets.get(pair_key)
                amount = batch_target[0] if batch_target else float(vals.get('annual_amount') or 0.0)
                if amount <= 0:
                    amount = self._get_annual_amount_for_pair(*pair_key)
                count = (
                    batch_target[1] if batch_target else
                    int(vals.get('allocation_month_count') or self._get_distribution_month_count_for_pair(*pair_key))
                )
                if amount > 0:
                    # Do not allow a different annual amount once this pair's
                    # annual target has already been approved.
                    approved_target = self.sudo().search(
                        self._annual_pair_domain(*pair_key) + [('approval_state', '=', 'approved')],
                        order='id desc', limit=1,
                    )
                    if approved_target and float_compare(
                            approved_target.annual_amount, amount,
                            precision_rounding=budget.currency_id.rounding) != 0:
                        raise UserError(_(
                            'El presupuesto anual de esta cuenta y centro ya fue aprobado. '
                            'No puede cambiarlo al agregar meses futuros.'
                        ))
                    if approved_target and count != (approved_target.allocation_month_count or 12):
                        raise UserError(_(
                            'La distribución mensual ya fue aprobada para esta cuenta y centro. '
                            'Las nuevas líneas deben conservar el mismo proyectado mensual.'
                        ))
                    vals['annual_amount'] = amount
                    vals['allocation_month_count'] = count
                    vals['planned_amount'] = self._monthly_amount_from_annual(
                        amount, budget.currency_id, count,
                    )
            if budget and budget.state not in ('draft', 'approved'):
                raise UserError(_(
                    'Solo puede agregar proyecciones cuando el presupuesto está en borrador '
                    'o aprobado y no tiene una ronda de aprobación abierta.'
                ))
            if budget and budget.state == 'approved' and not (
                    self.env.su or
                    self.env.user.has_group('expense_budget_control.group_expense_budget_registrar') or
                    self.env.user.has_group('expense_budget_control.group_expense_budget_manager')):
                raise AccessError(_('Solo Registro de presupuestos puede agregar nuevos meses a un presupuesto aprobado.'))
            if budget and vals.get('month') and vals.get('account_id'):
                approved_through = self._get_approved_through_month_for_pair_values(
                    budget.company_id.id, budget.year, vals.get('account_id'),
                    vals.get('cost_center_id') or False,
                )
                if approved_through and int(vals['month']) <= approved_through:
                    raise UserError(_(
                        'Para la cuenta y centro seleccionados, solo puede agregar meses posteriores a %s. '
                        'Otro centro de costo puede iniciar desde enero si todavía no tiene proyección.'
                    ) % MONTH_NAMES[str(approved_through)])
            # Las líneas nuevas siempre empiezan pendientes; no se acepta un estado de aprobación aportado por RPC.
            vals['approval_state'] = 'draft'
        records = super().create(vals_list)
        # The annual target is shared across draft/rejected months of a pair.
        # Never write to previously approved or currently submitted lines.
        if not self.env.context.get('skip_annual_amount_propagation'):
            targets = {}
            for line in records.filtered(lambda row: row.annual_amount > 0 and row.account_id and row.budget_id):
                key = (line.company_id.id, line.year, line.account_id.id, line.cost_center_id.id or False)
                targets[key] = (line.annual_amount, line.allocation_month_count or 12, line.currency_id)
            for key, (amount, count, currency) in targets.items():
                approved_target = self.sudo().search(
                    self._annual_pair_domain(*key) + [('approval_state', '=', 'approved')],
                    order='id desc', limit=1,
                )
                if approved_target and float_compare(
                        approved_target.annual_amount, amount,
                        precision_rounding=currency.rounding) != 0:
                    raise UserError(_(
                        'El presupuesto anual de esta cuenta y centro ya fue aprobado. '
                        'No puede cambiarlo al agregar meses futuros.'
                    ))
                sibling_domain = self._annual_pair_identity_domain(*key) + [
                    ('approval_state', 'in', ['draft', 'rejected']),
                    ('id', 'not in', records.ids),
                ]
                siblings = self.sudo().search(sibling_domain)
                if siblings:
                    siblings.with_context(
                        skip_annual_amount_propagation=True,
                        skip_expense_budget_consumption_on_save=True,
                    ).write({
                        'annual_amount': amount,
                        'allocation_month_count': count,
                        'planned_amount': self._monthly_amount_from_annual(amount, currency, count),
                    })
        records._assign_unmatched_expenses()
        if not self.env.context.get('skip_expense_budget_consumption_on_save'):
            self.env['expense.budget.inventory.sync']._sync_saved_lines(records)
        return records

    def write(self, vals):
        vals = dict(vals)
        if 'month_option_id' in vals:
            option_id = vals.pop('month_option_id')
            option = (
                self.env['expense.budget.comparison.month'].sudo().browse(option_id).exists()
                if option_id else self.env['expense.budget.comparison.month']
            )
            vals['month'] = str(option.number) if option else False
        # El estado solo se cambia desde los botones del flujo, que escriben
        # con sudo() después de validar el grupo del usuario.
        if 'approval_state' in vals and not self.env.su:
            raise AccessError(_('El estado de aprobación de una línea solo puede cambiarse mediante el flujo de aprobación.'))
        # Cambiar el mes en una línea creada cuando existía el calendario
        # elimina el viejo filtro de día y fuerza una consulta mensual nueva.
        if 'month' in vals:
            vals = dict(vals, consumption_date=False)
        elif vals.get('consumption_date') and 'month' not in vals:
            vals = dict(vals, month=str(fields.Date.to_date(vals['consumption_date']).month))
        if 'subcenter_code' in vals:
            vals = dict(vals, subcenter_code=(vals['subcenter_code'] or '').strip().upper() or False)
        if (len(self) == 1 and not self.env.context.get('skip_annual_target_sync')
                and {'account_id', 'cost_center_id', 'budget_id'}.intersection(vals)
                and 'annual_amount' not in vals):
            rec = self
            target_budget = self.env['expense.budget'].browse(
                vals.get('budget_id', rec.budget_id.id)
            ).exists()
            target_account = vals.get('account_id', rec.account_id.id)
            target_center = vals.get('cost_center_id', rec.cost_center_id.id) or False
            if target_budget and target_account:
                amount = self._get_annual_amount_for_pair(
                    target_budget.company_id.id, target_budget.year,
                    target_account, target_center,
                )
                count = self._get_distribution_month_count_for_pair(
                    target_budget.company_id.id, target_budget.year,
                    target_account, target_center,
                )
                if amount > 0:
                    vals['annual_amount'] = amount
                    vals['allocation_month_count'] = count
                    vals['planned_amount'] = self._monthly_amount_from_annual(
                        amount, target_budget.currency_id, count,
                    )
        annual_target = float(vals.get('annual_amount') or 0.0) if 'annual_amount' in vals else None
        if 'planned_amount' in vals and annual_target is None:
            # If a header annual target exists, the monthly projection is derived,
            # not a separate manually editable number (including direct RPC calls).
            for rec in self:
                if not (rec.budget_id and rec.account_id):
                    continue
                header_amount = self._get_annual_amount_for_pair(
                    rec.company_id.id, rec.year, rec.account_id.id,
                    rec.cost_center_id.id or False,
                )
                if header_amount > 0:
                    expected_count = int(
                        vals.get('allocation_month_count')
                        or self._get_distribution_month_count_for_pair(
                            rec.company_id.id, rec.year, rec.account_id.id,
                            rec.cost_center_id.id or False,
                        )
                    )
                    expected_monthly = self._monthly_amount_from_annual(
                        header_amount, rec.currency_id, expected_count,
                    )
                    if float_compare(
                            float(vals['planned_amount']), expected_monthly,
                            precision_rounding=rec.currency_id.rounding) != 0:
                        raise UserError(_(
                            'El campo Proyectado se calcula desde el presupuesto anual y la cantidad de meses de distribución configurada en cabecera. '
                            'Modifique el objetivo anual en la cabecera si necesita cambiar el importe.'
                        ))
        if annual_target is not None:
            default_count = int(vals.get('allocation_month_count') or (self[:1].allocation_month_count if self else 12) or 12)
            if not 1 <= default_count <= 12:
                raise ValidationError(_('La cantidad de meses para distribuir debe estar entre 1 y 12.'))
            vals['allocation_month_count'] = default_count
            for rec in self:
                if rec.account_id and rec.budget_id:
                    pair_domain = self._annual_pair_domain(
                        rec.company_id.id, rec.year, rec.account_id.id,
                        rec.cost_center_id.id or False,
                    ) + [('approval_state', '=', 'approved'), ('id', '!=', rec.id)]
                    approved_target = self.sudo().search(pair_domain, order='id desc', limit=1)
                    if approved_target and float_compare(
                            approved_target.annual_amount, annual_target,
                            precision_rounding=rec.currency_id.rounding) != 0:
                        raise UserError(_(
                            'El presupuesto anual de esta cuenta y centro ya fue aprobado. '
                            'No puede cambiarlo; los meses anteriores deben conservarse.'
                        ))
            if annual_target > 0 and self:
                vals['planned_amount'] = self._monthly_amount_from_annual(
                    annual_target, self[:1].currency_id, default_count,
                )
        period_fields = {'account_id', 'cost_center_id', 'subcenter_code',
                         'subcenter_id', 'budget_id', 'month', 'consumption_date'}
        if period_fields.intersection(vals):
            vals = dict(vals, erp_checked_at=False)
        protected = {
            'account_id', 'category_id', 'cost_center_id', 'subcenter_code',
            'subcenter_id', 'budget_id', 'month', 'consumption_date',
            'planned_amount', 'annual_amount', 'allocation_month_count',
        }
        if protected.intersection(vals):
            for rec in self:
                editable_line = (
                    rec.approval_state in ('draft', 'rejected')
                    and rec.budget_id.state in ('draft', 'approved')
                )
                if not editable_line:
                    raise UserError(_(
                        'No puede modificar una línea aprobada o enviada a aprobación. '
                        'Las líneas nuevas de meses futuros se pueden editar antes de enviarlas.'
                    ))
                if {'account_id', 'cost_center_id', 'budget_id', 'month'}.intersection(vals):
                    target_budget = self.env['expense.budget'].browse(
                        vals.get('budget_id', rec.budget_id.id)
                    ).exists()
                    target_account_id = vals.get('account_id', rec.account_id.id)
                    target_center_id = vals.get('cost_center_id', rec.cost_center_id.id) or False
                    target_month = vals.get('month', rec.month)
                    if target_budget and target_month and target_account_id:
                        approved_through = self._get_approved_through_month_for_pair_values(
                            target_budget.company_id.id, target_budget.year,
                            target_account_id, target_center_id,
                        )
                        if approved_through and int(target_month) <= approved_through:
                            raise UserError(_(
                                'El mes debe ser posterior a %s para esta cuenta y centro de costo. '
                                'Los demás centros mantienen su propio calendario de proyección.'
                            ) % MONTH_NAMES[str(approved_through)])
        # Cambiar solo la fecha de una proyección existente es seguro: la
        # reconciliación reasigna o desvincula movimientos de otros días.
        # Los cambios de cuenta/centro/subcentro siguen protegidos.
        locked_changes = {'account_id', 'cost_center_id', 'subcenter_code', 'budget_id'}.intersection(vals)
        if locked_changes and any(rec.expense_ids for rec in self):
            raise UserError(_('No puede cambiar cuenta, centro, subcentro o presupuesto de una línea con gastos reales. '
                              'Puede cambiar el mes y el sistema volverá a conciliar los movimientos.'))
        # Propagate a changed annual target to the other unapproved months for
        # the same account/center/year. Approved lines remain completely intact.
        result = super().write(vals)
        if (annual_target is not None and annual_target > 0
                and not self.env.context.get('skip_annual_amount_propagation')):
            processed_pairs = set()
            for rec in self:
                if not (rec.account_id and rec.budget_id):
                    continue
                key = (rec.company_id.id, rec.year, rec.account_id.id, rec.cost_center_id.id or False)
                if key in processed_pairs:
                    continue
                processed_pairs.add(key)
                approved_target = self.sudo().search(
                    self._annual_pair_domain(*key) + [('approval_state', '=', 'approved')],
                    order='id desc', limit=1,
                )
                if approved_target and annual_target is not None and float_compare(
                        approved_target.annual_amount, annual_target,
                        precision_rounding=rec.currency_id.rounding) != 0:
                    raise UserError(_(
                        'El presupuesto anual de esta cuenta y centro ya fue aprobado. '
                        'No puede cambiarlo; los meses anteriores deben conservarse.'
                    ))
                if (approved_target and 'allocation_month_count' in vals
                        and int(vals.get('allocation_month_count') or 12) != (approved_target.allocation_month_count or 12)):
                    raise UserError(_(
                        'La distribución mensual de esta cuenta y centro ya fue aprobada. '
                        'No puede cambiarla para los meses futuros.'
                    ))
                effective_annual = annual_target if annual_target is not None else rec.annual_amount
                effective_count = int(vals.get('allocation_month_count') or rec.allocation_month_count or 12)
                sibling_domain = self._annual_pair_identity_domain(*key) + [
                    ('approval_state', 'in', ['draft', 'rejected']),
                    ('id', 'not in', self.ids),
                ]
                siblings = self.sudo().search(sibling_domain)
                if siblings:
                    siblings.with_context(
                        skip_annual_amount_propagation=True,
                        skip_expense_budget_consumption_on_save=True,
                    ).write({
                        'annual_amount': effective_annual,
                        'allocation_month_count': effective_count,
                        'planned_amount': self._monthly_amount_from_annual(
                            effective_annual, rec.currency_id, effective_count,
                        ),
                    })
        if 'month' in vals or 'consumption_date' in vals:
            # Al cambiar de mes, desvincular el mes anterior y vincular
            # exclusivamente gastos del nuevo período mensual.
            self.env['expense.budget.inventory.sync']._reconcile_saved_line_periods(self)
        if {'account_id', 'cost_center_id', 'subcenter_code', 'budget_id', 'month', 'consumption_date'}.intersection(vals):
            self._assign_unmatched_expenses()
        if (period_fields.intersection(vals)
                and not self.env.context.get('skip_expense_budget_consumption_on_save')):
            self.env['expense.budget.inventory.sync']._sync_saved_lines(self)
        return result

    def unlink(self):
        for rec in self:
            if rec.approval_state in ('approved', 'to_approve'):
                raise UserError(_('No puede eliminar líneas aprobadas o pendientes de aprobación.'))
            if rec.budget_id.state not in ('draft', 'approved'):
                raise UserError(_('Solo puede eliminar líneas en borrador o nuevas líneas aún no aprobadas.'))
        return super().unlink()

    def _assign_unmatched_expenses(self):
        Expense = self.env['expense.budget.expense'].sudo()
        for line in self:
            year, month = line.budget_id.year, int(line.month)
            start = date(year, month, 1)
            end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
            period = [
                ('date', '>=', fields.Date.to_string(start)),
                ('date', '<', fields.Date.to_string(end)),
            ]
            expenses = Expense.search([
                ('company_id', '=', line.company_id.id),
                ('account_id', '=', line.account_id.id),
                ('cost_center_id', '=', line.cost_center_id.id or False),
            ] + period)
            for expense in expenses:
                target = Expense._find_budget_line(
                    expense.company_id.id, expense.account_id.id, expense.date,
                    expense.cost_center_id.id, expense.subcenter_code,
                )
                if target == line and expense.budget_line_id != line:
                    expense.write({'budget_line_id': line.id})
