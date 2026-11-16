# -*- coding: utf-8 -*-
"""Conservar el último movimiento anterior al historial estructurado.

Versiones hasta 18.0.1.8.0 solo disponían de los tres campos de último
movimiento y del chatter. No reconstruir movimientos anteriores inexistentes,
ni inventar receptores, ni crear duplicados cuando se repita la actualización.
"""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Equipment = env['maintenance.equipment'].sudo()
    History = env['maintenance.equipment.bodega.history'].sudo()

    for equipment in Equipment.search([
        ('bodega_asignacion_fecha', '!=', False),
        ('employee_id', '!=', False),
    ]):
        warehouse = equipment.employee_id
        if not warehouse.es_bodega:
            # El equipo pudo ser reasignado por otra vía desde la última
            # visita a bodega; no atribuirle una bodega incorrecta.
            continue
        if History.search_count([('equipment_id', '=', equipment.id)]):
            continue
        previous = equipment.empleado_devolucion_anterior_id
        user = equipment.bodega_asignado_por_id
        company = equipment.company_id or env.company
        History.create({
            'equipment_id': equipment.id,
            'company_id': company.id,
            'movement_date': equipment.bodega_asignacion_fecha,
            'previous_employee_id': previous.id or False,
            'warehouse_employee_id': warehouse.id,
            'registered_by_id': user.id or False,
            'previous_employee_name': previous.display_name if previous else 'Sin empleado',
            'warehouse_name': warehouse.display_name,
            'registered_by_name': user.display_name if user else False,
            # receiver no existía; dejar sin dato, no inventar.
        })
        equipment.with_context(tracking_disable=True).write({
            'bodega_destino_ultima_id': warehouse.id,
        })
