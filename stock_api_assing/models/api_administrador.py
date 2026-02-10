
import requests

from odoo import models, api, fields

from odoo.exceptions import UserError

import logging

import json

_logger = logging.getLogger(__name__)

class APIAdministrator(models.Model):
    _inherit = 'api.administrator'

    def button_run_sync(self):
        """Ejecuta la sincronización manual."""
        for record in self:
            if record.is_stock_update:
                try:
                    self.env['stock.api.sync'].sync_all_inventory(record.company_id.id)
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': 'Sincronización completada',
                            'message': f"Sincronización ejecutada para la empresa {record.company_id.name}.",
                            'type': 'success',
                            'sticky': False,
                        },
                    }
                except Exception as e:
                    raise UserError(f"Error durante la sincronización: {e}")
                


    def call_api(self, api_name, method="get", company_id=1, params=None, headers_extra=None):
        """ 
        Llama a la API configurada en api.administrator.

        :param api_name: Nombre de la API a buscar en la configuración.
        :param method: Método HTTP (get, post, put, delete).
        :param company_id: ID de la compañía.
        :param params: Datos que se enviarán en la petición (para POST o PUT).
        :param headers_extra: Cabeceras adicionales que se puedan necesitar.
        :return: Diccionario con la respuesta de la API.
        """
        # _logger.info("__DEBUG Iniciando sincronización con la API: %s, %s, %s", api_name,method,company_id)
        api_data = self.sudo().search(
            [('name', '=', api_name), ('type', '=', method), ('company_id', '=', company_id)], limit=1
        )
        #_logger.info("__DEBUG Iniciando sincronización con la API: %s", api_data)
        #_logger.info("__DEBUG order_data :  %s", params)
        
        if not api_data:
            raise ValueError(f"Configuración de API '{api_name}' no encontrada.")
        
        ## Validar los campos obligatorios
        api_url = (api_data.url or '').strip() + (api_data.end_point or '').strip()
        user_id = (api_data.user_id or '').strip()
        password = (api_data.password or '').strip()

        
        if not api_url or not user_id or not password:
            raise ValueError(f"Configuración de API incompleta para '{api_name}': falta URL, User ID o Password.")
        
        ## Configurar cabeceras
        headers = {
            'Accept': 'application/json',
            'version': '1',
            'framework': 'PRUEBAS',
            'userid': user_id,
            'password': password,
            'deviceid': '000000000000000',
            'sessionid': '0',
        }
        
        
        if headers_extra:
            headers.update(headers_extra)
        
        try:
            if method.lower() == "get":
                response = requests.get(api_url, headers=headers, timeout=60)
            elif method.lower() == "post":
                response = requests.post(api_url, json=params, headers=headers, timeout=60)
            elif method.lower() == "put":
                response = requests.put(api_url, json=params, headers=headers, timeout=60)
            elif method.lower() == "delete":
                response = requests.delete(api_url, headers=headers, timeout=60)
            else:
                raise ValueError(f"Método HTTP '{method}' no soportado.")
        
            response.raise_for_status()
            return response.json() 
        
        except requests.RequestException as e:
            _logger.error("Error al llamar a la API '%s': %s", api_name, e, exc_info=True)
            return {'success': False, 'message': str(e)}

