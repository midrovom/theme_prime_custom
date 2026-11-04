"""Permite números iguales en empresas distintas sin renumerar expedientes."""


def migrate(cr, version):
    # Odoo 18 antepone el nombre de la tabla al de _sql_constraints.
    # Cubrimos también bases donde se aplicó el nombre corto manualmente.
    cr.execute("""
        ALTER TABLE conedera_credit_application
        DROP CONSTRAINT IF EXISTS conedera_credit_application_conedera_credit_application_name_uniq
    """)
    cr.execute("""
        ALTER TABLE conedera_credit_application
        DROP CONSTRAINT IF EXISTS conedera_credit_application_name_uniq
    """)
