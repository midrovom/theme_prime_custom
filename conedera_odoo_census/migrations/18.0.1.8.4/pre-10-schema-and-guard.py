from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    cr.execute("ALTER TABLE res_partner ADD COLUMN IF NOT EXISTS census_company_id INTEGER")
    cr.execute("CREATE INDEX IF NOT EXISTS res_partner_census_company_id_idx ON res_partner (census_company_id)")
    cr.execute("SELECT COUNT(*) FROM res_partner WHERE census_active IS TRUE")
    cr.execute("CREATE TEMP TABLE IF NOT EXISTS conedera_184_guard (metric varchar primary key, value bigint)")
    cr.execute("INSERT INTO conedera_184_guard(metric,value) VALUES ('census', %s) ON CONFLICT(metric) DO UPDATE SET value=EXCLUDED.value", [cr.fetchone()[0]])
