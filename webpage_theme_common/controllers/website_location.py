from odoo import http
from odoo.http import request
import json

# Controlador para obtener datos del local para el mapa
class WebsiteLocations(http.Controller):

    @http.route('/locations', type='http', auth='public', methods=['GET'], csrf=False)
    def get_locations(self):
        records = request.env['website.location'].sudo().search([])
        data = [
            {
                'name': rec.name,
                'city': rec.city,
                'address': rec.address,
                'latitude': rec.latitude,
                'longitude': rec.longitude,
            }
            for rec in records
        ]
        return request.make_response(
            json.dumps(data, ensure_ascii=False),
            headers=[('Content-Type', 'application/json')]
        )
