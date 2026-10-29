import base64
from odoo import fields, models, _
from odoo.exceptions import ValidationError
from ..services.xlsx_reader import MAX_FILE


class DispatchImportWizard(models.TransientModel):
    _name = "dispatch.import.wizard"
    _description = "Importar análisis de despachos"

    source_id = fields.Many2one("dispatch.source", required=True, default=lambda s: s.env["dispatch.source"].search([("company_id", "=", s.env.company.id)], limit=1))
    cutoff_date = fields.Date(required=True, default=fields.Date.context_today, string="Fecha de corte del exportador")
    file = fields.Binary(required=True, attachment=False, string="Archivo Excel")
    file_name = fields.Char(required=True)

    def action_import(self):
        self.ensure_one()
        self.source_id._check_operator()
        if not self.file_name.lower().endswith(".xlsx"):
            raise ValidationError(_("Suba un archivo .xlsx."))
        if len(base64.b64decode(self.file)) > MAX_FILE:
            raise ValidationError(_("El archivo supera 40 MiB."))
        snapshot = self.env["dispatch.snapshot"].create({"name": "%s · %s" % (self.source_id.name, self.cutoff_date),
            "source_id": self.source_id.id, "company_id": self.source_id.company_id.id,
            "cutoff_date": self.cutoff_date, "input_type": "xlsx", "file_name": self.file_name,
            "raw_file": self.file, "state": "queued"})
        self.env.ref("transcash_dispatch_analysis.cron_dispatch_import")._trigger()
        return {"type": "ir.actions.act_window", "res_model": "dispatch.snapshot", "res_id": snapshot.id, "view_mode": "form"}
