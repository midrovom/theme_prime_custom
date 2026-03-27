from odoo import _, api, fields, models

DOCUMENT_TYPES = [
    ('cedula', 'Cédula'),
    ('ruc', 'RUC'),
    ('pasaporte', 'Pasaporte'),
]


class HrApplicant(models.Model):
    _inherit = 'hr.applicant'

    # Relaciones existentes
    education_ids = fields.One2many('applicant.education', 'applicant_id', string='Formación Académica')
    experience_job_ids = fields.One2many('applicant.experience.job', 'applicant_id', string='Experiencia Laboral')
    family_ids = fields.One2many('applicant.family', 'applicant_id', string='Familiares')
    known_ids = fields.One2many('applicant.known', 'applicant_id', string='Familiares o Conocidos del Grupo Empresarial')
    reference_ids = fields.One2many('applicant.reference', 'applicant_id', string='Referencias Personales')
    provincia_id = fields.Many2one('res.country.state', string='Provincia')
    medical_ids = fields.One2many('applicant.medical', 'applicant_id', string="Información Médica")


    disability = fields.Boolean('Discapacidad', default=False)
    family_disability = fields.Boolean('Familiar con Discapacidad', default=False)
    secondary_studies = fields.Boolean('Estudios Secundarios', default=False)
    terms_conditions = fields.Boolean('Términos y condiciones')
    birthdate = fields.Date(string="Fecha de Nacimiento")
    age = fields.Integer(string="Edad")
    address = fields.Char(string="Dirección de domicilio")
    parish = fields.Char(string="Parroquia")
    birth_country_id = fields.Many2one('res.country', string="Lugar de nacimiento (país)")
    code_cellphone = fields.Char(string="Código de celular")
    document_type = fields.Selection(DOCUMENT_TYPES, string='Tipo de documento')
    cedula = fields.Char(string='Número de documento')
    nacionality = fields.Char(string='Nacionalidad')

    estado_civil = fields.Selection([
        ('soltero', 'Soltero'),
        ('casado', 'Casado'),
        ('divorciado', 'Divorciado'),
        ('union_libre', 'Unión libre'),
        ('otro', 'Otro'),
    ], string="Estado civil")

    vive_con = fields.Selection([
        ('padres', 'Padres'),
        ('familia', 'Familia'),
        ('parientes', 'Parientes'),
        ('conyuge', 'Cónyuge'),
        ('solo', 'Solo'),
        ('otro', 'Otro'),
    ], string="Vive con")

    tipo_vivienda = fields.Selection([
        ('propia', 'Propia'),
        ('arrendada', 'Arrendada'),
    ], string="Tipo de vivienda")

    num_hijos = fields.Integer(string="Número de hijos")
    dependientes = fields.Char(string="Personas que dependen de usted")


    @api.depends('lastname_paterno', 'lastname_materno', 'firstname')
    def _compute_partner_name(self):
        for record in self:
            nombres = []
            if record.lastname_paterno:
                nombres.append(record.lastname_paterno)
            if record.lastname_materno:
                nombres.append(record.lastname_materno)
            if record.firstname:
                nombres.append(record.firstname)
            record.partner_name = " ".join(nombres)
