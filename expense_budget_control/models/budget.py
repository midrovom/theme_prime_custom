# -*- coding: utf-8 -*-
from datetime import date
from uuid import uuid4

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


MONTHS = [(str(index), name) for index, name in enumerate((
    'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
    'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre',
), start=1)]


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

    # El nombre del presupuesto es libre. El rubro de cada proyección se
    # obtiene de su cuenta controlada; category_id se conserva por compatibilidad
    # con presupuestos previos, sin restringir las líneas nuevas.
    name = fields.Char(string='Presupuesto', required=True)
    category_id = fields.Many2one(
        'expense.budget.category', string='Rubro del presupuesto',
        ondelete='restrict', check_company=True, index=True,
    )
    year = fields.Integer(string='Año', required=True,
                          default=lambda self: fields.Date.context_today(self).year, index=True)
    company_id = fields.Many2one('res.company', string='Empresa', required=True,
                                 default=lambda self: self.env.company, index=True)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', store=True)
    state = fields.Selection([
        ('draft', 'Borrador'), ('to_approve', 'Pendiente de aprobación'),
        ('approved', 'Aprobado'), ('rejected', 'Rechazado'),
    ], default='draft', required=True, string='Estado')
    line_ids = fields.One2many('expense.budget.line', 'budget_id', string='Proyecciones mensuales')
    planned_amount = fields.Monetary(string='Total proyectado', compute='_compute_totals',
                                     store=True, currency_field='currency_id')
    actual_amount = fields.Monetary(string='Total consumido', compute='_compute_totals',
                                    store=True, currency_field='currency_id')
    variance_amount = fields.Monetary(string='Saldo disponible', compute='_compute_totals',
                                      store=True, currency_field='currency_id')
    execution_percentage = fields.Float(string='Ejecución (%)', compute='_compute_totals',
                                        store=True, digits=(16, 2))
    note = fields.Text(string='Observaciones')

    # Se permiten presupuestos por rubros distintos para la misma empresa y año,
    # siempre que el anterior ya haya sido aprobado.

    @api.depends('line_ids.planned_amount', 'line_ids.actual_amount')
    def _compute_totals(self):
        for rec in self:
            rec.planned_amount = sum(rec.line_ids.mapped('planned_amount'))
            rec.actual_amount = sum(rec.line_ids.mapped('actual_amount'))
            rec.variance_amount = rec.planned_amount - rec.actual_amount
            rec.execution_percentage = (rec.actual_amount / rec.planned_amount * 100.0
                                        if rec.planned_amount else 0.0)

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
        if any(vals.get('state', 'draft') != 'draft' for vals in vals_list):
            raise UserError(_('Los presupuestos nuevos deben registrarse en borrador.'))
        # No se inicia el siguiente rubro mientras exista un presupuesto de
        # la empresa/año sin aprobar. Sí se admiten varios ya aprobados.
        new_periods = set()
        for vals in vals_list:
            if vals.get('category_id'):
                category = self.env['expense.budget.category'].browse(vals['category_id']).exists()
                if not category:
                    raise ValidationError(_('El rubro seleccionado ya no existe.'))
                # Compatibilidad con clientes antiguos que envían solo
                # category_id: nunca pisar un name escrito expresamente.
                if not vals.get('name'):
                    vals['name'] = category.name
                if category.company_id.id != (vals.get('company_id') or self.env.company.id):
                    raise ValidationError(_('El rubro debe pertenecer a la empresa del presupuesto.'))
            company_id = vals.get('company_id') or self.env.company.id
            year = vals.get('year') or fields.Date.context_today(self).year
            period = (company_id, year)
            if period in new_periods or self.search_count([
                ('company_id', '=', company_id), ('year', '=', year),
                ('state', 'in', ('draft', 'to_approve')),
            ]):
                raise UserError(_(
                    'Ya existe un presupuesto en borrador o pendiente de aprobación '
                    'para esta empresa y año. Apruébelo antes de registrar otro rubro.'
                ))
            new_periods.add(period)
        # Las líneas anidadas no deben llamar a la API una vez por cada fila;
        # consultar una sola vez tras guardar el presupuesto completo.
        budgets = super(ExpenseBudget, self.with_context(
            skip_expense_budget_consumption_on_save=True,
        )).create(vals_list)
        if not self.env.context.get('skip_expense_budget_consumption_on_save'):
            lines = budgets.mapped('line_ids')
            if lines:
                self.env['expense.budget.inventory.sync']._sync_saved_lines(lines)
        return budgets

    def write(self, vals):
        if 'category_id' in vals:
            if any(rec.state != 'draft' or rec.line_ids for rec in self):
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
                # Permitir al registrador editar únicamente el consumo de líneas
                # existentes, incluso si el presupuesto está enviado/aprobado.
                commands = vals.get('line_ids', ()) if set(vals) == {'line_ids'} else ()
                just_actual = bool(commands) and all(
                    isinstance(command, (tuple, list)) and len(command) >= 3 and
                    command[0] == 1 and isinstance(command[2], dict) and
                    set(command[2]) == {'actual_amount'} and
                    all(command[1] in rec.line_ids.ids for rec in self)
                    for command in commands
                )
                if not (just_actual and self.env.user.has_group(
                        'expense_budget_control.group_expense_budget_registrar')):
                    raise UserError(_('Solo puede editar el consumido de presupuestos enviados o aprobados.'))
        if ('year' in vals or 'company_id' in vals) and any(
            rec.state != 'draft' or rec.line_ids for rec in self
        ):
            raise UserError(_('No puede cambiar el año o la empresa de un presupuesto con líneas o aprobado.'))
        result = super(ExpenseBudget, self.with_context(
            skip_expense_budget_consumption_on_save=True,
        )).write(vals)
        # Guardar otras opciones o aprobar no provoca consultas al ERP.
        if ('line_ids' in vals and self and
                not self.env.context.get('skip_expense_budget_consumption_on_save')):
            lines = self.mapped('line_ids')
            if lines:
                self.env['expense.budget.inventory.sync']._sync_saved_lines(lines)
        return result

    def action_submit(self):
        """El registrador envía el borrador a revisión, sin poder aprobarlo."""
        if not (self.env.su or self.env.user.has_group(
                'expense_budget_control.group_expense_budget_registrar') or
                self.env.user.has_group('expense_budget_control.group_expense_budget_manager')):
            raise AccessError(_('Solo Registro de presupuestos o Administrador pueden enviar a aprobar.'))
        self.check_access('write')
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Solo se pueden enviar a aprobación presupuestos en borrador.'))
            if not rec.line_ids:
                raise UserError(_('Debe cargar al menos una línea presupuestaria.'))
        # Única elevación de privilegios: transición controlada de estado.
        self.sudo().write({'state': 'to_approve'})
        return True

    def action_approve(self):
        # Los botones no constituyen una barrera de seguridad: validar el grupo
        # también en Python antes de elevar privilegios para el cambio de estado.
        is_manager = self.env.su or self.env.user.has_group(
            'expense_budget_control.group_expense_budget_manager')
        is_approver = self.env.user.has_group(
            'expense_budget_control.group_expense_budget_approver')
        if not (is_manager or is_approver):
            raise AccessError(_('Solo el aprobador o el administrador pueden aprobar presupuestos.'))
        self.check_access('read')  # Incluye las reglas multiempresa de Odoo 18.
        for rec in self:
            if rec.state != 'to_approve':
                raise UserError(_('Solo puede aprobar presupuestos enviados a aprobación.'))
            if not rec.line_ids:
                raise UserError(_('Debe cargar al menos una línea presupuestaria.'))
            if not is_manager and rec.create_uid == self.env.user:
                raise AccessError(_('No puede aprobar un presupuesto registrado por usted mismo.'))
        # El aprobador no tiene permisos genéricos de escritura: únicamente
        # esta acción controlada eleva permisos para modificar el estado.
        self.sudo().write({'state': 'approved'})

    def action_reject(self):
        """Rechazo controlado por Aprobador o Administrador, sin devolver a borrador."""
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
            if not is_manager and rec.create_uid == self.env.user:
                raise AccessError(_('No puede rechazar un presupuesto creado por usted mismo.'))
        self.sudo().write({'state': 'rejected'})
        return True

    def action_reopen(self):
        if not (self.env.su or self.env.user.has_group(
            'expense_budget_control.group_expense_budget_manager')):
            raise AccessError(_('Solo el administrador puede volver el presupuesto a borrador.'))
        for rec in self:
            if self.search_count([
                ('id', '!=', rec.id), ('company_id', '=', rec.company_id.id),
                ('year', '=', rec.year), ('state', 'in', ('draft', 'to_approve')),
            ]):
                raise UserError(_(
                    'Existe otro presupuesto en preparación para esta empresa y año. '
                    'No puede volver este presupuesto a borrador todavía.'
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
            self.company_id, year=self.year,
        )
        return self.env['expense.budget.inventory.sync']._notification(result)


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

    erp_subcenter_codes = fields.Char(
        string='Subcentro', compute='_compute_erp_subcenter_codes', readonly=True,
        help='Subcentro(s) reales devueltos por getconsumosgastos/2, obtenidos '
             'de los gastos vinculados a esta cuenta, centro, año y mes. '
             'Si el ERP devuelve varios subcentros, se muestran separados por comas.',
    )
    # El rubro se elige primero en la línea, para filtrar las cuentas controladas.
    # El dato persistente sigue reflejando el rubro real de la cuenta. No hacer
    # writable el antiguo related: eso cambiaría el rubro de la cuenta completa.
    category_id = fields.Many2one(
        'expense.budget.category', string='Rubro',
        compute='_compute_category_id', inverse='_inverse_category_id',
        store=True, readonly=False, index=True, check_company=True,
    )

    @api.depends('account_id', 'account_id.category_id')
    def _compute_category_id(self):
        for line in self:
            line.category_id = line.account_id.category_id if line.account_id else False

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

    @api.onchange('account_id')
    def _onchange_account_id(self):
        for line in self:
            if line.account_id:
                line.category_id = line.account_id.category_id
                centers = line.account_id.cost_center_ids
                if not line.cost_center_id and len(centers) == 1:
                    line.cost_center_id = centers.id
    year = fields.Integer(string='Año', related='budget_id.year', store=True, index=True,
                          aggregator='max')
    month = fields.Selection(MONTHS, string='Mes', required=True, index=True)
    planned_amount = fields.Monetary(string='Proyectado', required=True, default=0,
                                     currency_field='currency_id')
    expense_ids = fields.One2many('expense.budget.expense', 'budget_line_id', string='Gastos reales')
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
            CREATE UNIQUE INDEX IF NOT EXISTS expense_budget_line_cc_sub_month_uniq
            ON expense_budget_line (budget_id, account_id, month,
                COALESCE(cost_center_id, 0), COALESCE(subcenter_code, ''))
        ''')

    def _period_expenses(self):
        """Solo gastos con la cuenta, centro, mes y año exactos del presupuesto.

        También evita mostrar consumos en un mes erróneo si una versión previa
        dejó un vínculo histórico incoherente. Las líneas antiguas con filtro
        de subcentro siguen restringiendo ese código.
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
            expense.date.month == month and
            (not self.subcenter_code or
             (expense.subcenter_code or '').strip().upper() == self.subcenter_code)
        ))

    @api.depends('expense_ids.subcenter_code', 'expense_ids.date',
                 'expense_ids.account_id', 'expense_ids.cost_center_id',
                 'account_id', 'cost_center_id', 'month', 'budget_id.year',
                 'subcenter_code')
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
                 'month', 'budget_id.year', 'subcenter_code')
    def _compute_actual_amount(self):
        for rec in self:
            rec.actual_amount = sum(rec._period_expenses().mapped('amount')) + rec.manual_actual_amount

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

    @api.constrains('cost_center_id', 'account_id', 'budget_id', 'month', 'subcenter_code')
    def _check_cost_center_and_uniqueness(self):
        for rec in self:
            if rec.cost_center_id and rec.cost_center_id.company_id != rec.company_id:
                raise ValidationError(_('El centro de costo debe pertenecer a la empresa del presupuesto.'))
            if rec.budget_id and rec.account_id and rec.month:
                duplicate = self.sudo().search([
                    ('id', '!=', rec.id), ('budget_id', '=', rec.budget_id.id),
                    ('account_id', '=', rec.account_id.id), ('month', '=', rec.month),
                    ('cost_center_id', '=', rec.cost_center_id.id or False),
                    ('subcenter_code', '=', rec.subcenter_code or False),
                ], limit=1)
                if duplicate:
                    raise ValidationError(_(
                        'Ya existe una proyección para esta cuenta, mes y centro de costo.'
                    ))

    @api.constrains('account_id', 'budget_id')
    def _check_account_company(self):
        for rec in self:
            if rec.account_id.company_id != rec.budget_id.company_id:
                raise ValidationError(_('La cuenta debe pertenecer a la empresa del presupuesto.'))

    @api.constrains('budget_id', 'account_id', 'month', 'cost_center_id', 'subcenter_code')
    def _check_unique_account_month_across_budgets(self):
        # Una cuenta/mes no debe duplicarse en distintos presupuestos del
        # mismo año, para no imputar un consumo en dos rubros diferentes.
        for rec in self:
            existing = self.sudo().search([
                ('id', '!=', rec.id),
                ('budget_id', '!=', rec.budget_id.id),
                ('budget_id.company_id', '=', rec.budget_id.company_id.id),
                ('budget_id.year', '=', rec.budget_id.year),
                ('account_id', '=', rec.account_id.id),
                ('month', '=', rec.month),
                ('cost_center_id', '=', rec.cost_center_id.id or False),
                ('subcenter_code', '=', rec.subcenter_code or False),
            ], limit=1)
            if existing:
                raise ValidationError(_(
                    'Esta cuenta y centro de costo ya están presupuestados para el mismo mes y año '
                    'en otro presupuesto de la empresa.'
                ))

    @api.model_create_multi
    def create(self, vals_list):
        budgets = self.env['expense.budget']
        for vals in vals_list:
            if 'subcenter_code' in vals:
                vals['subcenter_code'] = (vals['subcenter_code'] or '').strip().upper() or False
            budget = budgets.browse(vals.get('budget_id'))
            if budget.exists() and budget.state != 'draft':
                raise UserError(_('Solo puede modificar proyecciones en presupuestos borrador.'))
        records = super().create(vals_list)
        records._assign_unmatched_expenses()
        if not self.env.context.get('skip_expense_budget_consumption_on_save'):
            self.env['expense.budget.inventory.sync']._sync_saved_lines(records)
        return records

    def write(self, vals):
        if 'subcenter_code' in vals:
            vals = dict(vals, subcenter_code=(vals['subcenter_code'] or '').strip().upper() or False)
        protected = {'account_id', 'cost_center_id', 'subcenter_code', 'budget_id', 'month', 'planned_amount'}
        if protected.intersection(vals) and any(rec.budget_id.state != 'draft' for rec in self):
            raise UserError(_('No puede cambiar proyecciones de presupuestos pendientes de aprobación o aprobados.'))
        if {'account_id', 'cost_center_id', 'subcenter_code', 'budget_id', 'month'}.intersection(vals) and any(rec.expense_ids for rec in self):
            raise UserError(_('No puede cambiar cuenta, mes o presupuesto de una línea con gastos reales. '
                              'Puede modificar el monto proyectado o volver a conciliar los movimientos.'))
        result = super().write(vals)
        if {'account_id', 'cost_center_id', 'subcenter_code', 'budget_id', 'month'}.intersection(vals):
            self._assign_unmatched_expenses()
        if ({'account_id', 'cost_center_id', 'subcenter_code', 'budget_id', 'month', 'planned_amount'} & set(vals)
                and not self.env.context.get('skip_expense_budget_consumption_on_save')):
            self.env['expense.budget.inventory.sync']._sync_saved_lines(self)
        return result

    def unlink(self):
        if any(rec.budget_id.state != 'draft' for rec in self):
            raise UserError(_('Solo puede eliminar líneas de presupuestos borrador.'))
        return super().unlink()

    def _assign_unmatched_expenses(self):
        Expense = self.env['expense.budget.expense'].sudo()
        for line in self:
            year, month = line.budget_id.year, int(line.month)
            start = date(year, month, 1)
            end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
            expenses = Expense.search([
                ('company_id', '=', line.company_id.id),
                ('account_id', '=', line.account_id.id),
                ('cost_center_id', '=', line.cost_center_id.id or False),
                ('date', '>=', fields.Date.to_string(start)),
                ('date', '<', fields.Date.to_string(end)),
            ])
            for expense in expenses:
                target = Expense._find_budget_line(
                    expense.company_id.id, expense.account_id.id, expense.date,
                    expense.cost_center_id.id, expense.subcenter_code,
                )
                if target == line and expense.budget_line_id != line:
                    expense.write({'budget_line_id': line.id})
