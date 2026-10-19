"""V5.29 · Dominios ORM y acceso a bandejas de embarques.

Ejecutar con --test-enable -u logistica_transcash en una copia de BD.
"""
from odoo.tests.common import TransactionCase
from ..controllers.trip_filters import available_filters, resolve_filter, filter_domain


class TestFiltrosEmbarqueV529(TransactionCase):
    def test_chofer_no_puede_pedir_revision_ni_novedades_cliente(self):
        self.assertEqual(resolve_filter(None), 'curso')
        self.assertEqual(resolve_filter('pendientes'), 'curso')
        self.assertEqual(resolve_filter('revision'), 'curso')
        self.assertEqual(resolve_filter('incidencias'), 'curso')
        self.assertEqual([x[0] for x in available_filters()],
                         ['curso', 'entregados', 'todos'])

    def test_proveedor_revisa_sus_facturas_no_incidencias_clientes(self):
        self.assertEqual(resolve_filter('revision', supplier=True), 'revision')
        self.assertEqual(resolve_filter('incidencias', supplier=True), 'curso')
        self.assertEqual(filter_domain('revision', supplier=True), [
            ('liquidacion_linea_id', 'any', [('liquidacion_id.estado', 'in', ['revision', 'observada'])])])

    def test_personal_interno_ve_filtros_de_seguimiento(self):
        self.assertEqual(resolve_filter('revision', internal=True), 'revision')
        self.assertEqual(resolve_filter('incidencias', internal=True), 'incidencias')
        self.assertIn(('incidencias', 'Novedades del cliente'), available_filters(internal=True))

    def test_dominios_aplican_en_orm_odoo(self):
        # Valida cadenas relacionales SQL, sin crear ni modificar viajes de producción.
        trips = self.env['transcash.embarque'].sudo()
        for name in ('curso', 'revision', 'incidencias', 'entregados', 'todos'):
            trips.search([('company_id', 'in', self.env.user.company_ids.ids)] +
                         filter_domain(name), limit=1)
        trips.search([('company_id', 'in', self.env.user.company_ids.ids)] +
                     filter_domain('revision', supplier=True), limit=1)

    def test_fechas_previstas_existen_sin_guardar_datos(self):
        trip = self.env['transcash.embarque']
        self.assertIn('fecha_traslado_prevista', trip._fields)
        self.assertIn('fecha_entrega_prevista', trip._fields)
        self.assertFalse(trip._fields['fecha_traslado_prevista'].store)
        self.assertFalse(trip._fields['fecha_entrega_prevista'].store)

    def test_vista_no_expone_novedades_en_tarjeta_del_chofer(self):
        listing = self.env.ref('logistica_transcash.portal_embarques')
        self.assertIn('filtros_embarque', listing.arch_db)
        self.assertIn('puede_ver_revision and e.incidencias_pendientes', listing.arch_db)
        self.assertIn('trip_dates_card', listing.arch_db)
