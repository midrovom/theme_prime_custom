"""Convertir applicant_name de Char a Many2one(res.partner) sin convertir texto a entero.

ANTES del registro del nuevo campo Odoo necesita una columna libre llamada
applicant_name para crear la FK. La antigua se conserva como texto histórico.
Es idempotente para actualizar distintas bases.
"""


def migrate(cr, version):
    cr.execute("""
        SELECT data_type FROM information_schema.columns
         WHERE table_schema = current_schema()
           AND table_name = 'conedera_credit_application'
           AND column_name = 'applicant_name'
    """)
    row = cr.fetchone()
    if row and row[0] in ('character varying', 'text'):
        cr.execute("""
            SELECT 1 FROM information_schema.columns
             WHERE table_schema = current_schema()
               AND table_name = 'conedera_credit_application'
               AND column_name = 'applicant_name_text'
        """)
        if cr.fetchone():
            # No sobrescribir un backup potencialmente más reciente. Reutilizar
            # la columna de texto para los datos anteriores que falten.
            cr.execute("""
                UPDATE conedera_credit_application
                   SET applicant_name_text = applicant_name
                 WHERE applicant_name_text IS NULL AND applicant_name IS NOT NULL
            """)
            cr.execute('ALTER TABLE conedera_credit_application DROP COLUMN applicant_name')
        else:
            cr.execute('ALTER TABLE conedera_credit_application RENAME COLUMN applicant_name TO applicant_name_text')
    # La ficha nueva puede aún no tener el nombre histórico; su contacto es
    # la relación Many2one obligatoria en el formulario administrativo.
    cr.execute('ALTER TABLE conedera_credit_application ALTER COLUMN applicant_name_text DROP NOT NULL')
