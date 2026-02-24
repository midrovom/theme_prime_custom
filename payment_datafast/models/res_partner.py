from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

class ResPartner(models.Model):
    _inherit = 'res.partner'

    token_ids = fields.One2many('token.card', 'partner_id', string='Tokens tarjetas de credito')

    def split_name(self):
        parts = self.name.strip().split()
        
        if len(parts) == 0:
            return "", "", ""
        elif len(parts) == 1:
            return parts[0], "", ""
        elif len(parts) == 2:
            return parts[0], "", parts[1]
        elif len(parts) == 3:
            return parts[0], parts[1], parts[2]
        else:
            # Asumimos que los últimos 2 son apellidos (usado en muchos países de LATAM)
            given_name = parts[0]
            middle_name = " ".join(parts[1:-2])
            surname = " ".join(parts[-2:])
            return given_name, middle_name, surname
        

    def get_identification_doc_id(self):
        doc = self.vat or ''
        doc = doc.strip()

        if len(doc) >= 10:
            return doc[:10]
        else:
            return doc.zfill(10)


    