from odoo import _, fields, models


class PricelistERPPolicy(models.Model):
    _inherit = 'product.pricelist'

    catastro_access_restricted = fields.Boolean(
        string='Restringir esta lista a usuarios autorizados', default=False,
        help='Si se activa, solo los usuarios seleccionados podrán consultar esta lista de precios. '
             'No cambia sus precios, moneda ni reglas nativas.')
    catastro_allowed_user_ids = fields.Many2many(
        'res.users', 'catastro_erp_pricelist_user_rel',
        'pricelist_id', 'user_id', string='Usuarios autorizados',
        domain=[('share', '=', False)])

    def action_catastro_excel_import(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'res_model': 'catastro.erp.excel.import.wizard',
            'name': _('Importar precios ERP'), 'view_mode': 'form', 'target': 'new',
            'context': {
                'default_import_kind': 'pricelist', 'default_pricelist_id': self.id,
                'default_company_id': self.company_id.id or self.env.company.id,
                'default_currency_id': self.currency_id.id,
            },
        }


class PriceItemERPPolicy(models.Model):
    _inherit = 'product.pricelist.item'

    catastro_excel_managed = fields.Boolean(
        string='Gestionado por Excel ERP', default=False, copy=False, index=True)


class LoyaltyProgramERPPolicy(models.Model):
    _inherit = 'loyalty.program'

    catastro_erp_batch_key = fields.Char(
        string='Identificador de política ERP', copy=False, index=True, readonly=True)

    def action_catastro_excel_policy_import(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'res_model': 'catastro.erp.excel.import.wizard',
            'name': _('Importar política SKU por porcentaje'), 'view_mode': 'form', 'target': 'new',
            'context': {
                'default_import_kind': 'policy',
                'default_company_id': self.company_id.id or self.env.company.id,
                'default_campaign_name': self.name,
            },
        }

    def action_catastro_excel_rules_import(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'res_model': 'catastro.erp.excel.import.wizard',
            'name': _('Importar SKU de reglas'), 'view_mode': 'form', 'target': 'new',
            'context': {'default_import_kind': 'rule', 'default_program_id': self.id,
                        'default_company_id': self.company_id.id or self.env.company.id},
        }

    def action_catastro_excel_rewards_import(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'res_model': 'catastro.erp.excel.import.wizard',
            'name': _('Importar SKU de recompensas'), 'view_mode': 'form', 'target': 'new',
            'context': {'default_import_kind': 'reward', 'default_program_id': self.id,
                        'default_company_id': self.company_id.id or self.env.company.id},
        }


class LoyaltyRuleERPPolicy(models.Model):
    _inherit = 'loyalty.rule'

    def action_catastro_excel_import(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'res_model': 'catastro.erp.excel.import.wizard',
            'name': _('Importar SKU para regla'), 'view_mode': 'form', 'target': 'new',
            'context': {'default_import_kind': 'rule', 'default_rule_id': self.id,
                        'default_program_id': self.program_id.id,
                        'default_company_id': self.company_id.id or self.env.company.id},
        }


class LoyaltyRewardERPPolicy(models.Model):
    _inherit = 'loyalty.reward'

    def action_catastro_excel_import(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'res_model': 'catastro.erp.excel.import.wizard',
            'name': _('Importar SKU para recompensa'), 'view_mode': 'form', 'target': 'new',
            'context': {'default_import_kind': 'reward', 'default_reward_id': self.id,
                        'default_program_id': self.program_id.id,
                        'default_company_id': self.company_id.id or self.env.company.id},
        }
