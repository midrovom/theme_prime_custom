# -*- coding: utf-8 -*-
"""Prueba independiente del agregador de flota (sin base Odoo).

Ejecutar: python -m unittest discover -s transcash_guias_api/tests -p 'test_vehicle_bi_v220.py'
"""
import unittest
from collections import defaultdict
from pathlib import Path
from types import SimpleNamespace


class TripMetricsTest(unittest.TestCase):
    def test_aggregate_distinct_trips_and_departed_weight(self):
        source = (Path(__file__).resolve().parents[1] / 'models' / 'dashboard_bi.py').read_text()
        code = source.split('        # KPI de flota:')[1].split('        route_rows = []')[0]
        code = '        # KPI de flota:' + code
        # Dedentar el fragmento del método para ejecutarlo como bloque aislado.
        import textwrap
        code = textwrap.dedent(code)
        class FakeEnv:
            def __getitem__(self, model):
                if model != 'transcash.embarque':
                    raise AssertionError('Modelo incorrecto')
                return SimpleNamespace(_fields={
                    'tipo_vehiculo': SimpleNamespace(selection=[
                        ('camion', 'Camión'), ('mula','Mula / tractocamión'),
                        ('camioneta','Camioneta'), ('furgon','Furgón'), ('otro','Otro')])})
        guide1 = SimpleNamespace(id=1)
        guide2 = SimpleNamespace(id=2)
        guide3 = SimpleNamespace(id=3)
        guide4 = SimpleNamespace(id=4)
        guide5 = SimpleNamespace(id=5)
        # 1 viaje realizado con dos rutas (la lógica NO usa el número de rutas).
        embarked = SimpleNamespace(id=101, state='ruta', tipo_vehiculo='camion',
                                   fecha_salida='2026-10-21 08:00:00',
                                   guia_ids=[guide1, guide2], ruta_ids=[1, 2])
        # Otro embarque sin salida (programado): no debe aumentar el kg realizado.
        pending = SimpleNamespace(id=102, state='preparacion', tipo_vehiculo='camion',
                                  fecha_salida=False, guia_ids=[guide3], ruta_ids=[3])
        canceled = SimpleNamespace(id=103, state='cancelado', tipo_vehiculo='mula',
                                   fecha_salida=False, guia_ids=[guide4], ruta_ids=[])
        historic = SimpleNamespace(id=104, state='entregado', tipo_vehiculo=False,
                                   fecha_salida='2026-10-21 12:00:00', guia_ids=[guide5], ruta_ids=[])
        kg = {1:100, 2:250, 3:1000, 4:9000, 5:80}
        scope = {
            'self': SimpleNamespace(env=FakeEnv()), 'embarques':[embarked, pending, canceled, historic],
            'metricas': lambda g: {'kg':kg[g.id], 'm2':2, 'unidades':3},
            'kpis':{}, 'defaultdict':defaultdict,
        }
        exec(compile(code, '<vehicle-aggregation>', 'exec'), scope)
        by_type = {x['clave']:x for x in scope['vehicle_rows']}
        self.assertNotIn('mula', by_type)
        self.assertEqual(2, by_type['camion']['viajes_contratados'])
        self.assertEqual(1, by_type['camion']['viajes_realizados'])
        self.assertEqual(1350, by_type['camion']['kg_programados'])
        self.assertEqual(350, by_type['camion']['kg_transportados'])
        self.assertEqual(350, by_type['camion']['kg_promedio_viaje'])
        self.assertEqual(1, by_type['sin_tipo']['viajes_contratados'])
        self.assertEqual(80, by_type['sin_tipo']['kg_transportados'])
        self.assertEqual(2, scope['kpis']['vehiculos_viajes_realizados'])
        self.assertEqual(430, scope['kpis']['vehiculos_kg_transportados'])
        self.assertEqual(1430, scope['kpis']['vehiculos_kg_programados'])
        self.assertEqual(2, scope['kpis']['tipos_vehiculo_contratados'])

    def test_empty_result(self):
        source = (Path(__file__).resolve().parents[1] / 'models' / 'dashboard_bi.py').read_text()
        code = '        # KPI de flota:' + source.split('        # KPI de flota:')[1].split('        route_rows = []')[0]
        import textwrap
        scope = {'self': SimpleNamespace(env={
            'transcash.embarque': SimpleNamespace(_fields={
                'tipo_vehiculo': SimpleNamespace(selection=[('camion','Camión')])})}),
            'embarques':[], 'metricas':lambda g: {}, 'kpis':{}, 'defaultdict':defaultdict}
        exec(compile(textwrap.dedent(code), '<vehicle-empty>', 'exec'), scope)
        self.assertEqual([], scope['vehicle_rows'])
        self.assertEqual(0, scope['kpis']['vehiculos_viajes_realizados'])


if __name__ == '__main__':
    unittest.main()
