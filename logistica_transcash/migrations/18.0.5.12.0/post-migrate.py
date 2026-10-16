"""V5.12: link historical guide/route/tariff text codes to the destination master.
Keep historical monetary snapshots and states untouched.
"""
from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Dest = env['transcash.destino'].sudo().with_context(active_test=False)
    for model in ('transcash.guia', 'transcash.tarifa.traslado', 'transcash.hoja.ruta'):
        for record in env[model].sudo().with_context(active_test=False).search([('destino_id','=',False)]):
            code = (record.destino_codigo or '').strip().upper()
            if not code:
                # A legacy guide without ERP code is kept exactly as-is.
                continue
            try:
                code = Dest._normalizar_codigo(code)
            except Exception:
                continue  # Manual review of obsolete invalid codes.
            company_id = record.company_id.id
            destination = Dest.search([('company_id','=',company_id),('codigo','=',code)],limit=1)
            if not destination:
                name = ((getattr(record, 'destino_nombre', False) or
                         getattr(record, 'destino_ciudad', False) or
                         getattr(record, 'destino', False) or code)).strip()
                destination = Dest.create({'company_id':company_id,'codigo':code,
                    'name':name,'ciudad':name,'fuente':'migrado'})
            # SQL avoids triggering operational write guards and changing trip histories.
            cr.execute('UPDATE %s SET destino_id = %%s WHERE id = %%s' % record._table,
                       (destination.id, record.id))
