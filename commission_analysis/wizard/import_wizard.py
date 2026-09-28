import base64, hashlib, io, struct
from datetime import datetime
from odoo import fields, models, _
from odoo.exceptions import UserError

MONTHS={'ene':1,'feb':2,'mar':3,'abr':4,'may':5,'jun':6,'jul':7,'ago':8,'sept':9,'sep':9,'oct':10,'nov':11,'dic':12}
CHUNK=1000

def icc_key(value):
    s=''.join(ch for ch in str(value or '').strip() if ch.isdigit())
    return s[:18] if len(s)>=18 else s

def pdate(v):
    if not v:return False
    if isinstance(v,datetime):return v.date()
    if hasattr(v,'year') and not isinstance(v,str):return v
    s=str(v).strip().lower().replace(',','')
    for k,m in MONTHS.items():
        if s.startswith(k+' '):
            a=s.split(); return datetime(int(a[-1]),m,int(a[-2])).date()
    for f in ('%Y-%m-%d','%d/%m/%Y','%m/%d/%Y'):
        try:return datetime.strptime(s,f).date()
        except ValueError:pass
    return False

def dbf_rows(data):
    if len(data)<64: raise UserError(_('El archivo de compras no tiene una estructura DBF válida.'))
    header_len=struct.unpack('<H',data[8:10])[0]; record_len=struct.unpack('<H',data[10:12])[0]; fieldspec=[]; pos=32
    while pos < header_len and data[pos]!=0x0D:
        d=data[pos:pos+32]; name=d[:11].split(b'\x00')[0].decode('latin1').strip(); typ=chr(d[11]); ln=d[16]; dec=d[17]; fieldspec.append((name,typ,ln,dec)); pos+=32
    n=struct.unpack('<I',data[4:8])[0]
    for idx in range(n):
        rec=data[header_len+idx*record_len:header_len+(idx+1)*record_len]
        if not rec or rec[:1]==b'*':continue
        out={}; p=1
        for fname,typ,ln,dec in fieldspec:
            raw=rec[p:p+ln];p+=ln;s=raw.decode('latin1','ignore').strip()
            if typ in 'NF':
                try:out[fname]=float(s) if s else 0
                except ValueError:out[fname]=0
            elif typ=='D' and len(s)==8:
                try:out[fname]=datetime.strptime(s,'%Y%m%d').date()
                except ValueError:out[fname]=False
            else:out[fname]=s
        yield idx+1,out

