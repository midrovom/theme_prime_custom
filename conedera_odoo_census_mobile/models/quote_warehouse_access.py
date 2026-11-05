from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class CatastroQuoteWarehouseAccess(models.Model):
    _name = "catastro.quote.warehouse.access"
    _description = "Bodega autorizada para cotizar desde Catastro PWA"
    _rec_name = "warehouse_id"
    _order = "user_id, company_id, warehouse_id"

    user_id = fields.Many2one("res.users", string="Usuario", required=True, ondelete="cascade", index=True)
    warehouse_id = fields.Many2one("stock.warehouse", string="Bodega autorizada", required=True,
                                   ondelete="cascade", index=True)
    company_id = fields.Many2one("res.company", string="Empresa", related="warehouse_id.company_id",
                                 readonly=True, store=True)

    _sql_constraints = [
        ("user_warehouse_unique", "unique(user_id, warehouse_id)",
         "La bodega ya está asignada a este usuario."),
    ]

    @api.constrains("user_id", "warehouse_id")
    def _check_user_company(self):
        for record in self:
            if record.warehouse_id.company_id not in record.user_id.company_ids:
                raise ValidationError(_("La bodega debe pertenecer a una compañía permitida para el usuario."))


class CatastroQuoteWarehousesUser(models.Model):
    _inherit = "res.users"

    # Un único formulario por usuario y múltiples líneas de bodegas.
    # Reutiliza los registros existentes: no hay migración ni pérdida de asignaciones.
    catastro_quote_warehouse_access_ids = fields.One2many(
        "catastro.quote.warehouse.access", "user_id",
        string="Bodegas autorizadas para cotizar",
    )
