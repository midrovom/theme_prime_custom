# -*- coding: utf-8 -*-
from odoo import models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _catastro_radis_bridge_version(self):
        """Señal para la PWA: el puente inyecta los porcentajes en AMBAS rutas.

        No significa que Radis receptor ya soporte las nuevas claves.
        """
        return 1

    def _radis_line_percentages_payload_version(self):
        """Compatibilidad con instalaciones que consultan el contrato de líneas."""
        return 2

    def _catastro_radis_line_percentages(self, line):
        """Porcentajes ya guardados en la línea, sin recalcular importes.

        `price_unit` incluye el incremento de pago cuando fue aplicado por
        Catastro. Radis debe tomar `increase_percent` como dato informativo:
        NO debe aplicar de nuevo ese incremento a `price_unit`.
        """
        self.ensure_one()
        increment = 0.0
        if (
            'catastro_payment_surcharge_percent' in line._fields
            and 'catastro_payment_surcharge_applied' in line._fields
            and line.catastro_payment_surcharge_applied
        ):
            increment = float(line.catastro_payment_surcharge_percent or 0.0)
        return {
            'discount_percent': round(float(line.discount or 0.0), 4),
            'increase_percent': round(increment, 4),
        }
