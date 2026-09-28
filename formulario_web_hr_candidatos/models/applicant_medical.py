from odoo import _, api, fields, models

class HrApplicantMedical(models.Model):
    _name = 'applicant.medical'
    _description = 'Información Médica del Postulante'

    applicant_id = fields.Many2one('hr.applicant', string="Postulante")
    enfermedad_persistente = fields.Selection([
        ('si', 'Sí'), ('no', 'No')], 
        string="¿Padece alguna enfermedad persistente?")
    
    detalle_enfermedad_persistente = fields.Char(string="Detalle enfermedad persistente")

    medicacion_continua = fields.Selection([
        ('si', 'Sí'), ('no', 'No')], 
        string="¿Toma medicación continua?")
    
    detalle_medicacion_continua = fields.Char(string="Detalle medicación continua")

    enfermedad_laboral = fields.Selection([
        ('si', 'Sí'), ('no', 'No')], 
        string="¿Ha padecido enfermedad laboral?")
    
    detalle_enfermedad_laboral = fields.Char(string="Detalle enfermedad laboral")

    cirugia_realizada = fields.Selection([
        ('si', 'Sí'), ('no', 'No')], 
        string="¿Ha sido sometido a cirugía?")
    
    detalle_cirugia_realizada = fields.Char(string="Detalle cirugía realizada")

    discapacidad = fields.Selection([
        ('si', 'Sí'), ('no', 'No')], 
        string="¿Tiene usted alguna discapacidad?")
    
    tipo_discapacidad = fields.Char(string="Tipo de discapacidad")
    porcentaje_discapacidad = fields.Char(string="Porcentaje de discapacidad")
    tipo_sangre = fields.Char(string="Tipo de sangre")