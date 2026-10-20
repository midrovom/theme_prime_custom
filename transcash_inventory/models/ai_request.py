# -*- coding: utf-8 -*-
from odoo import fields, models


class TranscashAIRequest(models.Model):
    _name = 'transcash.inventory.ai.request'
    _description = 'Control de consumo de IA Transcash (sin guardar preguntas)'
    _order = 'create_date desc'
    user_id = fields.Many2one('res.users', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one('res.company', required=True, ondelete='cascade', index=True)
