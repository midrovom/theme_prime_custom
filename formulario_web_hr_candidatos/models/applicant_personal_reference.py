from odoo import _, api, fields, models

class ApplicantReference(models.Model):
    _name = 'applicant.reference'
    _description = 'Referencias personales del solicitante'

    applicant_id = fields.Many2one('hr.applicant', string='Solicitante', ondelete='cascade')

    nombre = fields.Char(string="Nombre", required=True)
    domicilio = fields.Char(string="Domicilio", required=True)
    telefono = fields.Char(string="Teléfono", required=True)
    ocupacion = fields.Char(string="Ocupación", required=True)
    tiempo_conocerlo = fields.Char(string="Tiempo de conocerlo", required=True)
