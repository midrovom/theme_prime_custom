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

    def test_03_portal_user_cannot_see_other_users_application(self):
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
