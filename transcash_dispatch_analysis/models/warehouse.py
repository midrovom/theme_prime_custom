from odoo import api, fields, models
from ..services.engine import normalize


class DispatchWarehouse(models.Model):
    _name = "dispatch.warehouse"
    _description = "Bodega del sistema de origen"
    _order = "name, code"

    name = fields.Char(string="Bodega", required=True)
    code = fields.Char(string="Código", required=True, index=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda s:s.env.company, index=True)
    _sql_constraints = [("warehouse_company_code", "unique(company_id,code)", "El código de bodega ya existe en esta compañía.")]

    @api.model
    def _ensure_records(self, company, rows):
        self.env.cr.execute("SELECT pg_advisory_xact_lock(%s,%s)", (180108,company.id))
        labels = {}
        for row in rows:
            code = normalize(row.get("CodBodega") or row.get("Bodega"))
            if code:
                labels[code] = str(row.get("Bodega") or row.get("CodBodega")).strip()
        records = self.sudo().search([("company_id","=",company.id),("code","in",list(labels))])
        found = {record.code:record.id for record in records}
        missing = [{"company_id":company.id,"code":code,"name":name} for code,name in labels.items() if code not in found]
        if missing:
            found.update({record.code:record.id for record in self.sudo().create(missing)})
        return found
