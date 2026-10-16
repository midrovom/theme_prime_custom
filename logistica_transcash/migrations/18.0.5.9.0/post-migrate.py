"""Reagrupar los embarques V5.8 abiertos en rutas sin mover sus guías.

No reescribe viajes que ya salieron ni liquidaciones históricas.
La ruta migrada debe recibir video del operador antes de liberar al conductor.
"""
from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Embarque = env['transcash.embarque'].sudo()
    Ruta = env['transcash.hoja.ruta'].sudo()
    Destino = env['transcash.destino'].sudo().with_context(active_test=False)
    for emb in Embarque.search([('state','=','preparacion'),('ruta_ids','=',False)]):
        if not emb.guia_ids:
            continue
        grouped = {}
        for guide in emb.guia_ids:
            code = (guide.destino_codigo or guide.destino_ciudad or ('G-%s' % guide.id)).strip().upper()
            grouped.setdefault(code, env['transcash.guia'].sudo())
            grouped[code] |= guide
        for code, guides in grouped.items():
            first = guides[0]
            # Compatible también con actualización directa desde V5.8: las rutas
            # necesitan destino del maestro desde V5.12.
            clean_code = Destino._normalizar_codigo(code)
            dest = Destino.search([('company_id','=',emb.company_id.id),
                                  ('codigo','=',clean_code)],limit=1)
            if not dest:
                dest = Destino.create({'company_id':emb.company_id.id,'codigo':clean_code,
                    'name':first.destino_ciudad or first.destino or clean_code,'fuente':'migrado'})
            route = Ruta.create({
                'name':'RUTA/MIG/%s/%s' % (emb.id, first.id),
                'company_id':emb.company_id.id,
                'chofer_usuario_id':emb.chofer_usuario_id.id,
                'proveedor_id':emb.proveedor_id.id,
                'placa':emb.placa or 'SIN-PLACA',
                'tipo_vehiculo':emb.tipo_vehiculo or 'camion',
                'origen':emb.origen,
                'destino_id':dest.id,
                'embarque_id':emb.id,
                'state':'planificada',
                'observaciones':'Ruta migrada de V5.8. Logística debe subir y validar video de carga.',
            })
            guides.write({'hoja_ruta_id':route.id})
