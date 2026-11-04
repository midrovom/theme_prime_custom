"""Remove only the old one-file-per-requirement unique constraint before module upgrade."""

def migrate(cr, version):
    cr.execute("""
        SELECT con.conname
          FROM pg_constraint con
          JOIN pg_class rel ON rel.oid = con.conrelid
         WHERE rel.relname = 'conedera_credit_document_line'
           AND con.contype = 'u'
           AND pg_get_constraintdef(con.oid) LIKE 'UNIQUE (document_id, requirement_id)%'
    """)
    for (name,) in cr.fetchall():
        # Identifiers obtained from pg_constraint; quote escaping for safety.
        cr.execute('ALTER TABLE conedera_credit_document_line DROP CONSTRAINT "%s"' % name.replace('"', '""'))
