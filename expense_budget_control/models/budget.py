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
    account_ids = fields.One2many('expense.budget.account', 'category_id', string='Cuentas')
    # Selector de cuentas existentes. El vínculo persistente sigue siendo
    # expense.budget.account.category_id, de modo que Excel, informes y gastos
    # consultan exactamente los mismos datos (sin tabla paralela de relaciones).
    account_selection_ids = fields.Many2many(
        'expense.budget.account', string='Cuentas controladas',
        compute='_compute_account_selection_ids', inverse='_inverse_account_selection_ids',
        help='Seleccione varias cuentas existentes de la empresa. Una cuenta puede pertenecer a un solo rubro; si ya pertenece a otro, solo se reasignará si no tiene movimientos ni proyecciones.',
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
            # Evitar mover cuentas con histórico para no alterar informes.
            reassigned = added.filtered(lambda account: account.category_id)
            if reassigned and (self.env['expense.budget.line'].sudo().search_count([
                    ('account_id', 'in', reassigned.ids),
            ]) or self.env['expense.budget.expense'].sudo().search_count([
                    ('account_id', 'in', reassigned.ids),
            ])):
                raise ValidationError(_(
                    'No puede cambiar de rubro una cuenta que ya tiene '
                    'proyecciones o gastos registrados. '
                    'Seleccione una cuenta sin movimientos.'
                ))
            # No dejar presupuestos históricos apuntando a una cuenta desligada
            # de su rubro: solo se pueden quitar cuentas nunca presupuestadas.
            if removed and (self.env['expense.budget.line'].sudo().search_count([
                ('account_id', 'in', removed.ids),
            ]) or self.env['expense.budget.expense'].sudo().search_count([
                ('account_id', 'in', removed.ids),
            ])):
                raise ValidationError(_(
                    'No puede quitar una cuenta que ya tiene proyecciones o gastos registrados.'
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

    # El nombre sigue siendo texto para mantener los reportes e integraciones
    # existentes, pero la interfaz selecciona un rubro ya registrado.
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

    @api.onchange('category_id')
    def _onchange_budget_category(self):
        # El nombre visible e impreso seguirá correspondiendo al rubro elegido.
        if self.category_id:
            self.name = self.category_id.name

    @api.onchange('company_id')
    def _onchange_budget_company(self):
        if self.category_id and self.category_id.company_id != self.company_id:
            self.category_id = False
            self.name = False

    @api.constrains('category_id', 'company_id')
    def _check_budget_category_company(self):
        for rec in self:
            if rec.category_id and rec.category_id.company_id != rec.company_id:
                raise ValidationError(_('El rubro del presupuesto debe pertenecer a su empresa.'))
            if rec.category_id and any(
                    line.account_id.category_id != rec.category_id for line in rec.line_ids):
                raise ValidationError(_(
                    'Las cuentas de las proyecciones deben pertenecer al rubro del presupuesto.'
                ))

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
        return super().create(vals_list)

    def write(self, vals):
        if 'category_id' in vals:
            if any(rec.state != 'draft' or rec.line_ids for rec in self):
                raise UserError(_('No puede cambiar el rubro de un presupuesto con líneas o enviado.'))
            vals = dict(vals)
            category = self.env['expense.budget.category'].browse(vals['category_id']).exists()
            if category:
                if any(rec.company_id != category.company_id for rec in self) and 'company_id' not in vals:
                    raise ValidationError(_('El rubro debe pertenecer a la empresa del presupuesto.'))
                vals['name'] = category.name
            # No se cambia ni se borra el nombre histórico si se limpia el selector.
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
        return super().write(vals)

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
            index = {(line.account_id.id, line.month): line for line in budget.line_ids}
            expenses = self.env['expense.budget.expense'].search([
                ('company_id', '=', budget.company_id.id),
                ('date', '>=', '%04d-01-01' % budget.year),
                ('date', '<=', '%04d-12-31' % budget.year),
                ('budget_line_id', '=', False),
            ])
            for expense in expenses:
                line = index.get((expense.account_id.id, str(expense.date.month)))
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
        result = self.env['expense.budget.api.sync']._sync_company(self.company_id)
        return self.env['expense.budget.api.sync']._notification(result)


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
    category_id = fields.Many2one('expense.budget.category', related='account_id.category_id',
                                  store=True, string='Rubro', index=True)
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
        ('budget_month_account_unique', 'unique(budget_id, account_id, month)',
         'Solo puede existir una proyección para cada cuenta y mes del presupuesto.'),
        ('planned_amount_nonnegative', 'check(planned_amount >= 0)',
         'La proyección no puede ser negativa.'),
    ]

    @api.depends('expense_ids.amount', 'manual_actual_amount')
    def _compute_actual_amount(self):
        for rec in self:
            rec.actual_amount = sum(rec.expense_ids.mapped('amount')) + rec.manual_actual_amount

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
            rec.manual_actual_amount = rec.actual_amount - sum(rec.expense_ids.mapped('amount'))

    @api.constrains('account_id', 'budget_id')
    def _check_account_company(self):
        for rec in self:
            if rec.account_id.company_id != rec.budget_id.company_id:
                raise ValidationError(_('La cuenta debe pertenecer a la empresa del presupuesto.'))
            if (rec.budget_id.category_id and
                    rec.account_id.category_id != rec.budget_id.category_id):
                raise ValidationError(_('La cuenta debe pertenecer al rubro seleccionado en el presupuesto.'))

    @api.constrains('budget_id', 'account_id', 'month')
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
            ], limit=1)
            if existing:
                raise ValidationError(_(
                    'Esta cuenta ya está presupuestada para el mismo mes y año '
                    'en otro presupuesto de la empresa.'
                ))

    @api.model_create_multi
    def create(self, vals_list):
        budgets = self.env['expense.budget']
        for vals in vals_list:
            budget = budgets.browse(vals.get('budget_id'))
            if budget.exists() and budget.state != 'draft':
                raise UserError(_('Solo puede modificar proyecciones en presupuestos borrador.'))
        records = super().create(vals_list)
        records._assign_unmatched_expenses()
        return records

    def write(self, vals):
        protected = {'account_id', 'budget_id', 'month', 'planned_amount'}
        if protected.intersection(vals) and any(rec.budget_id.state != 'draft' for rec in self):
            raise UserError(_('No puede cambiar proyecciones de presupuestos pendientes de aprobación o aprobados.'))
        if {'account_id', 'budget_id', 'month'}.intersection(vals) and any(rec.expense_ids for rec in self):
            raise UserError(_('No puede cambiar cuenta, mes o presupuesto de una línea con gastos reales. '
                              'Puede modificar el monto proyectado o volver a conciliar los movimientos.'))
        result = super().write(vals)
        if {'account_id', 'budget_id', 'month'}.intersection(vals):
            self._assign_unmatched_expenses()
        return result

    def unlink(self):
        if any(rec.budget_id.state != 'draft' for rec in self):
            raise UserError(_('Solo puede eliminar líneas de presupuestos borrador.'))
        return super().unlink()

    def _assign_unmatched_expenses(self):
        Expense = self.env['expense.budget.expense']
        for line in self:
            year, month = line.budget_id.year, int(line.month)
            start = date(year, month, 1)
            end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
            Expense.sudo().search([
                ('company_id', '=', line.company_id.id),
                ('account_id', '=', line.account_id.id),
                ('date', '>=', fields.Date.to_string(start)),
                ('date', '<', fields.Date.to_string(end)),
                ('budget_line_id', '=', False),
            ]).write({'budget_line_id': line.id})
