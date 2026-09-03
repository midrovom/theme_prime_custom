from odoo.tests.common import TransactionCase


class TestDigitalTrainingCertificate(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.organization = cls.env["digital.training.organization"].create(
            {"name": "Empresa de prueba"}
        )
        cls.course = cls.env["digital.training.course"].create(
            {"name": "Conciencia Digital", "default_duration_hours": 2.0}
        )
        cls.template = cls.env.ref(
            "digital_training_certificate.default_certificate_template"
        )
        cls.event = cls.env["digital.training.event"].create(
            {
                "name": "Inducción de prueba",
                "course_id": cls.course.id,
                "duration_hours": 2.0,
                "instructor_name": "Instructor de prueba",
                "organization_ids": [(6, 0, cls.organization.ids)],
                "certificate_template_id": cls.template.id,
            }
        )

    def test_attendee_normalization_and_placeholders(self):
        attendee = self.env["digital.training.attendee"].create(
            {
                "event_id": self.event.id,
                "full_name": "  Ana   Pérez  ",
                "email": "ANA.PEREZ@EXAMPLE.COM",
                "organization_id": self.organization.id,
            }
        )
        self.assertEqual(attendee.full_name, "Ana Pérez")
        self.assertEqual(attendee.email, "ana.perez@example.com")
        rendered = str(self.template.render_certificate_body(attendee))
        self.assertIn("Ana Pérez", rendered)
        self.assertIn("Conciencia Digital", rendered)
        self.assertIn("Empresa de prueba", rendered)

    def test_event_registration_state(self):
        available, _message = self.event.get_registration_availability()
        self.assertFalse(available)
        self.event.action_open_registration()
        available, _message = self.event.get_registration_availability()
        self.assertTrue(available)

