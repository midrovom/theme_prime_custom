import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Create newly introduced res.partner columns before model loading.

    This release is intentionally defensive because res.partner is read by
    Website and many other modules during normal requests. If new Python code
    is deployed before the module is upgraded, those requests can fail with
    UndefinedColumn. The normal ORM update will still register/validate the
    fields afterwards.
    """
    columns = {
        "owner_contact_name": "varchar",
        "commercial_contact_name": "varchar",
        "business_description": "varchar",
        "customer_segment": "varchar",
    }
    for name, sql_type in columns.items():
        cr.execute(
            f'ALTER TABLE res_partner ADD COLUMN IF NOT EXISTS "{name}" {sql_type}'
        )
        _logger.info("Ensured res_partner.%s exists", name)
