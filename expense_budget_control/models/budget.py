# -*- coding: utf-8 -*-
from datetime import date
from time import monotonic
from uuid import uuid4
import logging

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


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

    _sql_constraints = [
        ('budget_company_year_category_unique',
         'unique(company_id, year, category_id)',
         'Ya existe un presupuesto de ese rubro para la empresa y el año seleccionados.'),
    ]

    # Distintos rubros de un año se pueden registrar simultáneamente,
    # sin esperar a que los anteriores sean aprobados.

    @api.constrains('company_id', 'year', 'category_id')
    def _check_unique_budget_per_rubro(self):
        for rec in self:
            if not rec.category_id:
                # Presupuesto legado sin rubro único: no alterar ni borrar.
                continue
            duplicate = self.sudo().search([
                ('id', '!=', rec.id),
                ('company_id', '=', rec.company_id.id),
                ('year', '=', rec.year),
                ('category_id', '=', rec.category_id.id),
            ], limit=1)
            if duplicate:
                raise ValidationError(_(
                    'Ya existe el presupuesto "%(budget)s" para el rubro "%(rubro)s" '
                    'en el año %(year)s y la empresa "%(company)s". '
                    'Solo se permite un presupuesto por rubro y año.'
                ) % {
                    'budget': duplicate.name, 'rubro': rec.category_id.display_name,
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
            key = (company_id, year, category.id)
            if key in new_keys or self.sudo().search([
                ('company_id', '=', company_id), ('year', '=', year),
                ('category_id', '=', category.id),
            ], limit=1):
                raise ValidationError(_(
                    'Ya existe un presupuesto para el rubro "%(rubro)s" en el '
                    'año %(year)s y la empresa "%(company)s". '
                    'Seleccione otro rubro o abra el presupuesto existente.'
                ) % {
                    'rubro': category.display_name, 'year': year,
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

    def write(self, vals):
        started = monotonic()
        if 'category_id' in vals:
            if not vals['category_id']:
                raise ValidationError(_('Debe seleccionar el rubro del presupuesto.'))
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
                key = (company_id, year, category_id)
                if key in changed_keys or self.sudo().search([
                    ('id', '!=', rec.id),
                    ('company_id', '=', company_id), ('year', '=', year),
                    ('category_id', '=', category_id),
                ], limit=1):
                    raise ValidationError(_(
                        'Ya existe un presupuesto para el rubro elegido en '
                        'esa empresa y año. Abra el existente o seleccione otro rubro.'
                    ))
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
        """El registrador envía el borrador a revisión, sin poder aprobarlo."""
        if not (self.env.su or self.env.user.has_group(
                'expense_budget_control.group_expense_budget_registrar') or
                self.env.user.has_group('expense_budget_control.group_expense_budget_manager')):
            raise AccessError(_('Solo Registro de presupuestos o Administrador pueden enviar a aprobar.'))
        self.check_access('write')
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Solo se pueden enviar a aprobación presupuestos en borrador.'))
            if not rec.category_id:
                raise UserError(_('Seleccione el rubro del presupuesto antes de enviarlo a aprobación.'))
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
            if not rec.category_id:
                raise UserError(_('El presupuesto debe tener un rubro antes de aprobarlo.'))
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
                ('year', '=', rec.year), ('category_id', '=', rec.category_id.id),
            ]):
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
    # Campo legado: conservar las fechas de versiones anteriores sin eliminarlas.
    # Nunca usar este dato oculto para filtrar Consumido: el criterio vigente es
    # el MES completo del año del presupuesto.
    consumption_date = fields.Date(
        string='Fecha de consumo (histórica)', index=True, copy=False,
        help='Dato histórico de versiones anteriores. El consumo actual se calcula '
             'por el mes completo y el año del presupuesto.',
    )
    month = fields.Selection(MONTHS, string='Mes', required=True, index=True)
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
                        'Ya existe una proyección para esta cuenta, centro y mes. '
                        'El consumo mensual se consolida en una única línea.'
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
            ], limit=1)
            if existing:
                raise ValidationError(_(
                    'Esta cuenta y centro ya están presupuestados para el mismo mes y año '
                    'en otro presupuesto de la empresa.'
                ))

    @api.model_create_multi
    def create(self, vals_list):
        budgets = self.env['expense.budget']
        for vals in vals_list:
            # Fecha heredada solo se permite desde integraciones antiguas:
            # no impone el mes cuando el usuario proporciona uno explícito.
            if vals.get('consumption_date') and not vals.get('month'):
                vals['month'] = str(fields.Date.to_date(vals['consumption_date']).month)
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
        # Cambiar el mes en una línea creada cuando existía el calendario
        # elimina el viejo filtro de día y fuerza una consulta mensual nueva.
        if 'month' in vals:
            vals = dict(vals, consumption_date=False)
        elif vals.get('consumption_date') and 'month' not in vals:
            vals = dict(vals, month=str(fields.Date.to_date(vals['consumption_date']).month))
        if 'subcenter_code' in vals:
            vals = dict(vals, subcenter_code=(vals['subcenter_code'] or '').strip().upper() or False)
        period_fields = {'account_id', 'cost_center_id', 'subcenter_code',
                         'subcenter_id', 'budget_id', 'month', 'consumption_date'}
        if period_fields.intersection(vals):
            vals = dict(vals, erp_checked_at=False)
        protected = {'account_id', 'cost_center_id', 'subcenter_code', 'budget_id', 'month', 'consumption_date', 'planned_amount'}
        if protected.intersection(vals) and any(rec.budget_id.state != 'draft' for rec in self):
            raise UserError(_('No puede cambiar proyecciones de presupuestos pendientes de aprobación o aprobados.'))
        # Cambiar solo la fecha de una proyección existente es seguro: la
        # reconciliación reasigna o desvincula movimientos de otros días.
        # Los cambios de cuenta/centro/subcentro siguen protegidos.
        locked_changes = {'account_id', 'cost_center_id', 'subcenter_code', 'budget_id'}.intersection(vals)
        if locked_changes and any(rec.expense_ids for rec in self):
            raise UserError(_('No puede cambiar cuenta, centro, subcentro o presupuesto de una línea con gastos reales. '
                              'Puede cambiar el mes y el sistema volverá a conciliar los movimientos.'))
        result = super().write(vals)
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
        if any(rec.budget_id.state != 'draft' for rec in self):
            raise UserError(_('Solo puede eliminar líneas de presupuestos borrador.'))
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
