# -*- coding: utf-8 -*-
"""Carga manual independiente del dashboard, desde el menú de Odoo."""
import base64
import binascii
import zipfile
import xml.etree.ElementTree as ET

from odoo import fields, models, _
from odoo.exceptions import AccessError, UserError

from ..services.processor import read_xlsx, InventoryImportError, MAX_FILE


class TranscashInventoryImportWizard(models.TransientModel):
    _name = 'transcash.inventory.import.wizard'
    _description = 'Importar Excel de inventario TRANSCASH'

    company_id = fields.Many2one(
        'res.company', string='Empresa', required=True,
        default=lambda self: self.env.company, readonly=True)
    file_data = fields.Binary(string='Archivo Excel', required=True, attachment=False)
    file_name = fields.Char(string='Nombre de archivo')

    def action_import(self):
        self.ensure_one()
        if not (self.env.user.has_group('transcash_inventory.group_transcash_manager')
                or self.env.user.has_group('base.group_system')):
            raise AccessError(_('No tiene permisos para importar inventarios.'))
        if self.company_id != self.env.company:
            raise UserError(_('La empresa seleccionada ha cambiado. Cierre y abra nuevamente la importación.'))
        if not self.file_name or not self.file_name.lower().endswith('.xlsx'):
            raise UserError(_('Seleccione un archivo de Excel válido (.xlsx).'))
        if not self.file_data:
            raise UserError(_('Seleccione el archivo antes de importar.'))
        try:
            binary = base64.b64decode(self.file_data, validate=True)
        except (binascii.Error, ValueError, TypeError):
            raise UserError(_('El contenido del archivo no es válido.')) from None
        if len(binary) > MAX_FILE:
            raise UserError(_('El archivo supera el tamaño máximo de 45 MB.'))
        if not binary.startswith(b'PK'):
            raise UserError(_('El archivo no es un Excel .xlsx válido.'))
        try:
            dataset = read_xlsx(binary)
        except InventoryImportError as error:
            raise UserError(_('No se pudo importar el Excel: %s') % error) from None
        except (zipfile.BadZipFile, ET.ParseError, KeyError, IndexError, ValueError) as error:
            raise UserError(_('El Excel está dañado o sus hojas tienen una estructura no compatible: %s') % str(error)[:250]) from None
        self.env['transcash.inventory.snapshot'].create_from_dataset(
            dataset, filename=self.file_name[:180], raw_size=len(binary))
        # La información procesada se conserva como versión histórica. El XLSX
        # original no necesita mantenerse duplicado en este asistente temporal.
        self.write({'file_data': False})
        return {
            'type': 'ir.actions.client',
            'name': _('Dashboard de inventarios'),
            'tag': 'transcash_inventory.dashboard',
            'target': 'main',
        }
