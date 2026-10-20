"""Read-only audit and optional safe archiving of truly unreferenced duplicate contacts.

Never mass-delete or reassign records tied to trips, accounts, payments, users,
address hierarchies or any table with an FK to res_partner. This is an admin
review tool, NOT an unconditional cleanup job.
"""
from collections import defaultdict
import re

from psycopg2 import sql
from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError


def vat_key(value):
    return re.sub(r'[^A-Z0-9]', '', (value or '').upper())


class TCPartnerDuplicatesReview(models.TransientModel):
    _name = 'tc.partner.duplicates.review'
    _description = 'Diagnóstico y consolidación segura de contactos Transcash'

    report = fields.Text(string='Resultado del diagnóstico', readonly=True)
    candidate_count = fields.Integer(string='Duplicados revisados', readonly=True)
    archived_count = fields.Integer(string='Contactos archivados sin referencias', readonly=True)

    def _assert_manager(self):
        u = self.env.user
        if u.share or not (self.env.su or
            u.has_group('logistica_transcash.group_logistica_manager') or
            u.has_group('transcash_guias_api.group_tc_sync_admin')):
            raise AccessError(_('Solo la administración puede revisar y depurar terceros.'))

    def _duplicate_groups(self):
        # Primero RUC/cédula; después código ERP cuando falta documento fiscal.
        # Nunca declarar duplicados por nombre exclusivamente.
        self.env.cr.execute("""
            SELECT 'VAT:' || UPPER(REGEXP_REPLACE(COALESCE(vat, ''), '[^A-Za-z0-9]', '', 'g')) key,
                   ARRAY_AGG(id ORDER BY id)
              FROM res_partner
             WHERE active = TRUE AND NULLIF(BTRIM(vat), '') IS NOT NULL
             GROUP BY UPPER(REGEXP_REPLACE(COALESCE(vat, ''), '[^A-Za-z0-9]', '', 'g'))
            HAVING COUNT(*) > 1
            UNION ALL
            SELECT 'REF:' || UPPER(BTRIM(ref)) key, ARRAY_AGG(id ORDER BY id)
              FROM res_partner
             WHERE active = TRUE AND NULLIF(BTRIM(vat), '') IS NULL
               AND NULLIF(BTRIM(ref), '') IS NOT NULL
             GROUP BY UPPER(BTRIM(ref))
            HAVING COUNT(*) > 1
        """)
        return [(key, ids) for key, ids in self.env.cr.fetchall()
                if (key.startswith('VAT:') and len(key[4:]) >= 10) or
                   (key.startswith('REF:') and len(key[4:]) >= 2)]

    def _foreign_keys(self):
        """All actual PostgreSQL FK constraints (including relation tables)."""
        self.env.cr.execute('''
            SELECT n.nspname, cl.relname, a.attname
              FROM pg_constraint c
              JOIN pg_class cl ON cl.oid = c.conrelid
              JOIN pg_namespace n ON n.oid = cl.relnamespace
              JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = c.conkey[1]
             WHERE c.contype = 'f' AND c.confrelid = 'res_partner'::regclass
               AND array_length(c.conkey, 1) = 1
        ''')
        return self.env.cr.fetchall()

    def _has_references(self, partner_id, foreign_keys):
        for schema, table, column in foreign_keys:
            self.env.cr.execute(sql.SQL('SELECT 1 FROM {}.{} WHERE {} = %s LIMIT 1').format(
                sql.Identifier(schema), sql.Identifier(table), sql.Identifier(column)), (partner_id,))
            if self.env.cr.fetchone():
                return True
        return False

    def _evaluate(self, archive=False):
        self.ensure_one()
        self._assert_manager()
        if archive and not self.env.context.get('tc_confirm_safe_archive'):
            raise UserError(_('Se requiere confirmar la depuración antes de archivar contactos.'))
        Partner = self.env['res.partner'].sudo().with_context(active_test=False)
        groups = self._duplicate_groups()
        foreign_keys = self._foreign_keys()
        reports = []
        archived = 0
        examined = 0
        for key, ids in groups:
            contacts = Partner.browse(ids)
            # Los códigos ERP solo equivalen a la misma persona si el nombre
            # coincide; RUC/cédula tiene prioridad como identidad principal.
            if key.startswith('REF:') and len({(p.name or '').strip().upper() for p in contacts}) > 1:
                reports.append('%s: %s; nombres distintos, revisión manual obligatoria.' % (key, ids))
                continue
            # Do not merge company-specific contacts with different company_id.
            company_ids = set(p.company_id.id for p in contacts if p.company_id)
            if len(company_ids) > 1:
                reports.append('%s: %s; distintas empresas, requiere revisión manual.' % (key, ids))
                continue
            linked = set(self.env['res.users'].sudo().with_context(active_test=False).search([
                ('partner_id', 'in', ids)]).mapped('partner_id').ids)
            keeper = contacts.sorted(key=lambda p: (
                p.id not in linked, bool(p.company_id), p.id,
            ))[0]
            for duplicate in contacts - keeper:
                examined += 1
                if duplicate.id in linked or duplicate.child_ids or self._has_references(duplicate.id, foreign_keys):
                    reports.append('%s: conservar %s; %s tiene relaciones, fusionar manualmente.' %
                                   (key, keeper.id, duplicate.id))
                elif archive:
                    duplicate.write({'active': False})
                    archived += 1
                    reports.append('%s: conservar %s; archivado huérfano %s.' %
                                   (key, keeper.id, duplicate.id))
                else:
                    reports.append('%s: conservar %s; %s puede archivarse (sin referencias FK).' %
                                   (key, keeper.id, duplicate.id))
        self.write({
            'candidate_count': examined,
            'archived_count': archived if archive else 0,
            'report': ('Se detectaron %s grupos duplicados (RUC o referencia ERP). Revisados %s contactos secundarios. '
                       'El proceso NO elimina ni fusiona contactos con movimientos, portal o referencias.\n\n' %
                       (len(groups), examined)) + ('\n'.join(reports[:500]) or 'Sin duplicados activos de RUC.') +
                      ('\n(Informe limitado a los primeros 500 resultados)' if len(reports) > 500 else ''),
        })
        return {'type': 'ir.actions.act_window', 'res_model': self._name,
                'res_id': self.id, 'view_mode': 'form', 'target': 'new'}

    def action_analyze(self):
        return self._evaluate(False)

    def action_archive_orphans(self):
        return self.with_context(tc_confirm_safe_archive=True)._evaluate(True)
