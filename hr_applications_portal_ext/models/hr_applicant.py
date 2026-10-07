from odoo import api, fields, models
from odoo.http import request

class HrApplicant(models.Model):
    _inherit = "hr.applicant"

    portal_user_id = fields.Many2one(
        "res.users", string="Usuario Portal", index=True,
        ondelete="set null", copy=False
    )
    phase_1_completed = fields.Boolean(string="Fase 1 completada", default=False, copy=False)
    phase_2_completed = fields.Boolean(string="Fase 2 completada", default=False, copy=False)
    phase_3_completed = fields.Boolean(string="Fase 3 completada", default=False, copy=False)
    form2_portal_enabled = fields.Boolean(
        string="Formulario 2 habilitado en portal",
        default=False,
        copy=False,
        help="Se activa automáticamente cuando la postulación entra en la etapa con secuencia 3 (Ficha Tecnica).",
    )

    @api.model_create_multi
    def create(self, vals_list):
        if self.env.user.has_group("base.group_portal"):
            for vals in vals_list:
                vals.setdefault("portal_user_id", self.env.user.id)

        # El controlador nativo espera índices 0, 1 y 2 para las referencias.
        # Capturamos tanto los comandos one2many que lleguen en vals como los
        # campos enviados por /jobs/submit, para que la extensión sea tolerante
        # a ambas formas sin modificar el controlador nativo.
        reference_payloads = []
        http_reference_payload = []
        try:
            form = request.httprequest.form
            for idx in range(0, 3):
                nombre = form.get(f"ref_nombre_{idx}")
                if nombre is not None:
                    http_reference_payload.append({
                        "nombre": nombre,
                        "domicilio": form.get(f"ref_domicilio_{idx}") or "",
                        "telefono": form.get(f"ref_telefono_{idx}") or "",
                        "ocupacion": form.get(f"ref_ocupacion_{idx}") or "",
                        "tiempo_conocerlo": form.get(f"ref_tiempo_{idx}") or "",
                    })
            # También aceptamos temporalmente el formato 1..3 por si otro
            # asset deja esos nombres en el DOM al momento del submit.
            if not http_reference_payload:
                for idx in range(1, 4):
                    nombre = form.get(f"ref_nombre_{idx}")
                    if nombre is not None:
                        http_reference_payload.append({
                            "nombre": nombre,
                            "domicilio": form.get(f"ref_domicilio_{idx}") or "",
                            "telefono": form.get(f"ref_telefono_{idx}") or "",
                            "ocupacion": form.get(f"ref_ocupacion_{idx}") or "",
                            "tiempo_conocerlo": form.get(f"ref_tiempo_{idx}") or "",
                        })
        except Exception:
            http_reference_payload = []

        for vals in vals_list:
            commands = vals.get("reference_ids") or []
            extracted = []
            for command in commands:
                if (isinstance(command, (list, tuple)) and len(command) >= 3
                        and command[0] == 0 and isinstance(command[2], dict)):
                    extracted.append(dict(command[2]))
            reference_payloads.append(extracted or list(http_reference_payload))

        records = super().create(vals_list)

        # Persistencia de respaldo de referencias. El nativo puede no construir
        # reference_ids cuando recibe los índices 1..3; en ese caso recuperamos
        # los valores del request y creamos únicamente las líneas faltantes.
        for record, refs in zip(records, reference_payloads):
            if not refs:
                continue
            existing = {
                (ref.nombre, ref.domicilio, ref.telefono, ref.ocupacion, ref.tiempo_conocerlo)
                for ref in record.reference_ids
            }
            missing = []
            for ref in refs:
                key = (
                    ref.get("nombre"), ref.get("domicilio"), ref.get("telefono"),
                    ref.get("ocupacion"), ref.get("tiempo_conocerlo")
                )
                if key[0] and key not in existing:
                    missing.append(ref)
                    existing.add(key)
            if missing:
                self.env["applicant.reference"].sudo().create([
                    dict(ref, applicant_id=record.id) for ref in missing
                ])

        records._enable_form2_when_stage_3()
        return records

    def write(self, vals):
        result = super().write(vals)
        if "stage_id" in vals:
            self._enable_form2_when_stage_3()
        return result

    def _enable_form2_when_stage_3(self):
        """Habilita el Formulario 2 cuando la postulación entra en secuencia 3."""
        for record in self.sudo():
            if record.stage_id and record.stage_id.sequence == 3 and not record.form2_portal_enabled:
                record.with_context(skip_form2_stage_trigger=True).write({
                    "form2_portal_enabled": True,
                })

    def _portal_can_continue_form2(self, user=None):
        user = user or self.env.user
        return bool(
            self._portal_can_access(user)
            and self.form2_portal_enabled
            and not self.phase_2_completed
        )

    def _portal_can_access(self, user=None):
        user = user or self.env.user
        return bool(user and user.has_group("base.group_portal") and
                    all(rec.portal_user_id.id == user.id for rec in self))

    def _complete_phase_2(self):
        self.ensure_one()
        if not self._portal_can_access():
            return False
        # La identidad/propiedad se valida antes; la escritura se hace con
        # sudo para evitar que Odoo intente resolver permisos de etapas de
        # reclutamiento al actualizar el hr.applicant desde Portal.
        self.sudo().write({"phase_2_completed": True})
        return True
