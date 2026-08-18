from odoo import _, api, fields, models

FAMILY_TYPES = [
    ('1', 'Padre'),
    ('2', 'Madre'),
    ('3', 'Hermano(a)'),
    ('4', 'Conyugue'),
    ('5', 'Hijo(a)'),
]

DOCUMENT_TYPES = [
    ('cedula', 'Cédula'),
    ('id_extrj', 'Cédula extranjera'),
    ('pasaporte', 'Pasaporte'),
]

class ApplicantFamily(models.Model):
    _name = 'applicant.family'
    _description = 'Familiares del postulante'

    applicant_id = fields.Many2one( 'hr.applicant', string='Postulante',
        ondelete='cascade'
    )

    familiar_type = fields.Selection(selection=FAMILY_TYPES, string="Tipo de familiar", required=True)
    name = fields.Char(string='Nombre completo')
    document_type = fields.Selection(DOCUMENT_TYPES, string='Tipo de documento')
    cedula = fields.Char(string='Cédula')
    birthdate = fields.Date(string='Fecha de nacimiento')
    phone = fields.Char(string='Teléfono')
    occupation = fields.Char(string='Ocupación / Empresa')
    economically_dependent = fields.Selection(
        [
            ('si', 'Sí'),
            ('no', 'No')
        ],
        string='Depende económicamente'
    )

    disability = fields.Selection(
        [
            ('si', 'Sí'),
            ('no', 'No')
        ],
        string='Discapacidad'
    )

    disability_type = fields.Char(string='Tipo de discapacidad')
    disability_percentage = fields.Integer(string="Porcentaje de discapacidad")

class ApplicantKnown(models.Model):
    _name = 'applicant.known'
    _description = 'Familiares o conocidos del grupo empresarial'

    applicant_id = fields.Many2one('hr.applicant', string='Solicitante', ondelete='cascade')

    posee_familiares = fields.Selection([
        ('si', 'Sí'),
        ('no', 'No')
    ], string="¿Posee familiares o conocidos en el grupo empresarial?")

    nombre_completo = fields.Char(string="Nombre completo")
    relacion = fields.Selection([
        ('familiar', 'Familiar'),
        ('amigo', 'Amigo'),
        ('conocido', 'Conocido')
    ], string="Indique relación")

    parentesco = fields.Char(string="Parentesco (si es familiar)")

