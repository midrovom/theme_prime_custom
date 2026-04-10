from odoo import models, fields

class ApplicantEducation(models.Model):
    _name = 'applicant.education'
    _description = 'Educación para el reclutamiento del solicitante'

    applicant_id = fields.Many2one('hr.applicant', string='Solicitante')

    level_id = fields.Many2one('hr.recruitment.degree', string='Nivel Educativo', required=True)
    institucion = fields.Char(string="Institución Educativa", required=True)
    fecha_inicio = fields.Date(string="Fecha de inicio", required=True)
    year_fin = fields.Char(string="Año de finalización")

    country_id = fields.Many2one('res.country', string="País", required=True)
    state_id = fields.Many2one('res.country.state', string="Ciudad/Provincia")
 
    # Nuevo campo para diferenciar
    titulo = fields.Char(string='Título Recibido')
    titulo_por_obtener = fields.Char(string='Tipo de formación')
    institucion_2 = fields.Char(string="Institución", required=True)
    carrera = fields.Char(string="Carrera", required=True)
    horario = fields.Char(string="Horario", required=True)
    estado = fields.Char(string="Nivel actual")
    study_current = fields.Selection( selection=[('si', 'Sí'), ('no', 'No')], string="¿Estudia en la actualidad?", required=True)


class ApplicantStudyArea(models.Model):
    _name = 'applicant.study.area'
    _description = 'Área de estudio'
    _sql_constraints = [
        ('name_uniq', 'unique (name)', 'El nombre del área de estudio debe ser único!')
    ]

    sequence = fields.Integer("Secuencia", default=1)
