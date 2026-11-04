def migrate(cr, version):
    # Los dos valores históricos se asociarán al catálogo configurable.
    cr.execute("""
        UPDATE conedera_credit_reference AS ref
           SET account_type_id = typ.id
          FROM conedera_credit_bank_account_type AS typ
         WHERE ref.account_type_id IS NULL
           AND ref.account_type IS NOT NULL
           AND ref.account_type = typ.code
    """)
