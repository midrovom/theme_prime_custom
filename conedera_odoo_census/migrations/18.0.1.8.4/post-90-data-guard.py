def migrate(cr, version):
    cr.execute("SELECT value FROM conedera_184_guard WHERE metric='census'")
    before = cr.fetchone()[0]
    cr.execute("SELECT COUNT(*) FROM res_partner WHERE census_active IS TRUE")
    after = cr.fetchone()[0]
    if after < before:
        raise RuntimeError(f"Conedera Data Guard: catastros bajaron de {before} a {after}; se aborta la actualización.")
    cr.execute("SELECT COUNT(*) FROM res_partner WHERE census_active IS TRUE AND census_company_id IS NULL")
    missing = cr.fetchone()[0]
    if missing:
        raise RuntimeError(f"Conedera multiempresa: {missing} catastros quedaron sin Empresa del Catastro.")
