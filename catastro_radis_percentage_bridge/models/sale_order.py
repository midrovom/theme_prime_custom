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

    def _catastro_radis_payment_erp_code(self):
        """Obtain the ERP identifier, never the visible name or percentage.

        An order without a PWA payment option (e.g. older native orders) is
        not modified to preserve the original Radis contract. When a PWA
        option exists, fail closed if its code is missing or from another company.
        """
        self.ensure_one()
        option = self.catastro_payment_option_id
        if not option:
            return None
        from ..radis_payload import PayloadMismatch
        if option.company_id != self.company_id:
            raise PayloadMismatch('La forma de pago no pertenece a la empresa de la proforma %s.' % self.name)
        code = (option.erp_code or '').strip()
        if not code:
            raise PayloadMismatch(
                'Configure el Código ERP en Catastro > Configuración > Condiciones de pago PWA '
                'para «%s» (proforma %s) antes de enviar a Radis.' % (option.name, self.name))
        return code

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
