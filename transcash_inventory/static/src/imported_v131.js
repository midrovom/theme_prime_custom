(()=>{'use strict';const $=id=>document.getElementById(id), S={kind:'productos',page:1,total:0,limit:50};
const cols={productos:['SKU','Descripción','Categoría','Marca','Formato','Proveedor catálogo','Costo unit.','Precio','Stock cant.','Stock $'],
ventas:['Período','SKU','Descripción','Vendido cant.','Ventas $','Costo ventas $','Utilidad $'],
compras:['Período','SKU','Descripción','Comprado cant.','Compras $'],
proveedores:['Período','SKU','Descripción','Proveedor real','Compras $'],
stock:['SKU','Descripción','Bodega','Stock cant.','Costo unit.','Valor $']};
const numbers={productos:new Set([6,7,8,9]),ventas:new Set([3,4,5,6]),compras:new Set([3,4]),proveedores:new Set([4]),stock:new Set([3,4,5])};
function renderRows(rows){$('head').replaceChildren();$('body').replaceChildren();const hr=document.createElement('tr');for(const name of cols[S.kind]){const th=document.createElement('th');th.textContent=name;hr.append(th)}$('head').append(hr);for(const row of rows){const tr=document.createElement('tr');row.forEach((val,i)=>{const td=document.createElement('td');if(numbers[S.kind].has(i)&&Number.isFinite(Number(val))){td.className='numeric';td.textContent=new Intl.NumberFormat('es-EC',{maximumFractionDigits:2}).format(Number(val));}else td.textContent=String(val??'');tr.append(td)});$('body').append(tr)}if(!rows.length){const tr=document.createElement('tr'),td=document.createElement('td');td.colSpan=cols[S.kind].length;td.textContent='Sin registros para los filtros seleccionados.';tr.append(td);$('body').append(tr)}}
let controller=null;
async function load(){if(controller)controller.abort();controller=new AbortController();$('info').textContent='Consultando registros almacenados en Odoo...';$('info').classList.remove('error');
const params=new URLSearchParams({kind:S.kind,page:String(S.page),limit:String(S.limit),sku:$('sku').value.trim()});
if(['ventas','compras','proveedores'].includes(S.kind)){if($('from').value)params.set('from',$('from').value);if($('to').value)params.set('to',$('to').value)}
try{const r=await fetch('/transcash_inventory/imported/rows?'+params,{credentials:'same-origin',cache:'no-store',signal:controller.signal});const data=await r.json();if(!r.ok||data.error)throw Error(data.error||'Error al recuperar registros.');
S.total=data.count;$('meta').textContent='Versión vigente #'+data.snapshot_id+' · Origen: '+(data.source||'Carga')+' · Fecha: '+data.imported_at+' · Período disponible: '+data.period_start+' a '+data.period_end;
renderRows(data.rows);$('info').textContent='Registros actuales de '+S.kind+'. Los filtros por fecha aplican a ventas y compras; el stock es al último corte.';
$('count').textContent=new Intl.NumberFormat('es-EC').format(S.total)+' registros';$('pg').textContent='Página '+S.page+' de '+Math.max(1,Math.ceil(S.total/S.limit));$('prev').disabled=S.page===1;$('next').disabled=S.page>=Math.ceil(S.total/S.limit);
}catch(e){if(e.name==='AbortError')return;$('info').textContent=e.message;$('info').classList.add('error');renderRows([])} }
$('tabs').addEventListener('click',e=>{const b=e.target.closest('[data-kind]');if(!b)return;S.kind=b.dataset.kind;S.page=1;document.querySelectorAll('[data-kind]').forEach(n=>n.classList.toggle('active',n===b));const monthly=['ventas','compras','proveedores'].includes(S.kind);$('from').disabled=!monthly;$('to').disabled=!monthly;load()});
$('apply').addEventListener('click',()=>{S.page=1;load()});$('clear').addEventListener('click',()=>{$('sku').value=$('from').value=$('to').value='';S.page=1;load()});
$('sku').addEventListener('keydown',e=>{if(e.key==='Enter'){S.page=1;load()}});$('prev').addEventListener('click',()=>{S.page=Math.max(1,S.page-1);load()});$('next').addEventListener('click',()=>{if(S.page*S.limit<S.total){S.page++;load()}});

$('exportExcel').addEventListener('click',async()=>{
 const button=$('exportExcel'),label=button.textContent;
 button.disabled=true;button.textContent='Preparando Excel…';
 try{
  const csrf=document.querySelector('meta[name="transcash-csrf"]')?.content;
  if(!csrf)throw new Error('Sesión expirada. Abra de nuevo Datos importados.');
  const body=new FormData();body.append('csrf_token',csrf);body.append('company_id',document.querySelector('meta[name="transcash-company-id"]')?.content||'');body.append('kind',S.kind);
  body.append('sku',$('sku').value.trim());
  if(['ventas','compras','proveedores'].includes(S.kind)){
   body.append('from',$('from').value);body.append('to',$('to').value);
  }
  const resp=await fetch('/transcash_inventory/imported/export_xlsx',{method:'POST',body,credentials:'same-origin'});
  if(!resp.ok){const data=await resp.json().catch(()=>({}));throw Error(data.error||'No se pudo generar el archivo.');}
  const blob=await resp.blob(),url=URL.createObjectURL(blob),link=document.createElement('a');
  link.href=url;link.download='Transcash_Datos_'+S.kind+'.xlsx';document.body.append(link);link.click();link.remove();
  setTimeout(()=>URL.revokeObjectURL(url),30000);
 }catch(e){$('info').textContent=e.message;$('info').classList.add('error');}
 finally{button.disabled=false;button.textContent=label;}
});

$('from').disabled=true;$('to').disabled=true;load();})();