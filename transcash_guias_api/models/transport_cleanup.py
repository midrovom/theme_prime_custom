"""Diagnóstico y limpieza prudente de duplicados de empresas transportistas.

No fusiona terceros con relaciones, no cambia viajes ni liquidaciones. La baja
segura de contactos sin uso es archivado reversible; tc.transport sin uso puede
eliminarse si tiene RUC repetido y ninguna referencia FK.
"""
from collections import defaultdict

from psycopg2 import sql
from odoo import api, models, _
from odoo.exceptions import UserError
from .transport_identity import normalize_transport_ruc


class TCTransportCleanup(models.TransientModel):
    _inherit = 'tc.partner.duplicates.review'

    def _fk_for_table(self, table):
        self.env.cr.execute('''
            SELECT n.nspname, cl.relname, a.attname
              FROM pg_constraint c
              JOIN pg_class cl ON cl.oid = c.conrelid
              JOIN pg_namespace n ON n.oid = cl.relnamespace
              JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = c.conkey[1]
             WHERE c.contype = 'f' AND c.confrelid = %s::regclass
               AND array_length(c.conkey, 1) = 1
        ''', (table,))
        return self.env.cr.fetchall()

    def _transport_contact_groups(self):
        """Grupos por RUC real, sin asumir equivalencias basadas en nombres."""
        self.env.cr.execute('''
            WITH normalized AS (
                SELECT id, CASE
                    WHEN LEFT(raw_vat, 2) = 'EC' AND LENGTH(raw_vat) IN (12, 15)
                    THEN SUBSTRING(raw_vat FROM 3)
                    ELSE raw_vat END AS ruc
                FROM (
                    SELECT id, UPPER(REGEXP_REPLACE(COALESCE(vat, ''),
                        '[^A-Za-z0-9]', '', 'g')) AS raw_vat
                    FROM res_partner
                    WHERE active IS TRUE AND is_company IS TRUE
                ) AS source
            )
            SELECT ruc, ARRAY_AGG(id ORDER BY id)
            FROM normalized
            WHERE ruc ~ '^[0-9]+$' AND LENGTH(ruc) IN (10, 13)
            GROUP BY ruc HAVING COUNT(*) > 1
            ORDER BY ruc
        ''')
        groups = self.env.cr.fetchall()
        # Específico a transportistas: no tocar duplicados de otros negocios.
        self.env.cr.execute('''
            SELECT DISTINCT partner_id FROM (
               SELECT transport_partner_id AS partner_id FROM tc_guide
               UNION ALL SELECT proveedor_id FROM transcash_guia
               UNION ALL SELECT proveedor_id FROM transcash_hoja_ruta
               UNION ALL SELECT proveedor_id FROM transcash_embarque
            ) AS used_carriers WHERE partner_id IS NOT NULL
        ''')
        linked_ids = {row[0] for row in self.env.cr.fetchall()}
        self.env.cr.execute('SELECT ruc FROM tc_transport')
        master_rucs = {normalize_transport_ruc(row[0]) for row in self.env.cr.fetchall()}
        return [(ruc, ids) for ruc, ids in groups
                if ruc in master_rucs or linked_ids.intersection(ids)]

    def _transport_name_groups_without_vat(self):
        """Solo diagnostica/archiva contactos sin VAT ni referencias, nunca fusiona."""
        self.env.cr.execute('''
            SELECT UPPER(REGEXP_REPLACE(BTRIM(name), '[[:space:]]+', ' ', 'g')) AS name_key,
                   ARRAY_AGG(id ORDER BY id)
              FROM res_partner
             WHERE active IS TRUE AND is_company IS TRUE
               AND NULLIF(BTRIM(COALESCE(vat, '')), '') IS NULL
               AND NULLIF(BTRIM(name), '') IS NOT NULL
             GROUP BY UPPER(REGEXP_REPLACE(BTRIM(name), '[[:space:]]+', ' ', 'g'))
            HAVING COUNT(*) > 1
        ''')
        matches = self.env.cr.fetchall()
        self.env.cr.execute('''
            SELECT DISTINCT UPPER(REGEXP_REPLACE(BTRIM(transport_name),
                '[[:space:]]+', ' ', 'g'))
              FROM tc_guide
             WHERE NULLIF(BTRIM(COALESCE(transport_name, '')), '') IS NOT NULL
        ''')
        transport_names = {row[0] for row in self.env.cr.fetchall()}
        return [(name, ids) for name, ids in matches if name in transport_names]

    def _aux_duplicate_groups(self):
        Transport = self.env['tc.transport'].sudo()
        groups = defaultdict(list)
        for carrier in Transport.search([]):
            norm = normalize_transport_ruc(carrier.ruc)
            if norm:
                groups[(carrier.company_id.id, norm)].append(carrier)
        return {key: records for key, records in groups.items() if len(records) > 1}

    def _review_transport(self, cleanup=False):
        self.ensure_one()
        self._assert_manager()
        if cleanup and not self.env.context.get('tc_confirm_transport_cleanup'):
            raise UserError(_('Confirme la limpieza segura de transportistas antes de ejecutarla.'))
        Partner = self.env['res.partner'].sudo().with_context(active_test=False)
        contact_fks = self._foreign_keys()
        auxiliary_fks = self._fk_for_table('tc_transport')
        report = []
        examined = archived = masters_deleted = 0
        contacts = self._transport_contact_groups()
        for ruc, ids in contacts:
            partners = Partner.browse(ids)
            # Nunca fusionar en automático contactos privados de distintas empresas.
            scoped_companies = {p.company_id.id for p in partners if p.company_id}
            if len(scoped_companies) > 1:
                report.append('RUC %s | contactos %s: distintas compañías; conciliación manual.' %
                              (ruc, ids))
                continue
            users = set(self.env['res.users'].sudo().with_context(active_test=False).search([
                ('partner_id', 'in', ids)]).mapped('partner_id').ids)
            in_use = {p.id: self._has_references(p.id, contact_fks) for p in partners}
            canonical = partners.sorted(key=lambda p: (
                not in_use[p.id], p.id not in users, bool(p.company_id), p.id))[0]
            for alternate in partners - canonical:
                examined += 1
                if in_use[alternate.id] or alternate.child_ids or alternate.id in users:
                    report.append('RUC %s | conservar %s; duplicado %s EN USO (no tocar; fusión manual).' %
                                  (ruc, canonical.id, alternate.id))
                elif cleanup:
                    alternate.write({'active': False})
                    archived += 1
                    report.append('RUC %s | conservar %s; contacto sin uso %s ARCHIVADO.' %
                                  (ruc, canonical.id, alternate.id))
                else:
                    report.append('RUC %s | conservar %s; contacto %s sin referencias: archivable.' %
                                  (ruc, canonical.id, alternate.id))

        # Sin RUC no podemos afirmar identidad fiscal; solo archivamos clones
        # con nombre exactamente igual, cuando son totalmente huérfanos.
        nameless_ruc_groups = self._transport_name_groups_without_vat()
        for name, ids in nameless_ruc_groups:
            partners = Partner.browse(ids)
            companies = {p.company_id.id for p in partners if p.company_id}
            if len(companies) > 1:
                report.append('SIN RUC %s: contactos de varias empresas; revisión manual.' % name)
                continue
            used = {p.id: self._has_references(p.id, contact_fks) for p in partners}
            chosen = partners.sorted(key=lambda p: (not used[p.id], p.id))[0]
            for other in partners - chosen:
                examined += 1
                # Códigos ERP diferentes podrían significar entidades diferentes.
                conflicting_codes = bool(other.ref and chosen.ref and
                                         other.ref.strip().upper() != chosen.ref.strip().upper())
                if used[other.id] or other.child_ids or conflicting_codes:
                    report.append('SIN RUC %s | mantener %s; %s tiene referencias (revisión manual).' %
                                  (name, chosen.id, other.id))
                elif cleanup:
                    other.write({'active': False})
                    archived += 1
                    report.append('SIN RUC %s | mantener %s; %s sin uso ARCHIVADO.' %
                                  (name, chosen.id, other.id))
                else:
                    report.append('SIN RUC %s | mantener %s; %s sin uso archivable.' %
                                  (name, chosen.id, other.id))
        auxiliary = self._aux_duplicate_groups()
        for (company_id, ruc), carriers in auxiliary.items():
            used = {t.id: self._has_references(t.id, auxiliary_fks) for t in carriers}
            keep = sorted(carriers, key=lambda t: (not used[t.id], t.id))[0]
            for duplicate in carriers:
                if duplicate.id == keep.id:
                    continue
                examined += 1
                if used[duplicate.id]:
                    report.append('Auxiliar tc.transport | empresa %s RUC %s: %s tiene guías; no se elimina.' %
                                  (company_id, ruc, duplicate.id))
                elif cleanup:
                    # Odoo ORM unlink: FK revisadas previamente. A diferencia
                    # de res.partner este maestro auxiliar no usa archivado.
                    duplicate.unlink()
                    masters_deleted += 1
                    report.append('Auxiliar tc.transport | empresa %s RUC %s: %s sin uso ELIMINADO.' %
                                  (company_id, ruc, duplicate.id))
                else:
                    report.append('Auxiliar tc.transport | empresa %s RUC %s: %s sin uso eliminable.' %
                                  (company_id, ruc, duplicate.id))
        summary = ('RUC duplicados de TRANSPORTISTAS: %s grupos de contactos; %s grupos en tc.transport.\n'
                   'Secundarios examinados: %s. Archivados: %s. Auxiliares eliminados: %s.\n'
                   'No se cambian contactos en uso ni relaciones con guías, viajes, usuarios o liquidaciones.\n'
                   'Nombres de transporte repetidos SIN RUC: %s grupos (solo archivado huérfanos).\n'
                   'Para vincular un transportista sin RUC se necesita identificación fiscal confiable.\n\n'
                   % (len(contacts), len(auxiliary), examined, archived, masters_deleted,
                      len(nameless_ruc_groups)))
        self.write({'candidate_count': examined, 'archived_count': archived,
                    'report': summary + ('\n'.join(report[:500]) or 'Sin duplicados de RUC de transportistas.')})
        return {'type': 'ir.actions.act_window', 'res_model': self._name,
                'res_id': self.id, 'view_mode': 'form', 'target': 'new'}

    def action_analyze_transport(self):
        return self._review_transport(False)

    def action_cleanup_transport(self):
        return self.with_context(tc_confirm_transport_cleanup=True)._review_transport(True)
