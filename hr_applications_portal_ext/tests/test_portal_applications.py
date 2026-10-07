from odoo.tests import TransactionCase, tagged

@tagged("post_install", "-at_install")
class TestPortalApplications(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.portal_group = cls.env.ref("base.group_portal")
        cls.portal_user = cls.env["res.users"].with_context(no_reset_password=True).create({
            "name": "Portal Applicant Test",
            "login": "portal.application.test@example.com",
            "email": "portal.application.test@example.com",
            "groups_id": [(6, 0, [cls.portal_group.id])],
        })
        cls.job = cls.env["hr.job"].create({"name": "QA Portal Test"})
        cls.applicant = cls.env["hr.applicant"].create({
            "partner_name": "Portal Applicant Test", "job_id": cls.job.id,
            "portal_user_id": cls.portal_user.id,
            "phase_1_completed": True, "phase_3_completed": True,
            "phase_2_completed": False,
        })

    def test_01_application_is_owned_by_portal_user(self):
        self.assertEqual(self.applicant.portal_user_id, self.portal_user)
        self.assertTrue(self.applicant.with_user(self.portal_user).search(
            [("id", "=", self.applicant.id)]))

    def test_02_form2_completion_updates_existing_application(self):
        medical = self.env["applicant.medical"].create({
            "applicant_id": self.applicant.id, "enfermedad_persistente": "no",
            "medicacion_continua": "no", "enfermedad_laboral": "no",
            "cirugia_realizada": "no", "discapacidad": "no", "tipo_sangre": "O+",
        })
        portal_medical = medical.with_user(self.portal_user)
        portal_applicant = self.applicant.with_user(self.portal_user)
        portal_medical.write({"tipo_sangre": "A+"})
        self.assertTrue(portal_applicant._complete_phase_2())
        self.assertEqual(portal_medical.tipo_sangre, "A+")
        self.assertTrue(portal_applicant.phase_2_completed)
        self.assertEqual(portal_applicant.id, self.applicant.id)

    def test_03_completed_form2_cannot_be_reopened_from_portal(self):
        self.applicant.write({"form2_portal_enabled": True, "phase_2_completed": False})
        portal_applicant = self.applicant.with_user(self.portal_user)

        self.assertTrue(portal_applicant._portal_can_continue_form2(self.portal_user))
        self.assertTrue(portal_applicant._complete_phase_2())
        self.assertTrue(portal_applicant.phase_2_completed)
        self.assertFalse(portal_applicant._portal_can_continue_form2(self.portal_user))

    def test_04_portal_user_cannot_see_other_users_application(self):
        other_user = self.env["res.users"].with_context(no_reset_password=True).create({
            "name": "Other Portal Applicant", "login": "other.portal.application.test@example.com",
            "email": "other.portal.application.test@example.com",
            "groups_id": [(6, 0, [self.portal_group.id])],
        })
        other_applicant = self.env["hr.applicant"].create({
            "partner_name": "Other Portal Applicant", "job_id": self.job.id,
            "portal_user_id": other_user.id,
        })
        self.assertFalse(self.env["hr.applicant"].with_user(self.portal_user).search(
            [("id", "=", other_applicant.id)]))

    def test_05_reference_lines_are_persisted_from_create_values(self):
        applicant = self.env["hr.applicant"].create({
            "partner_name": "Reference Persistence Applicant",
            "job_id": self.job.id,
            "reference_ids": [(0, 0, {
                "nombre": "Referencia Uno",
                "domicilio": "Quito",
                "telefono": "0999999999",
                "ocupacion": "Ingeniero",
                "tiempo_conocerlo": "5 años",
            })],
        })
        self.assertEqual(len(applicant.reference_ids), 1)
        self.assertEqual(applicant.reference_ids.nombre, "Referencia Uno")


class TestFichaTecnicaEnablesForm2(TransactionCase):
    def setUp(self):
        super().setUp()
        self.Stage = self.env["hr.recruitment.stage"]
        self.Applicant = self.env["hr.applicant"]
        self.stage_3 = self.Stage.create({
            "name": "Ficha Tecnica",
            "sequence": 3,
        })
        self.stage_2 = self.Stage.create({
            "name": "Etapa previa",
            "sequence": 2,
        })

    def test_entering_sequence_3_enables_form2(self):
        applicant = self.Applicant.create({
            "name": "Candidato Ficha Tecnica",
            "stage_id": self.stage_2.id,
        })
        self.assertFalse(applicant.form2_portal_enabled)

        applicant.write({"stage_id": self.stage_3.id})
        self.assertTrue(applicant.form2_portal_enabled)

    def test_applicant_created_directly_in_sequence_3_enables_form2(self):
        applicant = self.Applicant.create({
            "name": "Candidato Ficha Tecnica Directo",
            "stage_id": self.stage_3.id,
        })
        self.assertTrue(applicant.form2_portal_enabled)

    def test_leaving_sequence_3_does_not_disable_form2(self):
        applicant = self.Applicant.create({
            "name": "Candidato Ficha Tecnica",
            "stage_id": self.stage_3.id,
        })
        applicant.write({"stage_id": self.stage_2.id})
        self.assertTrue(applicant.form2_portal_enabled)
