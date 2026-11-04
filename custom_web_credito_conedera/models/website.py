# -*- coding: utf-8 -*-
"""Configuración del sitio que solicita login antes de la ficha."""
import unicodedata

from odoo import fields, models


class Website(models.Model):
    _inherit = 'website'

    conedera_credit_login_home = fields.Boolean(
        string='Abrir login al entrar a este sitio web',
        help=('Si está marcado, la página principal de este sitio redirige '
              'a los visitantes sin sesión al acceso de Odoo y, después de '
              'autenticarse, abre la solicitud de crédito. Los demás sitios '
              'web no se ven afectados.'),
        default=False,
    )

    def _is_conedera_credit_login_home(self):
        self.ensure_one()
        if self.conedera_credit_login_home:
            return True
        # Compatibilidad con el nombre solicitado para el sitio independiente:
        # el ajuste se aplica automáticamente a ese sitio, nunca a todas las webs.
        normalized = unicodedata.normalize('NFKD', self.name or '')
        normalized = ''.join(char for char in normalized if not unicodedata.combining(char))
        normalized = ' '.join(normalized.casefold().split())
        return normalized in (
            'solicitud de credito',
            'solicitud de credito conedera',
            'credito conedera',
        )
