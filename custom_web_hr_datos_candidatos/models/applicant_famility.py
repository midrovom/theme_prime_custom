from odoo import _, api, fields, models

class ApplicantFamily(models.Model):
    _name = 'applicant.family'
    _description = 'Familiares del postulante'

    applicant_id = fields.Many2one(
        'hr.applicant',
        string='Postulante',
        ondelete='cascade'
    )

    name = fields.Char(string='Nombre completo')
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

