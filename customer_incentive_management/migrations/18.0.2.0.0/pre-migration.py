"""Prepare an existing 18.0.1 database for manual product/program lines.

The previous version linked each line to product.product and stored request-level
beneficiary_method/collection_method values. Version 18.0.2 replaces product
links with free-text Product No. and stores transfer/offset on each payment detail.
"""


def _table_exists(cr, table_name):
    cr.execute("SELECT to_regclass(%s)", (table_name,))
    return bool(cr.fetchone()[0])


def _column_types(cr, table_name):
    cr.execute(
        """
        SELECT column_name, data_type
          FROM information_schema.columns
         WHERE table_schema = current_schema() AND table_name = %s
        """,
        (table_name,),
    )
    return dict(cr.fetchall())


def migrate(cr, version):
    if _table_exists(cr, "incentive_request_line"):
        columns = _column_types(cr, "incentive_request_line")
        if "product_number" not in columns:
            cr.execute("ALTER TABLE incentive_request_line ADD COLUMN product_number VARCHAR")
            columns["product_number"] = "character varying"

        # Preserve a human-readable value from any existing product where possible.
        if "product_id" in columns:
            if _table_exists(cr, "product_product") and _table_exists(cr, "product_template"):
                product_columns = _column_types(cr, "product_product")
                template_columns = _column_types(cr, "product_template")
                if "product_tmpl_id" in product_columns:
                    code_expr = None
                    if "default_code" in template_columns:
                        code_expr = "pt.default_code"
                    elif "default_code" in product_columns:
                        code_expr = "pp.default_code"
                    name_expr = None
                    if "name" in template_columns:
                        name_expr = "pt.name->>'en_US'" if template_columns["name"] == "jsonb" else "pt.name"
                    choices = ["NULLIF(line.product_number, '')"]
                    if code_expr:
                        choices.append("NULLIF(%s, '')" % code_expr)
                    if name_expr:
                        choices.append("NULLIF(%s, '')" % name_expr)
                    choices.append("'LEGACY-' || line.product_id::text")
                    cr.execute(
                        """
                        UPDATE incentive_request_line AS line
                           SET product_number = COALESCE(%s)
                          FROM product_product AS pp
                          JOIN product_template AS pt ON pt.id = pp.product_tmpl_id
                         WHERE line.product_id = pp.id
                           AND (line.product_number IS NULL OR line.product_number = '')
                        """ % ", ".join(choices)
                    )
                else:
                    cr.execute(
                        "UPDATE incentive_request_line SET product_number = 'LEGACY-' || product_id::text WHERE product_number IS NULL OR product_number = ''"
                    )
            else:
                cr.execute(
                    "UPDATE incentive_request_line SET product_number = 'LEGACY-' || product_id::text WHERE product_number IS NULL OR product_number = ''"
                )

            # The new field is independent of the product addon, so drop the legacy FK/column.
            cr.execute("ALTER TABLE incentive_request_line DROP COLUMN IF EXISTS product_id CASCADE")

        if "product_number" in _column_types(cr, "incentive_request_line"):
            cr.execute(
                "UPDATE incentive_request_line SET product_number = 'LEGACY-' || id::text WHERE product_number IS NULL OR product_number = ''"
            )
        cr.execute("ALTER TABLE incentive_request_line DROP COLUMN IF EXISTS product_code CASCADE")

    # These required fields have moved from request-level to per-payment-detail method selection.
    if _table_exists(cr, "incentive_request"):
        cr.execute("ALTER TABLE incentive_request DROP COLUMN IF EXISTS beneficiary_method CASCADE")
        cr.execute("ALTER TABLE incentive_request DROP COLUMN IF EXISTS collection_method CASCADE")
