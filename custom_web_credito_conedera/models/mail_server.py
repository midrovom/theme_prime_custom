# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class IrMailServer(models.Model):
    _inherit = 'ir.mail_server'

    is_credit_server = fields.Boolean(
        string='Correo de crédito',
        help='Use this SMTP server exclusively for emails sent by the CONEDERA credit portal.',
    )

    @api.constrains('is_credit_server')
    def _check_single_conedera_credit_server(self):
        for server in self.filtered('is_credit_server'):
            other_count = self.sudo().search_count([
                ('is_credit_server', '=', True),
                ('id', '!=', server.id),
            ])
            if other_count:
                raise ValidationError(_(
                    'Solo puede marcarse un servidor SMTP con la opción "Correo de crédito".'
                ))

    @api.model
    def get_conedera_credit_mail_server(self):
        """Return the SMTP server reserved for credit emails, never the HR server."""
        servers = self.sudo().search([('is_credit_server', '=', True)], limit=2)
        if not servers:
            raise UserError(_(
                'No existe un servidor SMTP marcado como "Correo de crédito". '
                'Configure esa opción en Ajustes > Técnico > Correo > Servidores de correo saliente.'
            ))
        if len(servers) > 1:
            raise UserError(_(
                'Hay más de un servidor SMTP marcado como "Correo de crédito". '
                'Deje seleccionado solamente uno.'
            ))
        if not (servers.smtp_user or '').strip():
            raise UserError(_(
                'El servidor SMTP marcado como "Correo de crédito" no tiene configurado el usuario SMTP (smtp_user).'
            ))
        return servers
