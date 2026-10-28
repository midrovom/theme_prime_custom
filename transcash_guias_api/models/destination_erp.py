# -*- coding: utf-8 -*-
"""Acción administrativa: conciliar destinos recibidos del ERP."""
import logging
from odoo import api, models, _
from odoo.exceptions import AccessError, ValidationError
from .destination_codes import (
    erp_destination_code, erp_destination_key, _clean_city, upsert_erp_destination,
)

_logger = logging.getLogger(__name__)

class TCGuideSyncDestinations(models.Model):
    _inherit = 'tc.guide.sync'

    @api.model
    def action_reconcile_erp_destinations(self):
        """Reparar el catálogo y guías libres a partir de staging ya importado.

        No llama nuevamente al ERP ni altera guías históricas en ruta,
        embarcadas, entregadas o aprobadas.
        """
        user = self.env.user
        if not (self.env.su or user.has_group('transcash_guias_api.group_tc_sync_admin')
                or user.has_group('logistica_transcash.group_logistica_manager')):
            raise AccessError(_('Solo integración o jefe de Logística puede sincronizar el catálogo ERP.'))
        company_id = self.env.company.id
        Staging = self.env['tc.guide'].sudo().with_company(self.env.company)
        Operational = self.env['transcash.guia'].sudo().with_company(self.env.company)
        rows = Staging.search([('company_id', '=', company_id)], order='id')
        catalog_ids = set()
        guides_repaired = 0
        skipped_assigned = 0
        missing_code = 0
        errors = []
        for staged in rows:
            code = staged.destination_code_erp or (
                staged.destination_id.external_code if staged.destination_id else '')
            if not code:
                missing_code += 1
                continue
            try:
                with self.env.cr.savepoint():
                    canonical = erp_destination_code(code)
                    city = staged.destination_city or (
                        staged.destination_id.city if staged.destination_id else '')
                    master = upsert_erp_destination(self.env, company_id, canonical, city)
                    if not master or not master.active:
                        raise ValidationError(_('%s: destino inactivo o sin catálogo.') % code)
                    catalog_ids.add(master.id)
                    stage_vals = {}
                    if staged.destination_code_erp != canonical:
                        stage_vals['destination_code_erp'] = canonical
                    if city and staged.destination_city != _clean_city(city):
                        stage_vals['destination_city'] = _clean_city(city)
                    if stage_vals:
                        staged.write(stage_vals)
                    operational = staged.operational_guide_id
                    if not operational or operational.company_id.id != company_id:
                        operational = Operational.search([
                            ('company_id', '=', company_id),
                            ('external_id_erp', '=', staged.external_id),
                        ], limit=1)
                    if not operational:
                        # También crea las guías que nunca llegaron a publicarse.
                        staged._publish_safe()
                        continue
                    assigned = bool(operational.hoja_ruta_id or operational.embarque_id
                                    or operational.state != 'registrada'
                                    or operational.aprobacion_global == 'aprobada')
                    if assigned:
                        skipped_assigned += 1
                        # Solo completar vacíos cuando coincida el código de la ruta;
                        # no alterar destinos de viajes en curso o históricos.
                        route = operational.hoja_ruta_id
                        if (route and route.destino_id and
                                erp_destination_key(route.destino_id.codigo) ==
                                erp_destination_key(canonical)):
                            changes = {}
                            if not operational.destino:
                                changes['destino'] = canonical
                            if not operational.destino_codigo:
                                changes['destino_codigo'] = canonical
                            if not operational.destino_id:
                                changes['destino_id'] = route.destino_id.id
                            if city and not operational.destino_ciudad:
                                changes['destino_ciudad'] = _clean_city(city)
                            # Solo completar dirección faltante si ya es el mismo
                            # destino de la hoja de ruta (no modificar históricos).
                            if staged.destination_address and not operational.direccion_destino_erp:
                                changes['direccion_destino_erp'] = staged.destination_address
                            if changes:
                                operational.write(changes)
                                guides_repaired += 1
                        continue
                    vals = {}
                    if operational.destino != canonical:
                        vals['destino'] = canonical
                    if operational.destino_codigo != canonical:
                        vals['destino_codigo'] = canonical
                    if operational.destino_id != master:
                        vals['destino_id'] = master.id
                    if city and operational.destino_ciudad != _clean_city(city):
                        vals['destino_ciudad'] = _clean_city(city)
                    # La dirección viene de la guía ERP, no de la ciudad ni del
                    # catálogo de destinos; puede ser diferente en cada entrega.
                    if (staged.destination_address and
                            operational.direccion_destino_erp != staged.destination_address):
                        vals['direccion_destino_erp'] = staged.destination_address
                    if vals:
                        operational.write(vals)
                        guides_repaired += 1
            except Exception as exc:
                _logger.exception('Destino ERP no sincronizado en guía %s', staged.external_id)
                errors.append('%s: %s' % (staged.external_id, str(exc)))
        message = _(
            'Destinos encontrados/creados: %(dest)s. Guías operativas actualizadas: '
            '%(guides)s. Guías en operación protegidas: %(assigned)s. '
            'Guías sin código ERP: %(missing)s. Errores: %(errors)s.'
        ) % {
            'dest': len(catalog_ids), 'guides': guides_repaired,
            'assigned': skipped_assigned, 'missing': missing_code, 'errors': len(errors),
        }
        self.env['tc.guide.sync.log'].sudo().create({
            'company_id': company_id, 'api_name': 'getguiaslogistica - destinos',
            'created_count': len(catalog_ids), 'updated_count': guides_repaired,
            'error_count': len(errors), 'details': (message + '\n' + '\n'.join(errors))[:20000],
        })
        return {
            'type': 'ir.actions.client', 'tag': 'display_notification',
            'params': {'title': _('Sincronización de destinos ERP'),
                       'message': message,
                       'type': 'warning' if errors else 'success',
                       'sticky': bool(errors)},
        }
