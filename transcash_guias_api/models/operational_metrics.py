"""Indicadores de carga para los Kanban de guías y hojas de ruta.

Extensión solo de lectura: no toca asignaciones, estados ni liquidaciones.
"""
from odoo import api, fields, models


class TCOperationalGuideMetrics(models.Model):
    _inherit = 'transcash.guia'

    tc_line_count = fields.Integer('Referencias de producto', compute='_compute_tc_load')
    tc_total_m2 = fields.Float('Superficie (m²)', compute='_compute_tc_load', digits=(16, 2))
    tc_total_unidades = fields.Float('Unidades', compute='_compute_tc_load', digits=(16, 2))
    tc_total_pallets = fields.Float('Pallets', compute='_compute_tc_load', digits=(16, 2))
    tc_total_cajas = fields.Float('Cajas', compute='_compute_tc_load', digits=(16, 2))
    tc_total_kg = fields.Float('Peso (kg)', compute='_compute_tc_load', digits=(16, 2))

    @api.depends('linea_ids', 'linea_ids.cantidad', 'linea_ids.unidad',
                 'linea_ids.peso_kg', 'linea_ids.pallets_info',
                 'linea_ids.cajas_info', 'linea_ids.vigente_erp', 'peso_kg')
    def _compute_tc_load(self):
        for guide in self:
            lines = guide.linea_ids.filtered('vigente_erp')
            guide.tc_line_count = len(lines)
            guide.tc_total_m2 = sum(ln.cantidad for ln in lines if ln.unidad == 'm2')
            guide.tc_total_unidades = sum(ln.cantidad for ln in lines if ln.unidad == 'unidad')
            guide.tc_total_pallets = sum(lines.mapped('pallets_info'))
            guide.tc_total_cajas = sum(lines.mapped('cajas_info'))
            # Cuando un legado no tiene detalle, mostrar el peso declarado de cabecera.
            guide.tc_total_kg = sum(lines.mapped('peso_kg')) if lines else (guide.peso_kg or 0.0)


class TCRouteMetrics(models.Model):
    _inherit = 'transcash.hoja.ruta'

    tc_guias_carga = fields.Integer('Guías de carga', compute='_compute_tc_route_load')
    tc_productos_carga = fields.Integer('Referencias de producto', compute='_compute_tc_route_load')
    tc_kg_carga = fields.Float('Peso total (kg)', compute='_compute_tc_route_load', digits=(16, 2))
    tc_m2_carga = fields.Float('Superficie total (m²)', compute='_compute_tc_route_load', digits=(16, 2))
    tc_unidades_carga = fields.Float('Unidades totales', compute='_compute_tc_route_load', digits=(16, 2))
    tc_pallets_carga = fields.Float('Pallets totales', compute='_compute_tc_route_load', digits=(16, 2))
    tc_cajas_carga = fields.Float('Cajas totales', compute='_compute_tc_route_load', digits=(16, 2))
    tc_carga_preliminar = fields.Boolean('Carga preliminar', compute='_compute_tc_route_load')

    @api.depends('state', 'seleccion_guia_ids', 'guia_ids',
                 'seleccion_guia_ids.tc_total_m2', 'seleccion_guia_ids.tc_total_unidades',
                 'seleccion_guia_ids.tc_total_pallets', 'seleccion_guia_ids.tc_total_cajas',
                 'seleccion_guia_ids.tc_total_kg', 'seleccion_guia_ids.tc_line_count',
                 'guia_ids.tc_total_m2', 'guia_ids.tc_total_unidades',
                 'guia_ids.tc_total_pallets', 'guia_ids.tc_total_cajas',
                 'guia_ids.tc_total_kg', 'guia_ids.tc_line_count')
    def _compute_tc_route_load(self):
        for route in self:
            # Antes de confirmar las guías están en la M2M temporal.
            # Después se consideran exclusivamente las guías realmente confirmadas.
            preliminary = route.state == 'borrador'
            guides = route.seleccion_guia_ids if preliminary else route.guia_ids
            route.tc_carga_preliminar = preliminary
            route.tc_guias_carga = len(guides)
            route.tc_productos_carga = sum(guides.mapped('tc_line_count'))
            route.tc_kg_carga = sum(guides.mapped('tc_total_kg'))
            route.tc_m2_carga = sum(guides.mapped('tc_total_m2'))
            route.tc_unidades_carga = sum(guides.mapped('tc_total_unidades'))
            route.tc_pallets_carga = sum(guides.mapped('tc_total_pallets'))
            route.tc_cajas_carga = sum(guides.mapped('tc_total_cajas'))


class TCRouteSelectionLineMetrics(models.TransientModel):
    _inherit = 'transcash.seleccionar.guias.ruta.linea'

    tc_total_m2 = fields.Float(related='guia_id.tc_total_m2', readonly=True, string='m²')
    tc_total_unidades = fields.Float(related='guia_id.tc_total_unidades', readonly=True, string='Unidades')
    tc_total_pallets = fields.Float(related='guia_id.tc_total_pallets', readonly=True, string='Pallets')
    tc_total_cajas = fields.Float(related='guia_id.tc_total_cajas', readonly=True, string='Cajas')
    tc_total_kg = fields.Float(related='guia_id.tc_total_kg', readonly=True, string='kg')
