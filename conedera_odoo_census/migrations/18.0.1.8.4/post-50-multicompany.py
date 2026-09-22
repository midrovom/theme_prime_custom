from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    main_company = env.ref('base.main_company', raise_if_not_found=False) or env['res.company'].search([], limit=1)
    cr.execute("""
        UPDATE res_partner p
           SET census_company_id = COALESCE(
               (SELECT t.company_id FROM crm_team t WHERE t.id = p.census_team_id),
               p.company_id,
               (SELECT u.company_id FROM res_users u WHERE u.id = COALESCE(p.user_id, p.census_user_id)),
               %s
           )
         WHERE p.census_active IS TRUE
           AND p.census_company_id IS NULL
    """, [main_company.id if main_company else None])
    cr.execute("UPDATE res_partner SET census_company_id = %s WHERE census_active IS TRUE AND census_company_id IS NULL", [main_company.id if main_company else None])
    # Team/company consistency: keep only a team from the Catastro company; otherwise let ORM/UI reassign it.
    cr.execute("""
        UPDATE res_partner p
           SET census_team_id = NULL
          FROM crm_team t
         WHERE p.census_active IS TRUE
           AND p.census_team_id = t.id
           AND (t.company_id IS NULL OR t.company_id IS DISTINCT FROM p.census_company_id)
    """)
    # Enabled Catastro teams must be company-specific. Disable ambiguous shared teams rather than guessing a company.
    cr.execute("UPDATE crm_team SET census_enabled = FALSE WHERE census_enabled IS TRUE AND company_id IS NULL")