class CommissionImportWizard(models.TransientModel):
    _name='commission.import.wizard';_description='Importar Compras / Liquidaciones'
    import_type=fields.Selection([('purchase','Compras'),('settlement','Liquidación Claro')],required=True,default='settlement')
    purchase_batch_id=fields.Many2one('commission.purchase.batch');settlement_batch_id=fields.Many2one('commission.settlement.batch');file_ids=fields.Many2many('ir.attachment',string='Archivos',required=True)

    def action_import(self):
        self.ensure_one()
        if self.import_type=='purchase' and not self.purchase_batch_id:raise UserError(_('Seleccione un lote de compras.'))
        if self.import_type=='settlement' and not self.settlement_batch_id:raise UserError(_('Seleccione una liquidación.'))
        for att in self.file_ids:
            data=base64.b64decode(att.datas);sha=hashlib.sha256(data).hexdigest()
            if self.env['commission.import.file'].search_count([('sha256','=',sha)]):raise UserError(_('El archivo %s ya fue importado.')%att.name)
            count=self._import_purchase(att.name,data) if self.import_type=='purchase' else self._import_settlement(att.name,data)
            self.env['commission.import.file'].create({'name':att.name,'sha256':sha,'attachment_id':att.id,'purchase_batch_id':self.purchase_batch_id.id if self.import_type=='purchase' else False,'settlement_batch_id':self.settlement_batch_id.id if self.import_type=='settlement' else False,'row_count':count})
        return {'type':'ir.actions.client','tag':'reload'}

    def _warehouse_mapping(self, code, name):
        M=self.env['commission.warehouse.mapping']; dom=['|',('warehouse_code','=',str(code or '').strip()),('warehouse_name','=ilike',str(name or '').strip())]
        return M.search(dom,limit=1)

    def _import_purchase(self,name,data):
        Sim=self.env['commission.sim'];Line=self.env['commission.purchase.line'];count=0; buffer=[]; mapping_cache={}
        def flush(rows):
            nonlocal count
            if not rows:return
            keys=list({v['icc_key'] for v in rows}); existing={x.icc_key:x for x in Sim.search([('icc_key','in',keys)])}
            newvals=[]; seen_new=set()
            for v in rows:
                if v['icc_key'] not in existing and v['icc_key'] not in seen_new:
                    seen_new.add(v['icc_key'])
                    key=(str(v['warehouse_code'] or ''),str(v['warehouse_name'] or '')); mp=mapping_cache.get(key);
                    if key not in mapping_cache: mp=self._warehouse_mapping(*key); mapping_cache[key]=mp
                    newvals.append({'icc':v['icc'],'icc_key':v['icc_key'],'purchase_date':v['date'],'invoice':v['invoice'],'warehouse':v['warehouse_name'],'product':v['product_name'],'purchase_cost':v['cost'],'region_id':mp.region_id.id if mp else False,'zone_id':mp.zone_id.id if mp else False})
            if newvals:
                for sim in Sim.create(newvals):existing[sim.icc_key]=sim
            linevals=[]
            for v in rows:
                sim=existing[v['icc_key']]; key=(str(v['warehouse_code'] or ''),str(v['warehouse_name'] or '')); mp=mapping_cache.get(key)
                if key not in mapping_cache: mp=self._warehouse_mapping(*key); mapping_cache[key]=mp
                v.update({'sim_id':sim.id,'region_id':mp.region_id.id if mp else sim.region_id.id,'zone_id':mp.zone_id.id if mp else sim.zone_id.id});linevals.append(v)
            Line.create(linevals);count+=len(linevals)
        for rownum,r in dbf_rows(data):
            icc=str(r.get('CHIP') or '').strip()
            if not icc:continue
            buffer.append({'icc':icc,'icc_key':icc_key(icc),'date':r.get('FECHA'),'document_type':r.get('TIPO'),'number':r.get('NUMERO'),'supplier_code':r.get('PROVEEDOR'),'supplier_name':r.get('NPROVEEDOR'),'invoice':r.get('FACTURA'),'warehouse_code':r.get('BODEGA'),'warehouse_name':r.get('NBODEGA'),'product_code':r.get('PRODUCTO'),'product_name':r.get('NPRODUCTO'),'quantity':r.get('CANTIDAD') or 1,'cost':r.get('COSTO') or 0,'discount':r.get('DESCUENTO') or 0,'tax':r.get('IMPUESTO') or 0,'source_file':name,'source_row':rownum,'batch_id':self.purchase_batch_id.id})
            if len(buffer)>=CHUNK:flush(buffer);buffer=[]
        flush(buffer);self.purchase_batch_id.state='processed';return count

    def _import_settlement(self,name,data):
        try:from openpyxl import load_workbook
        except ImportError:raise UserError(_('Se requiere la librería Python openpyxl.'))
        ws=load_workbook(io.BytesIO(data),read_only=True,data_only=True).active
        top=list(next(ws.iter_rows(min_row=1,max_row=1,values_only=True)));hdr=list(next(ws.iter_rows(min_row=2,max_row=2,values_only=True)))
        headers=[hdr[i] if i<len(hdr) and hdr[i] else (top[i] if i<len(top) else None) for i in range(max(len(top),len(hdr)))]
        idx={str(v).strip():i for i,v in enumerate(headers) if v};required={'Compensation Date','Región','Concepto','Simcard','Porcentaje','Consumo Evaluado','Valor'}
        missing=required-set(idx)
        if missing:raise UserError(_('Faltan columnas requeridas en %s: %s')%(name,', '.join(sorted(missing))))
        Line=self.env['commission.settlement.line'];Sim=self.env['commission.sim'];Region=self.env['commission.region'];count=0;buffer=[];region_cache={}
        def g(row,key):
            i=idx.get(key);return row[i] if i is not None and i<len(row) else None
        def region(name):
            key=str(name or '').strip()
            if not key:return False
            if key not in region_cache:region_cache[key]=Region.search([('name','=ilike',key)],limit=1) or Region.create({'name':key})
            return region_cache[key]
        def flush(rows):
            nonlocal count
            if not rows:return
            keys=list({v['icc_key'] for v in rows});sims={s.icc_key:s for s in Sim.search([('icc_key','in',keys)])}
            for v in rows:
                sim=sims.get(v['icc_key']);v['sim_id']=sim.id if sim else False
                if sim and not v.get('zone_id'):v['zone_id']=sim.zone_id.id
            recs=Line.create(rows);recs._recalculate_expected_bulk();count+=len(rows)
        for rownum,row in enumerate(ws.iter_rows(min_row=3,values_only=True),3):
            icc=str(g(row,'Simcard') or '').strip()
            if not icc:continue
            reg=region(g(row,'Región'))
            buffer.append({'batch_id':self.settlement_batch_id.id,'icc':icc,'icc_key':icc_key(icc),'compensation_date':pdate(g(row,'Compensation Date')),'region_text':g(row,'Región'),'region_id':reg.id if reg else False,'customer':g(row,'Cliente'),'product':g(row,'Producto'),'concept':g(row,'Concepto'),'service_number':g(row,'Número Servicio'),'activation_date':pdate(g(row,'Fecha Activación')),'regularization_date':pdate(g(row,'Fecha Regularización')),'high_date':pdate(g(row,'Fecha Alta')),'distributor_type':g(row,'Tipo Distribuidor'),'invoice':g(row,'No. Factura'),'pvp':g(row,'PVP') or 0,'reported_percentage':g(row,'Porcentaje') or 0,'recharges':g(row,'Recargas') or 0,'consumptions':g(row,'Consumos') or 0,'base_tariff':g(row,'Tarifa Básica') or 0,'evaluated_consumption':g(row,'Consumo Evaluado') or 0,'reported_value':g(row,'Valor') or 0,'discounted_base_tariff':g(row,'Tarifa Básica Descontada') or 0,'advance_value':g(row,'Valor Anticipo') or 0,'source_file':name,'source_row':rownum})
            if len(buffer)>=CHUNK:flush(buffer);buffer=[]
        flush(buffer);self.settlement_batch_id.state='processed';return count
