from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class CatastroQuotePaymentOption(models.Model):
    _name = 'catastro.quote.payment.option'
    _description = 'Condición de pago y recargo - Catastro PWA'
    _order = 'sequence,id'

    name = fields.Char(string='Condición de pago', required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    surcharge_percent = fields.Float(string='Recargo (%)', default=0, digits=(12, 4), required=True)
    payment_term_id = fields.Many2one('account.payment.term', string='Plazo de pago nativo')
    surcharge_product_id = fields.Many2one('product.product', string='Servicio de recargo anterior (no se usa en nuevas proformas)', help='Campo conservado para compatibilidad con versiones anteriores. El recargo ahora se incorpora al precio de los productos.')

    @api.constrains('surcharge_percent', 'surcharge_product_id', 'company_id', 'payment_term_id')
    def _check_option(self):
        for r in self:
            if r.surcharge_percent < 0 or r.surcharge_percent > 100:
                raise ValidationError('El recargo debe estar entre 0% y 100%.')
            if r.surcharge_product_id:
                if r.surcharge_product_id.type != 'service' or not r.surcharge_product_id.sale_ok:
                    raise ValidationError('El producto de recargo debe ser un servicio vendible.')
                if r.surcharge_product_id.company_id and r.surcharge_product_id.company_id != r.company_id:
                    raise ValidationError('El servicio de recargo pertenece a otra empresa.')
            if r.payment_term_id and r.payment_term_id.company_id and r.payment_term_id.company_id != r.company_id:
                raise ValidationError('El plazo de pago debe pertenecer a esta empresa.')


class ResCompany(models.Model):
    _inherit = 'res.company'

    # IMPORTANT: this is deliberately NON-STORED. A new stored column on
    # res.company can be prefetched by button_install() BEFORE module upgrade
    # creates the column (UndefinedColumn during ir.module.module upgrade).
    # The per-company configuration lives in ir.config_parameter instead.
    catastro_retail_partner_id = fields.Many2one(
        'res.partner', string='Consumidor final para Catastro PWA',
        compute='_compute_catastro_retail_partner_id',
        inverse='_inverse_catastro_retail_partner_id',
        store=False,
        help='El perfil Tienda podrá crear cotizaciones únicamente a este cliente sin un catastro previo.',
    )

    @api.model
    def _catastro_retail_config_key(self, company_id):
        return 'conedera_odoo_census_mobile.retail_partner.company_%s' % company_id

    def _compute_catastro_retail_partner_id(self):
        # Support databases where v18.0.1.5.8 managed to install: read the old
        # column as a fallback until the first save. Never query it unless
        # PostgreSQL confirms the column exists.
        ids = [company.id for company in self if isinstance(company.id, int)]
        legacy = {}
        if ids:
            self.env.cr.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM pg_attribute
                     WHERE attrelid = 'res_company'::regclass
                       AND attname = 'catastro_retail_partner_id'
                       AND NOT attisdropped
                )
            """)
            if self.env.cr.fetchone()[0]:
                self.env.cr.execute(
                    'SELECT id, catastro_retail_partner_id FROM res_company WHERE id = ANY(%s)',
                    [ids],
                )
                legacy = dict(self.env.cr.fetchall())

        parameters = self.env['ir.config_parameter'].sudo()
        Partner = self.env['res.partner'].sudo()
        for company in self:
            partner_id = 0
            if isinstance(company.id, int):
                value = parameters.get_param(self._catastro_retail_config_key(company.id))
                # An explicit '0' means the setting was cleared, preventing a
                # stale old-column value from being resurrected.
                try:
                    partner_id = int(value) if value is not False and value is not None else int(legacy.get(company.id) or 0)
                except (TypeError, ValueError):
                    partner_id = 0
            company.catastro_retail_partner_id = Partner.browse(partner_id).exists() if partner_id > 0 else False

    def _inverse_catastro_retail_partner_id(self):
        from odoo.exceptions import AccessError
        if not self.env.user.has_group('base.group_system'):
            raise AccessError('Solo un administrador puede configurar el Consumidor Final por empresa.')
        parameters = self.env['ir.config_parameter'].sudo()
        for company in self:
            if not isinstance(company.id, int):
                continue
            partner = company.catastro_retail_partner_id
            if partner and partner.company_id and partner.company_id != company:
                raise ValidationError('El cliente Consumidor Final pertenece a otra empresa.')
            parameters.set_param(self._catastro_retail_config_key(company.id), str(partner.id if partner else 0))


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    catastro_payment_option_id = fields.Many2one('catastro.quote.payment.option',
        string='Condición de pago PWA', copy=False, ondelete='restrict')

    def catastro_restore_base_prices(self):
        """Restaurar precios previos al recargo para volver a calcular promociones.

        Solo en cotizaciones en borrador; evita alimentar al motor Loyalty
        precios que ya incluyen gastos financieros por forma de pago.
        """
        for order in self:
            if order.state != 'draft':
                continue
            for line in order.order_line.filtered('catastro_payment_surcharge_applied'):
                # Si una personalización modificó el precio desde entonces, no
                # sobrescribir su valor. Se tratará como nuevo precio base.
                expected = line.catastro_payment_base_price_unit + line.catastro_payment_surcharge_unit_amount
                changed = order.currency_id.compare_amounts(line.price_unit, expected) != 0
                values = {
                    'catastro_payment_surcharge_applied': False,
                    'catastro_payment_surcharge_percent': 0.0,
                    'catastro_payment_surcharge_unit_amount': 0.0,
                }
                if not changed:
                    values['price_unit'] = line.catastro_payment_base_price_unit
                line.write(values)

    def catastro_recompute_surcharge(self):
        """Aplicar el recargo *en cada precio unitario*, de forma idempotente.

        La lista de precios, negotiable_price, impuestos y promociones se
        calculan primero en Odoo. El recargo no forma parte de la negociación,
        ni genera un producto adicional: cada línea conserva base, porcentaje
        y monto unitario para auditoría. Se excluyen las recompensas Loyalty.
        """
        for order in self:
            if order.state != 'draft':
                continue
            option = order.catastro_payment_option_id
            if option and option.company_id != order.company_id:
                raise ValidationError('La condición de pago pertenece a otra empresa.')
            percent = option.surcharge_percent if option else 0.0
            # Eliminar exclusivamente las antiguas líneas de recargo creadas
            # por versiones < 18.0.1.5.10; no tocar productos ni recompensas.
            old_fees = order.order_line.filtered('is_catastro_payment_surcharge')
            if old_fees:
                old_fees.unlink()
            for line in order.order_line:
                if line.display_type or not line.product_id:
                    continue
                if ('reward_id' in line._fields and line.reward_id) or (
                    'is_reward_line' in line._fields and line.is_reward_line
                ):
                    # Los premios/cupones son descuentos, nunca se recargan.
                    continue
                if line.catastro_payment_surcharge_applied:
                    expected = (line.catastro_payment_base_price_unit +
                                line.catastro_payment_surcharge_unit_amount)
                    if order.currency_id.compare_amounts(expected, line.price_unit) == 0:
                        base = line.catastro_payment_base_price_unit
                    else:
                        # El formulario nativo / un módulo externo cambió el
                        # precio después del recargo: usarlo como nueva base.
                        base = line.price_unit
                else:
                    base = line.price_unit
                unit_fee = order.currency_id.round(base * percent / 100.0)
                final = base + unit_fee
                line.write({
                    'price_unit': final,
                    'catastro_payment_base_price_unit': base,
                    'catastro_payment_surcharge_percent': percent,
                    'catastro_payment_surcharge_unit_amount': unit_fee,
                    'catastro_payment_surcharge_applied': bool(percent),
                })

    def action_confirm(self):
        # Actualizar precios y porcentajes al confirmar desde Ventas.
        # No hay línea adicional de servicio: el recargo figura en cada línea.
        self.filtered(lambda order: order.state == 'draft' and order.catastro_payment_option_id).catastro_recompute_surcharge()
        return super().action_confirm()


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    # Se conserva el indicador histórico por compatibilidad con borradores ya
    # existentes. Las nuevas proformas no crean líneas de recargo adicionales.
    is_catastro_payment_surcharge = fields.Boolean(string='Recargo por condición de pago anterior',
        copy=False, readonly=True, default=False)
    catastro_payment_base_price_unit = fields.Float(
        string='Precio unitario antes del recargo', digits='Product Price', readonly=True, copy=False)
    catastro_payment_surcharge_percent = fields.Float(
        string='Recargo de pago (%)', digits=(12, 4), readonly=True, copy=False)
    catastro_payment_surcharge_unit_amount = fields.Float(
        string='Recargo unitario aplicado', digits='Product Price', readonly=True, copy=False)
    catastro_payment_surcharge_applied = fields.Boolean(
        string='Recargo aplicado al precio', readonly=True, copy=False, default=False)
