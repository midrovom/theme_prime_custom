from odoo import _, api, fields, models

class ApplicantExperienceJob(models.Model):
    _name = 'applicant.experience.job'
    _description = 'Experiencia laboral para el reclutamiento del solicitante'

    applicant_id = fields.Many2one('hr.applicant', string='Solicitante')

    name = fields.Char(string="Cargo desempeñado")
    empresa = fields.Char(string="Nombre de la compañía")
    location_id = fields.Reference( selection=[('res.country', 'País'), ('res.country.state', 'Ciudad/Provincia')], string="País/Ciudad", required=True)
    #pais_id = fields.Many2one('res.country', string="País")
    fecha_inicio = fields.Date(string="Fecha de inicio")
    year_fin = fields.Char(string="Año de finalización")

    # Nuevos campos
    tiempo_servicio = fields.Char(string="Tiempo que prestó su servicio")
    telefonos = fields.Char(string="Teléfonos")
    ingreso_mensual = fields.Float(string="Ingreso mensual")
    motivo_separacion = fields.Char(string="Motivo de separación")
    jefe_directo = fields.Char(string="Nombre de su jefe directo")
    cargo_jefe_directo = fields.Char(string="Cargo de su jefe directo")
