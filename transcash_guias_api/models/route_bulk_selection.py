# -*- coding: utf-8 -*-
"""Casilla de selección masiva en el asistente ORIGINAL de Logística.

No reemplaza ni salta las reglas de seguridad y elegibilidad del módulo operativo.
Se utiliza un máximo de 100 guías por lote porque el embarque está limitado a
100 por la aplicación principal (logistica_transcash.models.rutas).
"""
from odoo import api, fields, models

MAX_GUIAS_EN_EMBARQUE = 100


class SeleccionarGuiasRutaBulk(models.TransientModel):
    _inherit = 'transcash.seleccionar.guias.ruta.wizard'

    tc_seleccionar_todas = fields.Boolean(
        string='Seleccionar todas las guías disponibles',
        help='Marca las guías elegibles mostradas en la lista, hasta 100. '
             'Las que requieran cambio de transportista o chofer solo se '
             'incluyen si autoriza la reasignación.',
    )
    tc_total_marcadas = fields.Integer(
        string='Guías marcadas', compute='_tc_compute_resumen_marcado'
    )
    tc_total_elegibles = fields.Integer(
        string='Guías elegibles de esta lista', compute='_tc_compute_resumen_marcado'
    )

    @api.depends('linea_ids.seleccionada', 'linea_ids.disponible',
                 'linea_ids.requiere_reasignacion', 'permitir_reasignar')
    def _tc_compute_resumen_marcado(self):
        for wizard in self:
            wizard.tc_total_marcadas = len(wizard.linea_ids.filtered('seleccionada'))
            wizard.tc_total_elegibles = len(wizard.linea_ids.filtered(
                lambda line: line.disponible and (
                    not line.requiere_reasignacion or wizard.permitir_reasignar
                )
            ))

    def _tc_aplicar_seleccion_masiva(self):
        """Solo modifica las casillas del wizard; no asigna guías a ninguna ruta."""
        for wizard in self:
            # Las ya seleccionadas van primero para no perder la preparación
            # previa cuando haya más candidatas que el límite del embarque.
            lineas = sorted(wizard.linea_ids, key=lambda line: not line.seleccionada)
            marcadas = 0
            for line in lineas:
                elegible = bool(
                    line.disponible and (
                        not line.requiere_reasignacion or wizard.permitir_reasignar
                    )
                )
                marcar = bool(wizard.tc_seleccionar_todas and elegible and
                              marcadas < MAX_GUIAS_EN_EMBARQUE)
                line.seleccionada = marcar
                if marcar:
                    marcadas += 1

    @api.onchange('tc_seleccionar_todas')
    def _tc_onchange_seleccionar_todas(self):
        self._tc_aplicar_seleccion_masiva()

    @api.onchange('permitir_reasignar')
    def _tc_onchange_autorizacion_masiva(self):
        # Al cambiar la autorización, solo reevalúa si el control masivo
        # está activado; no afecta casillas elegidas manualmente.
        for wizard in self:
            if wizard.tc_seleccionar_todas:
                wizard._tc_aplicar_seleccion_masiva()
