// La importación se realiza exclusivamente desde Inventario Inteligente → Cargar archivos.
// No existen modales de carga en la visualización web.
function showUnavailable(message) {
 const title=document.getElementById('tcStatusTitle');
 const text=document.getElementById('tcStatusText');
 if(title)title.textContent='No hay información disponible';
 if(text)text.textContent=(message||'No se encontraron datos.')+' Abre Inventario Inteligente → Cargar archivos desde el menú de Odoo para importar el Excel.';
}
(async()=>{
 let response;
 const id=new URLSearchParams(window.location.search).get('snapshot_id');
 const datasetUrl='/transcash_inventory/data'+(id && /^\d+$/.test(id)?'?snapshot_id='+id:'');
 try {response=await fetch(datasetUrl,{credentials:'same-origin',cache:'no-store'});
 if(!response.ok){const err=await response.json().catch(()=>({}));showUnavailable(err.error||'No se pudo cargar la información.');return;}}
 catch(e){showUnavailable('No se pudo obtener la información del servidor Odoo: '+e.message);return;}
 const DATA=await response.json();
 if(!DATA.products||!DATA.months||!DATA.months.length){showUnavailable('La última importación está incompleta.');return;}
 document.getElementById('tcStatusArea').hidden=true;
 document.body.classList.remove('tc-awaiting-data');
 const allowAI=document.querySelector('meta[name="transcash-can-ai"]')?.content==='true';
 document.getElementById('navAI').hidden=!allowAI;
 const firstMonth=DATA.months[0],lastMonth=DATA.months[DATA.months.length-1];
 const suspiciousStock=DATA.summary.stock_catalogo>0&&(DATA.summary.stock_fuente>DATA.summary.stock_catalogo*2||DATA.summary.stock_fuente<DATA.summary.stock_catalogo*.1);
 const risk=document.querySelector('.risk-banner');
 if(risk&&!suspiciousStock){risk.innerHTML='<div class="alerticon">ⓘ</div><div><b>Valoración provisional.</b> El stock se estima con existencias positivas × costo de catálogo. Es necesario conciliarlo con el Kardex, confirmar fecha de corte y disponer de cierres históricos para rotación contable y GMROI.</div>';}

 document.querySelector('.version').textContent='TRANSCASH · Corte '+lastMonth;
 document.querySelector('#period option[value="26"]').textContent='Acumulado '+lastMonth.substring(0,4);
 document.querySelector('#period option[value="25"]').textContent='Año anterior comparable';
 document.querySelector('#period option[value="all"]').textContent='Todo el histórico ('+firstMonth+' a '+lastMonth+')';
const $=id=>document.getElementById(id),C={green:'#10a794',blue:'#3979ef',amber:'#f0ac4b',red:'#e05b6a',ink:'#253a51',gray:'#92a1b3'};const months=DATA.months;const refLast=months.length-1;const refMonth=months[refLast];const refYear=Number(refMonth.substring(0,4));const refNumber=Number(refMonth.substring(5));const prevYear=refYear-1;const refDays3=Array.from({length:3},(_,k)=>{const d=new Date(refYear,refNumber-k,0);return d.getDate()}).reduce((a,b)=>a+b,0);const monthLabels=months.map(m=>{let d=m.split('-');return new Date(+d[0],+d[1]-1,1).toLocaleDateString('es-EC',{month:'short',year:'2-digit'}).replace('.','')});const stockWare=Array.from({length:DATA.products.length},()=>[]);for(const [i,w,q] of DATA.stockWarehouses)stockWare[i].push([w,q]);const saleBySku=Array.from({length:DATA.products.length},()=>[]);for(const [i,m,q,rev,cogs] of DATA.sales)saleBySku[i].push([m,q,rev,cogs]);const buyBySku=Array.from({length:DATA.products.length},()=>[]);for(const [i,m,q,amt] of DATA.purchases)buyBySku[i].push([m,q,amt]);const suppBySku=Array.from({length:DATA.products.length},()=>[]);for(const [i,m,s,amt] of DATA.supplierPurchases)suppBySku[i].push([m,s,amt]);
// Fotos de Transcash.ec: el dashboard siempre consulta un índice privado de Odoo por SKU.
const photoCache=new Map();
const photoQueriedAt=new Map();
const photoPending=new Set();
const photoQueueSent=new Set();
const PHOTO_REFRESH_MS=2*60*1000;
// SKU photos are looked up as soon as the explorer is rendered. No manual click needed.

async function fetchPhotoRefs(skus){
 const now=Date.now();
 const need=[...new Set(skus)].filter(s=>!photoPending.has(s)&&(!photoQueriedAt.has(s)||now-photoQueriedAt.get(s)>PHOTO_REFRESH_MS)).slice(0,80);
 if(!need.length)return;
 for(const sku of need){photoPending.add(sku);photoQueriedAt.set(sku,now);}
 document.querySelectorAll('[data-photo-sku]').forEach(node=>renderPhoto(node));
 try{
  const response=await fetch('/transcash_inventory/photos?skus='+encodeURIComponent(JSON.stringify(need)),{credentials:'same-origin',cache:'no-store'});
  if(!response.ok)throw new Error('Imagen no disponible');
  const data=await response.json();
  for(const sku of need)photoCache.set(sku,(data.images||{})[sku]||null);
  document.querySelectorAll('[data-photo-sku]').forEach(node=>renderPhoto(node));
  // Missing photos are queued only for authorised inventory managers.
  // Rendering never waits for remote shop requests.
  const csrf=document.querySelector('meta[name="transcash-csrf"]')?.content;
  if(document.querySelector('meta[name="transcash-can-upload"]')?.content==='1' && csrf){
   const missing=need.filter(s=>!photoQueueSent.has(s) && data.images?.[s]?.status!=='verified' && data.images?.[s]?.status!=='queued').slice(0,40);
   if(missing.length){missing.forEach(s=>photoQueueSent.add(s));
    const body=new FormData();body.append('csrf_token',csrf);body.append('skus',JSON.stringify(missing));
    fetch('/transcash_inventory/photos/queue',{method:'POST',credentials:'same-origin',body}).catch(e=>console.info('Cola de fotos:',e.message));
   }
  }
 }catch(e){console.warn('No se pudieron consultar las imágenes:',e.message);
  for(const sku of need)photoQueriedAt.delete(sku);
 }finally{for(const sku of need)photoPending.delete(sku);
  document.querySelectorAll('[data-photo-sku]').forEach(node=>renderPhoto(node));}
}
function renderPhoto(node){
 const sku=node.getAttribute('data-photo-sku'),photo=photoCache.get(sku);
 const isLarge=node.classList.contains('tc-photo-large');
 // Do not replace loaded <img> on every filter change; this avoids a visual flash.
 if(photo?.image_url&&(/^(?:https:\/\/(?:www\.)?transcash\.ec\/web\/(?:image|content)\/|\/transcash_inventory\/photos\/thumb\?sku=)/i.test(photo.image_url))){
  const existing=node.querySelector('img');
  if(existing&&existing.getAttribute('src')===photo.image_url)return;
  node.innerHTML='<img src="'+escapeHtml(photo.image_url)+'" alt="Fotografía de '+escapeHtml(sku)+'" loading="eager" decoding="async" referrerpolicy="no-referrer"/>'+(isLarge?'<a href="'+escapeHtml(photo.website_url||'https://www.transcash.ec/shop')+'" target="_blank" rel="noopener noreferrer">Ver producto en Transcash.ec ↗</a>':'');
  const img=node.querySelector('img');
  img.addEventListener('error',()=>{node.innerHTML=isLarge?'<span>Imagen no disponible en el sitio</span>':'<span title="La foto vinculada no pudo descargarse">◫</span>';},{once:true});
 }else if(photoPending.has(sku)){
  node.innerHTML='<span class="tc-photo-loading" title="Cargando foto vinculada...">◌</span>';
 }else if(!photo?.image_url){
  const reason=photo?.status==='not_found'?'SKU no encontrado en tienda':photo?.status==='error'?'Error de conexión; se reintentará':photo?.status==='broken'?'La imagen necesita revisión':photo?.status==='queued'?'Búsqueda en cola':'Sin fotografía vinculada';
  node.innerHTML=isLarge?'<span>'+escapeHtml(reason)+'</span>':'<span title="'+escapeHtml(reason)+'">◫</span>';
 }
}
// La fuente no trae U.M. explícita. Solo inferimos cuando el nombre lo declara,
// sin convertir cajas/piezas ni suponer que todo revestimiento se vende en m².
function unitForProduct(product){
 const raw=String(product[20]||'').trim();
 if(raw)return {label:raw,confirmed:true};
 const desc=String(product[1]||'').toUpperCase();
 if(/(?:^|[^A-Z0-9])(?:M2|M²|MT2|MTS2|METROS? CUADRADOS?)(?:$|[^A-Z0-9])/i.test(desc))return {label:'m²*',confirmed:false};
 if(/(?:^|[^A-Z0-9])(?:UND|UNID|UNIDAD(?:ES)?)(?:$|[^A-Z0-9])/i.test(desc))return {label:'und.*',confirmed:false};
 return {label:'s/d',confirmed:false};
}
function qtyCell(quantity,p){
 const unit=unitForProduct(p);
 const note=unit.confirmed?'Unidad indicada en catálogo':unit.label==='s/d'?'Unidad de medida no informada en el Excel':'* Unidad inferida de la descripción, verificar antes de convertir';
 return '<span class="tc-qty" title="'+escapeHtml(note)+'">'+fmt(quantity,2)+' <span class="tc-unit">'+escapeHtml(unit.label)+'</span></span>';
}

// El formato exacto se conserva desde la v1.7. Los historiales importados
// previamente no lo incluían: se recupera una medida si está en el nombre.
function normalizeFormat(raw){
 const value=String(raw||'').trim();
 if(!value)return '';
 return value.toLocaleUpperCase('es').replace(/(\d)\s*[x×*]\s*(\d)/gi,'$1×$2').replace(/(\d),(\d)/g,'$1.$2').replace(/\s+/g,' ').trim();
}
function productFormat(p){
 if(p[21]&&String(p[21]).trim())return normalizeFormat(p[21]);
 const match=String(p[1]||'').match(/(\d{1,4}(?:[.,]\d{1,2})?)\s*[x×*]\s*(\d{1,4}(?:[.,]\d{1,2})?)/i);
 return match?normalizeFormat(match[0]):'SIN FORMATO IDENTIFICABLE';
}
const explorerFormatExact=DATA.products.some(p=>p.length>21 && String(p[21]||'').trim());
const explorerFormatBySku=DATA.products.map(productFormat);
const explorerFormats=[...new Set(explorerFormatBySku)].sort((a,b)=>a.localeCompare(b,'es',{numeric:true}));
const explorerFormatIndexes=new Map(explorerFormats.map((value,i)=>[value,i]));
const explorerFormatIdBySku=explorerFormatBySku.map(f=>explorerFormatIndexes.get(f));
let st={period:'12',start:Math.max(0,refLast-11),end:refLast,cat:-1,brand:-1,wh:-1,providerExp:-1,formatExp:-1,search:'',action:-1,abcFilter:'all',goalDays:60,page:'resumen',pagenum:0,pageSize:25,sort:'rev',desc:true,xyzCell:'all',xyzPage:0,xyzPageSize:25,xyzSort:'rev',xyzDesc:true},view=null;const fmt=(v,d=0)=>new Intl.NumberFormat('es-EC',{minimumFractionDigits:d,maximumFractionDigits:d}).format(v||0),usd=(v,d=0)=>v<0?'-$'+fmt(-v,d):'$'+fmt(v,d),pct=(v,d=1)=>fmt(v*100,d)+' %',compact=v=>{let a=Math.abs(v),sg=v<0?'-':'';return a>=1e6?sg+'$'+fmt(a/1e6,2)+' M':a>=1e3?sg+'$'+fmt(a/1e3,1)+' mil':usd(v)},escapeHtml=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));const median=(arr)=>{const a=[...arr].sort((x,y)=>x-y);return a.length?(a.length%2?a[(a.length-1)/2]:(a[a.length/2-1]+a[a.length/2])/2):0};
function fillSelect(id,arr,all){$(id).innerHTML='<option value="-1">'+all+'</option>'+arr.map((x,i)=>'<option value="'+i+'">'+escapeHtml(x)+'</option>').join('')};fillSelect('cat',DATA.categories,'Todas las categorías');fillSelect('brand',DATA.brands,'Todas las marcas');fillSelect('wh',DATA.warehouses,'Todas las bodegas');$('from').innerHTML=months.map((m,i)=>'<option value="'+i+'">'+m+'</option>').join('');$('to').innerHTML=$('from').innerHTML;$('from').value=st.start;$('to').value=st.end;
// Buscadores con listas desplegables para valores extensos.
const expConfigs={
 provider:{input:'expProviderInput',menu:'expProviderOptions',options:DATA.providers,label:'Todos los proveedores'},
 format:{input:'expFormatInput',menu:'expFormatOptions',options:explorerFormats,label:'Todos los formatos'},
 brand:{input:'expBrandInput',menu:'expBrandOptions',options:DATA.brands,label:'Todas las marcas'}
};
let openExpCombo=null;
const activeExpOption={provider:0,format:0,brand:0};
function expSelected(type){return type==='provider'?st.providerExp:type==='format'?st.formatExp:st.brand;}
function expNormal(text){return String(text||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLocaleLowerCase('es').replace(/(\d)\s*[x×*]\s*(\d)/g,'$1x$2').replace(/(\d),(\d)/g,'$1.$2').trim();}
function expSyncValues(){
 for(const [type,config] of Object.entries(expConfigs)){
  if(openExpCombo===type)continue;
  const index=expSelected(type);
  $(config.input).value=index<0?'':config.options[index]||'';
 }
}
function expClose(type,restore=true){
 if(!expConfigs[type])return;
 const conf=expConfigs[type];$(conf.menu).hidden=true;$(conf.input).setAttribute('aria-expanded','false');
 if(restore){const index=expSelected(type);$(conf.input).value=index<0?'':conf.options[index]||'';}
 if(openExpCombo===type)openExpCombo=null;
}
function expOpen(type){
 if(openExpCombo&&openExpCombo!==type)expClose(openExpCombo);
 openExpCombo=type;
 const conf=expConfigs[type];$(conf.menu).hidden=false;$(conf.input).setAttribute('aria-expanded','true');
 expRenderOptions(type);
}
function expRenderOptions(type){
 const conf=expConfigs[type],filter=expNormal($(conf.input).value);
 // Cuando el usuario enfoca un valor ya seleccionado se ofrece toda la lista.
 const selectedText=conf.options[expSelected(type)]||'';
 const searching=filter&&expNormal(selectedText)!==filter;
 let matches=[];
 for(let i=0;i<conf.options.length;i++){
  if(!searching||expNormal(conf.options[i]).includes(filter))matches.push(i);
 }
 const max=70,shown=matches.slice(0,max),withAll=!searching;
 const items=(withAll?[-1]:[]).concat(shown);
 activeExpOption[type]=0;
 const mark=index=>index===expSelected(type)?'true':'false';
 $(conf.menu).innerHTML=items.map((index,pos)=>'<button type="button" role="option" id="'+conf.menu+'Opt'+pos+'" class="tc-combo-option'+(pos===0?' is-active':'')+'" aria-selected="'+mark(index)+'" data-exp-select="'+type+'" data-index="'+index+'">'+escapeHtml(index<0?conf.label:conf.options[index])+'</button>').join('')
   +(matches.length>max?'<div class="tc-combo-msg">Mostrando '+max+' de '+matches.length+' opciones. Escribe más para precisar.</div>':'')
   +(items.length===0?'<div class="tc-combo-msg">No hay coincidencias con esa búsqueda.</div>':'');
}
function expSet(type,index){
 const conf=expConfigs[type];
 if(!Number.isInteger(index)||index<-1||index>=conf.options.length)return;
 if(type==='provider')st.providerExp=index;
 else if(type==='format')st.formatExp=index;
 else{st.brand=index;$('brand').value=String(index);}
 expClose(type,false);
 expSyncValues();
 st.pagenum=0;st.xyzPage=0;
 if(type==='brand')update();else if(st.page==='xyz')renderXYZ();else renderProducts();
}
function expFilterRows(){
 return view.rows.filter(r=>(st.action<0||r.action===st.action)
  &&(st.abcFilter==='all'||r.abc===st.abcFilter)
  &&(st.providerExp<0||r.p[4]===st.providerExp)
  &&(st.formatExp<0||explorerFormatIdBySku[r.i]===st.formatExp));
}
function expStatus(count){
 const active=[];
 if(st.providerExp>=0)active.push('Proveedor: '+DATA.providers[st.providerExp]);
 if(st.formatExp>=0)active.push('Formato: '+explorerFormats[st.formatExp]);
 if(st.brand>=0)active.push('Marca: '+DATA.brands[st.brand]);
 $('expFilterStatus').textContent=fmt(count)+' productos encontrados'+(active.length?' · '+active.join(' · '):'')
  +(!explorerFormatExact?' · Formato inferido de descripción: reimporta el Excel para recuperar el formato exacto.':'');
}
function expInit(){
 for(const [type,conf] of Object.entries(expConfigs)){
  const input=$(conf.input), menu=$(conf.menu);
  input.addEventListener('focus',()=>expOpen(type));
  input.addEventListener('input',()=>expOpen(type));
  input.addEventListener('keydown',e=>{
   const opts=[...menu.querySelectorAll('[data-exp-select]')];
   if(e.key==='Escape'){expClose(type);input.blur();return;}
   if(e.key==='ArrowDown'||e.key==='ArrowUp'){
    e.preventDefault();if(openExpCombo!==type)expOpen(type);
    const nodes=[...menu.querySelectorAll('[data-exp-select]')];if(!nodes.length)return;
    const next=Math.max(0,Math.min(nodes.length-1,activeExpOption[type]+(e.key==='ArrowDown'?1:-1)));
    activeExpOption[type]=next;nodes.forEach((node,i)=>node.classList.toggle('is-active',i===next));nodes[next].scrollIntoView({block:'nearest'});
   }else if(e.key==='Enter'){
    e.preventDefault();if(openExpCombo!==type)expOpen(type);
    const selected=menu.querySelectorAll('[data-exp-select]')[activeExpOption[type]];
    if(selected)expSet(type,Number(selected.dataset.index));
   }
  });
  menu.addEventListener('click',e=>{const item=e.target.closest('[data-exp-select]');if(item)expSet(type,Number(item.dataset.index));});
  document.querySelector('[data-combo-open="'+type+'"]').addEventListener('click',()=>{if(openExpCombo===type){expClose(type);return;}input.focus();expOpen(type);});
 }
 document.addEventListener('pointerdown',event=>{
  if(openExpCombo&&!event.target.closest('[data-explorer-combo]'))expClose(openExpCombo);
 });
 $('expClearAll').addEventListener('click',()=>{
  st.providerExp=-1;st.formatExp=-1;st.brand=-1;$('brand').value='-1';st.pagenum=0;
  if(openExpCombo)expClose(openExpCombo,false);expSyncValues();update();
 });
 expSyncValues();
}

// ABC × XYZ (v1.8): ABC = importancia relativa de las ventas netas en la población
// filtrada; XYZ = coeficiente de variación poblacional de unidades vendidas en los
// 12 meses completos que terminan en st.end. El historial nulo no se inventa.
const XYZ_CODES=['AX','AY','AZ','BX','BY','BZ','CX','CY','CZ'];
const XYZ_HINT={AX:'Alta prioridad y demanda regular',AY:'Alta prioridad y demanda variable',AZ:'Alta prioridad y demanda irregular',BX:'Prioridad media y demanda regular',BY:'Prioridad media y demanda variable',BZ:'Prioridad media y demanda irregular',CX:'Baja contribución y demanda regular',CY:'Baja contribución y demanda variable',CZ:'Baja contribución y demanda irregular'};
const xyzMonthlyCache=new Map();
let xyzRowsCache=[];
function getXYZ(i){
 const key=st.end;
 if(!xyzMonthlyCache.has(key))xyzMonthlyCache.set(key,new Array(DATA.products.length));
 const cached=xyzMonthlyCache.get(key);if(cached[i])return cached[i];
 const start=key-11;
 if(start<0){return cached[i]={xyz:'—',cv:null,active:0,mean:null,months:Math.max(0,key+1),insufficient:true};}
 const volume=new Array(12).fill(0);
 for(const [month,units] of saleBySku[i])if(month>=start&&month<=key)volume[month-start]+=units;
 // Al igual que el procesador original, la demanda neta negativa mensual no
 // equivale a un consumo negativo: la base para variabilidad se acota a cero.
 let sum=0,square=0,active=0;
 for(const raw of volume){const x=Math.max(0,raw);sum+=x;square+=x*x;if(x>0)active++;}
 const mean=sum/12;
 if(mean<=0)return cached[i]={xyz:'—',cv:null,active:0,mean:0,months:12,insufficient:false};
 const variance=Math.max(0,square/12-mean*mean),cv=Math.sqrt(variance)/mean;
 return cached[i]={xyz:cv<=0.5?'X':cv<=1?'Y':'Z',cv,active,mean,months:12,insufficient:false};
}
function xyzPopulation(){
 // Provider and format filters apply to the population. Brand, category, SKU
 // search, period and warehouse already filter the underlying view.
 const population=view.rows.filter(r=>(st.providerExp<0||r.p[4]===st.providerExp)
   &&(st.formatExp<0||explorerFormatIdBySku[r.i]===st.formatExp));
 const ranked=population.filter(r=>r.rev>0).sort((a,b)=>b.rev-a.rev||a.i-b.i);
 const total=ranked.reduce((sum,r)=>sum+r.rev,0);
 const abc=new Map(), epsilon=1e-9;let accumulated=0;
 for(const r of ranked){abc.set(r.i,accumulated/(total||1)<0.80-epsilon?'A':accumulated/(total||1)<0.95-epsilon?'B':'C');accumulated+=r.rev;}
 return population.map(r=>{
  const trend=getXYZ(r.i),ab=abc.get(r.i)||'—';
  return {...r,xyz:trend.xyz,xyzCv:trend.cv,xyzActive:trend.active,xyzMean:trend.mean,
   xyzInsufficient:trend.insufficient,xyzAbc:ab,xyzGroup:ab==='—'||trend.xyz==='—'?'—':ab+trend.xyz};
 });
}
function xyzBadge(row){return row.xyzGroup==='—'?'<span class="xyz-badge unclassified">Sin clase</span>':'<span class="xyz-badge '+row.xyzGroup.toLowerCase()+'">'+row.xyzGroup+'</span>';}
function xyzSelectedRows(){return xyzRowsCache.filter(r=>st.xyzCell==='all'||(st.xyzCell==='—'?r.xyzGroup==='—':r.xyzGroup===st.xyzCell));}
function xyzSortRows(rows){const key=st.xyzSort,sign=st.xyzDesc?-1:1;
 const get=(r)=>({sku:r.p[0],name:r.p[1],abcxyz:r.xyzGroup,xyz:r.xyz,cv:r.xyzCv??-1,months:r.xyzActive,rev:r.rev,qty:r.qty,profit:r.profit,stockQty:r.stockQty,stock:r.stock,coverage:r.coverage??-1})[key];
 rows.sort((a,b)=>{const x=get(a),y=get(b);const cmp=typeof x==='string'?x.localeCompare(y,'es'):(x-y);return (cmp||a.i-b.i)*sign;});return rows;
}
function renderXYZ(){
 const rows=xyzPopulation();xyzRowsCache=rows;
 const stats=Object.fromEntries(XYZ_CODES.map(code=>[code,{count:0,rev:0,profit:0,stock:0}]));
 let unclassified=0,unclassifiedStock=0,xyzClassified=0;
 for(const r of rows){const cell=stats[r.xyzGroup];if(cell){cell.count++;cell.rev+=r.rev;cell.profit+=r.profit;cell.stock+=r.stock;xyzClassified++;}else{unclassified++;unclassifiedStock+=r.stock;}}
 const validPositive=rows.reduce((n,r)=>n+(r.rev>0?r.rev:0),0);
 const ax=stats.AX,az=stats.AZ,cz=stats.CZ;
 $('xyzKpis').innerHTML=kpi('SKU clasificados',fmt(xyzClassified),fmt(rows.length)+' SKU en universo filtrado','▤')
   +kpi('Grupo AX',fmt(ax.count),compact(ax.rev)+' en ventas netas','◎','good')
   +kpi('Grupo AZ',fmt(az.count),compact(az.rev)+' con demanda irregular','◈','warn')
   +kpi('Capital en CZ',compact(cz.stock),fmt(cz.count)+' SKU de bajo aporte irregular','⚑','bad');
 let markup='';
 for(const abc of ['A','B','C'])for(const xyz of ['X','Y','Z']){
  const code=abc+xyz,s=stats[code],selected=st.xyzCell===code;
  markup+='<button type="button" class="xyz-cell '+code.toLowerCase()+(selected?' selected':'')+'" data-xyz-cell="'+code+'" aria-pressed="'+selected+'" title="'+escapeHtml(XYZ_HINT[code])+'">'
     +'<span class="xyz-cell-title">'+code+'</span><strong>'+fmt(s.count)+' SKU</strong><small>'+compact(s.rev)+' ventas · '+pct(validPositive?s.rev/validPositive:0)+'</small><small>'+compact(s.stock)+' en stock</small></button>';
 }
 $('xyzMatrix').innerHTML=markup;
 $('xyzMatrixFoot').textContent=fmt(unclassified)+' SKU sin clasificación conjunta (sin ventas positivas o sin demanda/12 meses de XYZ) · stock estimado '+usd(unclassifiedStock)+'. ABC se calcula sobre ventas positivas del universo filtrado.';
 $('xyzSelection').innerHTML='<button class="chip '+(st.xyzCell==='all'?'sel':'')+'" data-xyz-cell="all">Todos</button>'
   +XYZ_CODES.map(code=>'<button class="chip '+(st.xyzCell===code?'sel':'')+'" data-xyz-cell="'+code+'">'+code+'</button>').join('')
   +'<button class="chip '+(st.xyzCell==='—'?'sel':'')+'" data-xyz-cell="—">Sin clasificar ('+fmt(unclassified)+')</button>';
 const all=xyzSortRows(xyzSelectedRows()), pages=Math.max(1,Math.ceil(all.length/st.xyzPageSize));
 st.xyzPage=Math.min(Math.max(0,st.xyzPage),pages-1);
 const segment=all.slice(st.xyzPage*st.xyzPageSize,(st.xyzPage+1)*st.xyzPageSize);
 const head=(label,field,numeric=false)=>'<th '+(numeric?'class="num" ':'')+'data-xyz-sort="'+field+'">'+label+(st.xyzSort===field?(st.xyzDesc?' ↓':' ↑'):'')+'</th>';
 $('xyzTable').innerHTML='<div class="tablewrap"><table class="data-table"><thead><tr>'
  +head('SKU','sku')+head('Producto / imagen','name')+head('Grupo','abcxyz')+head('XYZ','xyz')
  +head('CV','cv',true)+head('Meses con venta','months',true)+head('Ventas $','rev',true)+head('Vendido · cant.','qty',true)
  +head('Utilidad $','profit',true)+head('Stock · cant.','stockQty',true)+head('Stock $','stock',true)
  +head('Cobertura','coverage',true)+'</tr></thead><tbody>'
  +segment.map(r=>'<tr data-sku="'+r.i+'"><td>'+escapeHtml(r.p[0])+'</td><td>'+productPhotoCell(r.p)+'</td><td>'+xyzBadge(r)+'</td><td>'+escapeHtml(r.xyz)+'</td><td class="num">'+(r.xyzCv===null?'—':fmt(r.xyzCv,2))+'</td><td class="num">'+fmt(r.xyzActive)+' / '+(r.xyzInsufficient?getXYZ(r.i).months:12)+'</td><td class="num">'+usd(r.rev)+'</td><td class="num">'+qtyCell(r.qty,r.p)+'</td><td class="num">'+usd(r.profit)+'</td><td class="num">'+qtyCell(r.stockQty,r.p)+'</td><td class="num">'+usd(r.stock)+'</td><td class="num">'+(r.coverage===null?'—':fmt(r.coverage,0)+' d')+'</td></tr>').join('')
  +'</tbody></table></div>';
 $('xyzCount').textContent=fmt(all.length)+' de '+fmt(rows.length)+' SKU · '+months[Math.max(0,st.end-11)]+' → '+months[st.end]+' (XYZ)';
 const begin=all.length?st.xyzPage*st.xyzPageSize+1:0,end=Math.min(all.length,(st.xyzPage+1)*st.xyzPageSize);
 $('xyzPagerText').textContent=fmt(begin)+'–'+fmt(end)+' de '+fmt(all.length)+' productos';
 $('xyzPagerNum').textContent=(st.xyzPage+1)+' / '+pages;
 $('xyzFirst').disabled=$('xyzPrev').disabled=st.xyzPage<=0;
 $('xyzNext').disabled=$('xyzLast').disabled=st.xyzPage>=pages-1;
 const host=$('xyzFilterHost');if(host.contains(document.querySelector('.tc-explorer-filters')))expStatus(rows.length);
 loadTablePhotos('xyzTable');
}
function mountExplorerFilters(page){
 const filters=document.querySelector('.tc-explorer-filters'),destination=$(page==='xyz'?'xyzFilterHost':'productsFilterHost');
 if(filters&&destination&&!destination.contains(filters)){
  if(openExpCombo)expClose(openExpCombo);
  destination.appendChild(filters);
 }
}

function setPeriod(v){st.period=v;const r={12:[Math.max(0,refLast-11),refLast],6:[Math.max(0,refLast-5),refLast],3:[Math.max(0,refLast-2),refLast],26:[Math.max(0,months.indexOf(refYear+'-01')),refLast],25:[Math.max(0,months.indexOf(prevYear+'-01')),Math.max(0,months.indexOf(prevYear+'-'+String(refNumber).padStart(2,'0')))],all:[0,refLast]};if(r[v])[st.start,st.end]=r[v];$('from').disabled=$('to').disabled=v!=='custom';$('from').value=st.start;$('to').value=st.end;st.pagenum=0;update()}
function actionClass(a){return a===0?'buy':a===1?'keep':a===2?'reduce':a===3?'stop':'review'}
function actionBadge(a){return '<span class="action '+actionClass(a)+'">'+escapeHtml(DATA.actions[a])+'</span>'}
function inPeriod(m){return m>=st.start&&m<=st.end}
function calculate(){let selected=[],selectedIndex=new Set(),yoy={rev25:0,rev26:0,profit25:0,profit26:0},tot={rev:0,cogs:0,profit:0,qty:0,stock:0,stockQty:0,purchases:0,stalecap:0,excesscap:0,stockNoSale12:0,negativeprofit:0,negativeSkus:0,stockNegative:0};const trends=months.map(()=>({rev:0,cogs:0,profit:0,purchases:0}));const categories=new Map(),brands=new Map(),warehouseTotals=new Map();const maskBrand=st.brand, maskCat=st.cat,maskWh=st.wh,q=st.search.toLocaleLowerCase('es').trim();for(let i=0;i<DATA.products.length;i++){let p=DATA.products[i];if(maskCat>=0&&p[2]!==maskCat||maskBrand>=0&&p[3]!==maskBrand)continue;if(q&&!((p[0]+' '+p[1]+' '+DATA.providers[p[4]]).toLocaleLowerCase('es').includes(q)))continue;let localStock=0,neg=0;if(maskWh>=0){for(const [w,qty]of stockWare[i])if(w===maskWh){if(qty>0)localStock+=qty;else neg+=qty}if(localStock===0&&neg===0)continue}else{localStock=p[7];neg=p[9]}
 const row={i,p,rev:0,cogs:0,profit:0,qty:0,buys:0,buyQty:0,stockQty:localStock,stock:localStock*Math.max(p[5],0),stockNeg:neg,coverage:maskWh<0&&p[14]>0?p[7]*refDays3/p[14]:null,abc:'—',abcProfit:'—',xyz:p[12],action:p[13]};for(const [m,q,rev,cogs]of saleBySku[i]){if(inPeriod(m)){row.rev+=rev;row.cogs+=cogs;row.qty+=q;const trend=trends[m];trend.rev+=rev;trend.cogs+=cogs;trend.profit+=rev-cogs}let lab=months[m];if(lab>=prevYear+'-01'&&lab<=prevYear+'-'+String(refNumber).padStart(2,'0')){yoy.rev25+=rev;yoy.profit25+=rev-cogs}else if(lab>=refYear+'-01'&&lab<=refMonth){yoy.rev26+=rev;yoy.profit26+=rev-cogs}}row.profit=row.rev-row.cogs;for(const [m,quantity,buy]of buyBySku[i])if(inPeriod(m)){row.buys+=buy;row.buyQty+=quantity;trends[m].purchases+=buy}
 tot.rev+=row.rev;tot.cogs+=row.cogs;tot.profit+=row.profit;tot.qty+=row.qty;tot.stock+=row.stock;tot.stockQty+=row.stockQty;tot.purchases+=row.buys;tot.stockNegative+=neg;if(row.stockQty>0&&p[15]<=0)tot.stalecap+=row.stock;if(row.stockQty>0&&p[14]<=0)tot.stockNoSale12+=p[16]<=0?row.stock:0;if(maskWh<0&&row.stockQty>0&&row.coverage!==null&&row.coverage>=180)tot.excesscap+=row.stock;if(row.rev>0&&row.profit<0){tot.negativeprofit+=row.profit;tot.negativeSkus++}
 const cat=categories.get(p[2])||{name:DATA.categories[p[2]],id:p[2],rev:0,profit:0,stock:0,stale:0,count:0};cat.rev+=row.rev;cat.profit+=row.profit;cat.stock+=row.stock;cat.count++;if(row.stockQty>0&&p[15]<=0)cat.stale+=row.stock;categories.set(p[2],cat);const b=brands.get(p[3])||{name:DATA.brands[p[3]],rev:0,profit:0};b.rev+=row.rev;b.profit+=row.profit;brands.set(p[3],b);selected.push(row);selectedIndex.add(i)
 }
 // ABC for active subset, by positive sales / gross profit only.
 function assignABC(field,out){let filtered=selected.filter(r=>r[field]>0).sort((a,b)=>b[field]-a[field]);let sum=filtered.reduce((a,b)=>a+b[field],0),cum=0;for(const r of filtered){r[out]=cum/sum<.8?'A':cum/sum<.95?'B':'C';cum+=r[field]}}
 assignABC('rev','abc');assignABC('profit','abcProfit');const abcs={A:{count:0,rev:0,profit:0},B:{count:0,rev:0,profit:0},C:{count:0,rev:0,profit:0},'—':{count:0,rev:0,profit:0}};for(let r of selected){const ob=abcs[r.abc];ob.count++;ob.rev+=r.rev;ob.profit+=r.profit}
 for(let [i,p]of DATA.products.entries()){if(!selectedIndex.has(i))continue;for(const [wi,qty]of stockWare[i]){if(qty<=0)continue;if(st.wh>=0&&wi!==st.wh)continue;const vl=qty*Math.max(0,p[5]);const obj=warehouseTotals.get(wi)||{id:wi,name:DATA.warehouses[wi],qty:0,value:0,skus:0,negative:0};obj.qty+=qty;obj.value+=vl;obj.skus++;warehouseTotals.set(wi,obj)}}
 const sups=new Map();for(const row of selected){for(const [m,s,amt]of suppBySku[row.i])if(inPeriod(m)){let b=sups.get(s)||{id:s,name:DATA.purchaseSuppliers[s],buy:0,entries:0};b.buy+=amt;b.entries++;sups.set(s,b)}}
 return{rows:selected,tot,trends,yoy,abcs,categories:[...categories.values()],brands:[...brands.values()],warehouses:[...warehouseTotals.values()],suppliers:[...sups.values()]}}
function update(){st.xyzPage=0;let time=performance.now();view=calculate();let labels=months[st.start]+' a '+months[st.end];$('scopeinfo').textContent=fmt(view.rows.length)+' productos · '+labels+' · '+(st.wh>=0?'stock de bodega seleccionada y ventas corporativas':'stock agregado de todas las bodegas');$('warehouseWarning').innerHTML=st.wh>=0?'<b>Filtro bodega:</b> las ventas y compras siguen siendo corporativas para los SKU de la bodega; por eso no se calcula cobertura por bodega.':'';$('dateLegend').textContent=labels;$('skuCount').textContent=fmt(view.rows.length)+' SKU';const page=st.page;renderAll();}
function kpi(label,val,foot,icon,kind=''){return '<div class="metric"><div class="meta"><span class="label">'+label+'</span><span class="miniicon">'+icon+'</span></div><div class="amount '+kind+'" title="'+escapeHtml(val)+'">'+val+'</div><div class="foot">'+foot+'</div></div>'}
function renderAll(){let v=view,t=v.tot; $('kpis').innerHTML=kpi('Ventas netas',compact(t.rev),'Periodo seleccionado','↗')+kpi('Utilidad bruta',compact(t.profit),'Ingresos menos costo de ventas','◉','good')+kpi('Margen bruto',pct(t.rev?t.profit/t.rev:0),'Rentabilidad bruta sobre ventas','%')+kpi('Compras',compact(t.purchases),'Compras de los SKU incluidos','↘')+kpi('Stock valorizado',compact(t.stock),'Positivo × costo catálogo','▣')+kpi('Sin demanda 6 meses',compact(t.stalecap),'Global '+months[Math.max(0,refLast-5)]+' a '+refMonth+' · stock visible','⚑','warn')+kpi('Contribución negativa',usd(t.negativeprofit),'SKU con venta positiva y pérdida','−','bad')+kpi('Cobertura de 180+ días',st.wh>=0?'N/D':compact(t.excesscap),st.wh>=0?'Sin ventas por bodega':'Referencia '+months[Math.max(0,refLast-2)]+' a '+refMonth,'◷','warn');
 renderLine();renderABC();renderBars('catTop',v.categories,'rev',9,'cat');renderProductBars();renderCallouts();if(st.page==='abc')renderABCPage();else if(st.page==='xyz')renderXYZ();else if(st.page==='rotacion')renderRisk();else if(st.page==='comprasplan')renderPlan();else if(st.page==='bodegas')renderWare();else if(st.page==='proveedores')renderSup();else if(st.page==='productos')renderProducts();else if(st.page==='provprofit')renderProviderProfit();else if(st.page==='calidad')renderQuality();}
function renderLine(){const arr=view.trends.slice(st.start,st.end+1),W=720,H=265,pad={t:22,b:43,l:69,r:15};const left=pad.l,right=W-pad.r,top=pad.t,bottom=H-pad.b;let mx=Math.max(1,...arr.map(t=>Math.max(t.rev,t.profit,t.purchases)))*1.16;const Y=v=>bottom-(v/mx)*(bottom-top),X=i=>left+(arr.length<=1?(right-left)/2:i*(right-left)/(arr.length-1));let parts=['<svg viewBox="0 0 '+W+' '+H+'" role="img" aria-label="Gráfico mensual de ventas utilidad y compras">'];for(let k=0;k<=4;k++){let value=mx*k/4,y=Y(value);parts.push('<line x1="'+left+'" x2="'+right+'" y1="'+y+'" y2="'+y+'" stroke="#e9eff4"/><text x="'+(left-9)+'" y="'+(y+4)+'" font-size="11" text-anchor="end" fill="#8092a2">'+escapeHtml(compact(value))+'</text>')}
 for(let [field,color] of [['rev',C.blue],['profit',C.green],['purchases',C.amber]]){let points=arr.map((m,i)=>[X(i),Y(m[field])]);parts.push('<polyline points="'+points.map(p=>p.join(',')).join(' ')+'" fill="none" stroke="'+color+'" stroke-width="2.9" stroke-linecap="round" stroke-linejoin="round"/>');for(let [i,p] of points.entries()){parts.push('<circle cx="'+p[0]+'" cy="'+p[1]+'" r="3.5" fill="'+color+'" stroke="white" stroke-width="1"><title>'+escapeHtml(months[st.start+i]+' · '+({rev:'Ventas',profit:'Utilidad',purchases:'Compras'}[field])+' '+usd(arr[i][field],2))+'</title></circle>')}}
 for(let i=0;i<arr.length;i++){if(arr.length>13&&i%Math.ceil(arr.length/10)!==0&&i!==arr.length-1)continue;parts.push('<text x="'+X(i)+'" y="'+(H-15)+'" fill="#8292a1" font-size="11" text-anchor="middle">'+monthLabels[st.start+i]+'</text>')}parts.push('</svg>');$('monthlyChart').innerHTML=parts.join('')}
function renderABC(){let a=view.abcs,total=view.tot.rev||1,arr=['A','B','C'];let cards=arr.map(key=>'<div class="abccell" data-abc="'+key+'" title="Mostrar clase '+key+' en explorador"><span class="abcletter">CLASE '+key+'</span><div class="abcbig">'+fmt(a[key].count)+'</div><div class="abcshare">'+pct(a[key].rev/total)+' ventas</div></div>').join('');let segments=arr.map(k=>'<div class="s'+k+'" style="width:'+Math.max(0,a[k].rev/total*100)+'%" title="'+k+': '+usd(a[k].rev)+'"></div>').join('');$('abcSummary').innerHTML='<div class="abc-cols">'+cards+'</div><div class="stack">'+segments+'</div><p class="boxsub">Clasificación por ventas positivas acumuladas (80 / 15 / 5 %) y recalculada para el subconjunto activo. Los SKU sin ventas positivas se mantienen fuera de las clases A/B/C.</p><div class="mid-block" style="margin-top:17px"><h4>Interpretación gerencial</h4><p>'+fmt(a.A.count)+' artículos concentran aproximadamente '+pct(a.A.rev/total)+' de las ventas del filtro. Evalúa rentabilidad y stock antes de reponer automáticamente.</p></div>'}
function renderBars(target,arr,key,count,kind){let list=[...arr].sort((a,b)=>b[key]-a[key]).slice(0,count);let max=Math.max(...list.map(x=>x[key]),1);if(!list.length){$(target).innerHTML='<div class="empty">No hay registros para estos filtros.</div>';return}$(target).innerHTML='<div class="barbox">'+list.map(r=>'<div class="hbar '+(kind?'clickable':'')+'" '+(kind==='cat'?'data-cat="'+r.id+'"':kind==='warehouse'?'data-wh="'+r.id+'"':'')+' title="'+escapeHtml(r.name)+' · '+usd(r[key],2)+'"><span class="hlabel">'+escapeHtml(r.name)+'</span><span class="track"><span class="fill" style="display:block;width:'+Math.max(0,100*r[key]/max)+'%"></span></span><span class="hvalue">'+compact(r[key])+'</span></div>').join('')+'</div>'}
function renderProductBars(){let arr=view.rows.filter(r=>r.profit>0).sort((a,b)=>b.profit-a.profit).slice(0,8),max=arr[0]?.profit||1;$('topProducts').innerHTML='<div class="barbox">'+arr.map(r=>'<div class="hbar clickable" data-sku="'+r.i+'" title="'+escapeHtml(r.p[1]+' '+usd(r.profit))+'"><span class="hlabel">'+escapeHtml(r.p[1])+'</span><span class="track"><span class="fill" style="width:'+Math.round(100*r.profit/max)+'%;display:block;background:#3f82e9"></span></span><span class="hvalue">'+compact(r.profit)+'</span></div>').join('')+'</div>'}
function renderCallouts(){let t=view.tot,n=view.rows.length,stock=t.stock||1;let buy=view.rows.filter(r=>r.action===0&&r.p[14]>0&&r.p[17]>0).length;const block=(title,body)=>'<div class="mid-block"><h4>'+title+'</h4><p>'+body+'</p></div>';$('executiveCallouts').innerHTML=block('01 · Capital sin movimiento',compact(t.stalecap)+' representa '+pct(t.stalecap/stock)+' del stock valorizado visible. Revisar bodegas especiales antes de liquidar.')+block('02 · Productos a revisar para reposición',fmt(buy)+' productos tienen señal corporativa de compra basada en cobertura histórica y rentabilidad. Verificar lead time, tránsito y reservas.')+block('03 · Comparativo interanual',pct(view.yoy.rev25?view.yoy.rev26/view.yoy.rev25-1:0)+' en ventas y '+pct(view.yoy.profit25?view.yoy.profit26/view.yoy.profit25-1:0)+' en utilidad bruta ('+refYear+' frente a '+prevYear+', para la misma selección de SKU).')}
function barABC(key,meaning){let agg={A:0,B:0,C:0,'—':0},rev={A:0,B:0,C:0,'—':0};for(const r of view.rows){let c=r[key]||'—';agg[c]++;rev[c]+=r[key==='abc'?'rev':'profit']}let total=rev.A+rev.B+rev.C;return '<h4 style="font-size:12px">'+meaning+'</h4><div class="abc-cols">'+['A','B','C'].map(k=>'<div class="abccell" data-abc="'+(key==='abc'?k:'')+'"><span class="abcletter">'+k+'</span><div class="abcbig">'+fmt(agg[k])+'</div><div class="abcshare">'+pct(total?rev[k]/total:0)+' aporte</div></div>').join('')+'</div><p class="boxsub">'+fmt(agg['—'])+' productos no clasificables por '+(key==='abc'?'ventas':'utilidad')+' positiva.</p>'}
function renderABCPage(){$('abcBreakdown').innerHTML=barABC('abc','ABC por ventas netas')+'<div style="height:18px"></div>'+barABC('abcProfit','ABC por utilidad bruta');let categories=view.categories.filter(x=>x.rev>100).map(x=>({...x,margin:x.profit/x.rev})).sort((a,b)=>b.rev-a.rev).slice(0,12);let max=.7;$('marginCats').innerHTML=categories.map(c=>'<div class="hbar clickable" data-cat="'+c.id+'"><span class="hlabel">'+escapeHtml(c.name)+'</span><span class="track"><span class="fill" style="width:'+Math.min(100,c.margin/max*100)+'%;display:block;background:'+(c.margin<0?C.red:C.blue)+'"></span></span><span class="hvalue">'+pct(c.margin)+'</span></div>').join('');let top=view.rows.filter(r=>r.rev>0).sort((a,b)=>b.profit-a.profit).slice(0,40);$('profitTable').innerHTML=simpleTable(['Producto','Ventas netas','Costo ventas','Utilidad','Margen','ABC ventas','ABC utilidad'],top.map(r=>[r.p[1],usd(r.rev),usd(r.cogs),usd(r.profit),pct(r.rev?r.profit/r.rev:0),r.abc,r.abcProfit]),top.map(r=>r.i))}
function simpleTable(headers,rows,ids,htmlColumns=[]){return '<div class="tablewrap"><table class="data-table"><thead><tr>'+headers.map((h,i)=>'<th class="'+(i?'num':'')+'">'+escapeHtml(h)+'</th>').join('')+'</tr></thead><tbody>'+rows.map((row,j)=>'<tr '+(ids?'data-sku="'+ids[j]+'"':'')+'>'+row.map((col,k)=>'<td class="'+(k?'num':'')+'">'+(htmlColumns.includes(k)?col:escapeHtml(col))+'</td>').join('')+'</tr>').join('')+'</tbody></table></div>'}
// La misma miniatura verificada se utiliza en Explorador y Reposición.
function productPhotoCell(product){
 return '<div class="tc-product-cell"><span class="tc-photo-mini" data-photo-sku="'+escapeHtml(product[0])+'"><span>◫</span></span><span class="cellname" title="'+escapeHtml(product[1])+'">'+escapeHtml(product[1])+'</span></div>';
}
// Actualizar primero las fotos ya consultadas, incluso tras regenerar una tabla;
// después consultar sólo los SKU nuevos/expirados sin bloquear la vista.
function loadTablePhotos(tableId){
 const nodes=[...document.querySelectorAll('#'+tableId+' [data-photo-sku]')];
 for(const node of nodes)renderPhoto(node);
 if(nodes.length)fetchPhotoRefs(nodes.map(node=>node.getAttribute('data-photo-sku')));
}
function renderRisk(){let t=view.tot;let stale=view.rows.filter(r=>r.stockQty>0&&r.p[15]<=0).sort((a,b)=>b.stock-a.stock);let high=view.rows.filter(r=>r.stockQty>0&&r.coverage!==null&&r.coverage>=180).length; $('riskKpis').innerHTML=kpi('Sin ventas 6 meses',compact(t.stalecap),fmt(stale.length)+' SKU con stock · global','⚑','warn')+kpi('Inventario >180 días',st.wh>=0?'N/D':compact(t.excesscap),st.wh>=0?'Bodega sin ventas propias':fmt(high)+' SKU · demanda jul–sep','◷','warn')+kpi('Sin ventas 12 meses',compact(stale.filter(r=>r.p[16]<=0).reduce((s,r)=>s+r.stock,0)),'Ventas del año de referencia','▣')+kpi('Utilidad negativa',usd(t.negativeprofit),fmt(t.negativeSkus)+' SKU con ventas positivas','↘','bad');renderBars('staleCats',view.categories,'stale',13,'cat');let actions=new Map();for(let row of view.rows){const e=actions.get(row.action)||{name:DATA.actions[row.action],count:0,stock:0};e.count++;e.stock+=row.stock;actions.set(row.action,e)}$('actionsChart').innerHTML=[...actions.values()].sort((a,b)=>b.stock-a.stock).map(x=>'<div class="hbar"><span class="hlabel">'+escapeHtml(x.name)+'</span><span class="track"><span class="fill" style="display:block;width:'+Math.min(100,x.stock/(t.stock||1)*100)+'%;background:'+(x.name.includes('SUSPENDER')?C.red:x.name==='REDUCIR'?C.amber:C.green)+'"></span></span><span class="hvalue">'+compact(x.stock)+'</span></div><div class="small" style="text-align:right">'+fmt(x.count)+' SKU</div>').join('')+'<p class="boxsub">Etiquetas globales fijas calculadas con el periodo '+DATA.source.start+' a '+refMonth+'; se filtran, pero no se recalculan para periodos anteriores ni por bodega.</p>';
 $('staleTable').innerHTML=simpleTable(['Producto','Categoría','Stock valorizado','Ventas periodo','ABC global','Acción global'],stale.slice(0,65).map(r=>[r.p[1],DATA.categories[r.p[2]],usd(r.stock),usd(r.rev),r.p[10],DATA.actions[r.action]]),stale.slice(0,65).map(r=>r.i))}
function renderPlan(){if(st.wh>=0){$('planKpis').innerHTML='';$('replenishTable').innerHTML='<div class="empty">Para calcular un escenario de reposición es necesario seleccionar <b>Todas las bodegas</b>, porque las ventas no están desglosadas por ubicación. El filtro de bodega solo sirve para explorar stock.</div>';return}let days=st.goalDays;let candidates=view.rows.filter(r=>{let p=r.p;if(p[14]<=0||p[17]<=0||p[5]<=0||p[7]<0)return false;let proposed=Math.max(0,p[14]/refDays3*days-p[7]);r.proposed=proposed;r.capital=proposed*p[5];return proposed>0}).sort((a,b)=>b.capital-a.capital);let total=candidates.reduce((s,r)=>s+r.capital,0),units=candidates.reduce((s,r)=>s+r.proposed,0),priority=candidates.filter(r=>r.p[10]==='A').length;
$('planKpis').innerHTML=kpi('Inversión estimada',compact(total),'Escenario '+days+' días · costo catálogo','▣','warn')+kpi('Productos candidatos',fmt(candidates.length),'Margen bruto positivo y demanda reciente','▦')+kpi('Candidatos ABC A globales',fmt(priority),'Por ventas de los 12 meses de referencia','◉')+kpi('Stock objetivo',days+' días','Demanda media de '+months[Math.max(0,refLast-2)]+' a '+refMonth,'◷');let top=candidates.slice(0,50);$('replenishTable').innerHTML=simpleTable(['Producto y foto','ABC global','Cobertura actual','Stock actual · cant.','Demanda 3 meses','Cantidad sugerida','Costo estimado'],top.map(r=>[productPhotoCell(r.p),r.p[10],fmt(r.coverage||0)+' días',qtyCell(r.p[7],r.p),qtyCell(r.p[14],r.p),qtyCell(r.proposed,r.p),usd(r.capital)]),top.map(r=>r.i),[0,3,4,5])+'<p class="boxsub">Mostrando '+fmt(top.length)+' de '+fmt(candidates.length)+' candidatos. Las cantidades están expresadas en la unidad que maneja cada artículo (no sumar entre productos). La inversión estimada no incluye impuestos, fletes o condiciones de compra.</p>';loadTablePhotos('replenishTable')}
function renderWare(){renderBars('warehouseBars',view.warehouses,'value',22,'warehouse');renderBars('stockCats',view.categories,'stock',17,'cat');let arr=[...view.warehouses].sort((a,b)=>b.value-a.value);$('warehouseTable').innerHTML=simpleTable(['Bodega','Stock positivo valorizado','Existencia física*','SKU con stock'],arr.map(a=>[a.name,usd(a.value),fmt(a.qty,2),fmt(a.skus)]));$('warehouseTable').innerHTML+='<p class="boxsub">* Las cantidades suman unidades, metros, metros cuadrados y otras presentaciones; el total combinado no tiene significado físico homogéneo. Existen bodegas especiales, exhibición y remate que deben clasificarse.</p>'}
function renderSup(){let v=view,t=v.tot,arr=v.suppliers.sort((a,b)=>b.buy-a.buy),n=arr.length,top5=arr.slice(0,5).reduce((sum,a)=>sum+a.buy,0);$('buyKpis').innerHTML=kpi('Compras del periodo',compact(t.purchases),'Transacciones por SKU','▧')+kpi('Proveedores de compra',fmt(n),'Con compras en la selección','♙')+kpi('Concentración top 5',pct(t.purchases?top5/t.purchases:0),'Participación del valor comprado','◎')+kpi('SKU comprados',fmt(view.rows.filter(r=>r.buys>0).length),'Con compras positivas en periodo','▦');renderBars('supBars',arr,'buy',14,'');$('supConcentration').innerHTML='<div class="abc-cols"><div class="abccell"><span class="abcletter">TOP 1</span><div class="abcbig">'+pct(t.purchases?(arr[0]?.buy||0)/t.purchases:0)+'</div><div class="abcshare">'+escapeHtml((arr[0]?.name||'Sin compras').slice(0,25))+'</div></div><div class="abccell"><span class="abcletter">TOP 5</span><div class="abcbig">'+pct(t.purchases?top5/t.purchases:0)+'</div><div class="abcshare">Concentración</div></div><div class="abccell"><span class="abcletter">RESTO</span><div class="abcbig">'+pct(t.purchases?1-top5/t.purchases:0)+'</div><div class="abcshare">Otros proveedores</div></div></div><div class="mid-block" style="margin-top:24px"><h4>Regla de atribución</h4><p>Este ranking corresponde al proveedor registrado en cada compra. No asigna automáticamente la venta, rentabilidad o existencia a ese proveedor porque no hay trazabilidad de lotes.</p></div>';$('supTable').innerHTML=simpleTable(['Proveedor de compras','Compras netas','Participación','Registros producto-mes'],arr.slice(0,100).map(a=>[a.name,usd(a.buy,2),pct(t.purchases?a.buy/t.purchases:0,2),fmt(a.entries)]))}
function sortRows(arr){let key=st.sort,sign=st.desc?-1:1;return arr.sort((a,b)=>{let x=a[key],y=b[key];if(key==='name'){x=a.p[1].toLowerCase();y=b.p[1].toLowerCase()}if(key==='category'){x=DATA.categories[a.p[2]];y=DATA.categories[b.p[2]]}if(key==='sku'){x=a.p[0];y=b.p[0]}if(key==='margin'){x=a.rev?a.profit/a.rev:0;y=b.rev?b.profit/b.rev:0}if(key==='abc'){x=a.abc;y=b.abc}if(key==='action'){x=a.action;y=b.action}if(key==='coverage'){x=a.coverage??-1;y=b.coverage??-1}return (typeof x==='string'?x.localeCompare(y):x-y)*sign})}
function renderProducts(){let data=expFilterRows();expSyncValues();expStatus(data.length);$('skuCount').textContent=fmt(data.length)+' / '+fmt(view.rows.length)+' SKU';let base=[...data];sortRows(base);let totalpages=Math.max(1,Math.ceil(base.length/st.pageSize));st.pagenum=Math.max(0,Math.min(st.pagenum,totalpages-1));let page=base.slice(st.pagenum*st.pageSize,(st.pagenum+1)*st.pageSize);let th=(label,field,isnum=false)=>'<th '+(isnum?'class="num" ':'')+'data-sort="'+field+'">'+label+(field===st.sort?(st.desc?' ↓':' ↑'):'')+'</th>';
 $('productTable').innerHTML='<div class="tablewrap"><table class="data-table"><thead><tr>'+th('Código','sku')+th('Producto','name')+th('Categoría','category')+th('Vendido · cant.','qty',true)+th('Comprado · cant.','buyQty',true)+th('Stock · cant.','stockQty',true)+th('ABC','abc')+th('Venta','rev',true)+th('Utilidad','profit',true)+th('Margen','margin',true)+th('Stock $','stock',true)+th('Cobertura','coverage',true)+th('Acción global','action')+'</tr></thead><tbody>'+page.map(r=>'<tr data-sku="'+r.i+'"><td>'+escapeHtml(r.p[0])+'</td><td title="'+escapeHtml(r.p[1])+'">'+productPhotoCell(r.p)+'</td><td>'+escapeHtml(DATA.categories[r.p[2]])+'</td><td class="num">'+qtyCell(r.qty,r.p)+'</td><td class="num">'+qtyCell(r.buyQty,r.p)+'</td><td class="num">'+qtyCell(r.stockQty,r.p)+'</td><td><span class="tag '+(r.abc==='—'?'none':r.abc.toLowerCase())+'">'+r.abc+'</span></td><td class="num">'+usd(r.rev)+'</td><td class="num">'+usd(r.profit)+'</td><td class="num">'+pct(r.rev?r.profit/r.rev:0)+'</td><td class="num">'+usd(r.stock)+'</td><td class="num">'+(r.coverage===null?'—':fmt(r.coverage,0)+' d')+'</td><td>'+actionBadge(r.action)+'</td></tr>').join('')+'</tbody></table></div>';let begin=base.length?st.pagenum*st.pageSize+1:0;let end=Math.min(base.length,(st.pagenum+1)*st.pageSize);$('pagerText').textContent=fmt(begin)+'–'+fmt(end)+' de '+fmt(base.length)+' productos';$('pagerNum').textContent=(st.pagenum+1)+' / '+totalpages;$('firstPage').disabled=$('prevPage').disabled=st.pagenum===0;$('nextPage').disabled=$('lastPage').disabled=st.pagenum>=totalpages-1;
 loadTablePhotos('productTable');
 $('actionPills').innerHTML=(st.abcFilter!=='all'?'<button class="chip sel" data-abcclear="1">ABC '+st.abcFilter+' ✕</button>':'')+'<button class="chip '+(st.action<0?'sel':'')+'" data-action="-1">Todas</button>'+DATA.actions.map((a,i)=>'<button class="chip '+(st.action===i?'sel':'')+'" data-action="'+i+'">'+escapeHtml(a)+'</button>').join('')}
function renderQuality(){const sum=DATA.summary;let stats=[['SKU analizados',fmt(DATA.products.length)],['Productos de ficha',fmt(DATA.source.productsLines||0)],['Líneas mensuales de ventas (fuente)',fmt(DATA.source.salesLines||0)],['Líneas de compras (fuente)',fmt(DATA.source.purchasesLines||0)],['Registros de stock/bodega',fmt(DATA.stockWarehouses.length)],['Meses visualizables',months[0]+' → '+months[months.length-1]],['Análisis principal',DATA.source.start+' → '+refMonth],['Valor informado en Stock.Valor (NO USAR)',usd(sum.stock_fuente,0)],['Valor estimado stock a costo de catálogo',usd(sum.stock_catalogo,0)]];$('sourceStats').innerHTML='<div class="info-list">'+stats.map(a=>'<div class="info-row"><span class="n">'+escapeHtml(a[0])+'</span><span class="v">'+escapeHtml(a[1])+'</span></div>').join('')+'</div>';
 let defs=[['ABC ventas','SKU con ventas positivas, ordenados por aporte acumulado. A ≈80 %, B ≈15 %, C ≈5 %. Recalculado dentro del filtro.'],['ABC utilidad','Igual metodología, pero ordenando utilidad bruta positiva. Puede diferir del ABC por ventas.'],['Utilidad bruta','Ventas netas menos costo de ventas del periodo seleccionado. No equivale a utilidad neta.'],['Cobertura','Existencias positivas corporativas ÷ (unidades vendidas netas entre '+months[Math.max(0,refLast-2)]+' a '+refMonth+' / '+refDays3+' días). No es rotación contable.'],['Sin demanda 6 meses','Existencias positivas cuya venta neta acumulada '+months[Math.max(0,refLast-5)]+' a '+refMonth+' es ≤ 0; no implica obsolescencia definitiva.'],['XYZ global / ABC × XYZ','La etiqueta XYZ global del importador queda fija en el período histórico de referencia. La nueva pestaña ABC × XYZ recalcula XYZ con CV poblacional de 12 meses completos de unidades (X ≤ 0,50; Y ≤ 1,00; Z > 1,00) hasta el mes final elegido. Incluye meses sin venta como cero. ABC se recalcula sobre ventas netas positivas de los SKU filtrados (incluye proveedor y formato). Sin 12 meses o demanda positiva, el SKU queda sin XYZ.'],['Stock valorizado','Existencia positiva por bodega × costo unitario de ficha. No se netean saldos negativos de otras bodegas.'],['Compras y proveedores','Compras por SKU y proveedor real del movimiento. Rentabilidad no se atribuye al proveedor sin trazabilidad de lotes.'],['Acciones','Etiquetas originales fijas del periodo de referencia. Se filtran por contexto, sin reestimación temporal o por bodega.'],['Rotación / GMROI','No se calculan por falta de inventario promedio histórico valorizado.']];$('formulaNotes').innerHTML='<div class="info-list">'+defs.map(a=>'<div class="info-row"><span class="n">'+escapeHtml(a[0])+'</span><span class="v" style="font-weight:500">'+escapeHtml(a[1])+'</span></div>').join('')+'</div>';
 let notes=[[suspiciousStock?'CRÍTICO · Valor de Stock inconsistente':'REVISAR · Valorización de Stock', suspiciousStock?'La columna Valor no concuerda con cantidad × costo de catálogo. Conciliar contra Kardex/Contabilidad y corregir SQL.':'La valoración con costo de catálogo es estimativa. Validar contra Kardex y cierre contable.'],['Stock sin fecha exacta','No hay fecha de corte explicitada en hoja Stock. Se asume última fotografía recibida; no presentar como cierre de septiembre.'],['Costo del catálogo','No sustituye el costo promedio contable por bodega/lote ni incorpora completamente fletes, descuentos o costos adicionales.'],['Bodega y ventas','La hoja Ventas no identifica bodega. Al filtrar bodega se muestran ventas globales de los productos presentes allí; no son ventas imputables a esa bodega.'],['No calcular pedidos finales','Faltan plazos de entrega, mínimos de compra, reservas, stock en tránsito, calendario comercial y presupuesto.'],['Clasificación de bodegas','Exhibidores, muestras, mercadería dañada, remates, tránsito, faltantes y stock comercial deben separarse antes de recomendar liquidación.'],['Unidades heterogéneas','No sumar existencias físicas de m², unidades, cajas y otras presentaciones para estimar volumen físico uniforme.'],['Mes de referencia','Se consideran completos los meses hasta '+refMonth+'. La hoja Stock no indica una fecha exacta de corte.']];$('qualityNotes').innerHTML='<table class="quality-table">'+notes.map(n=>'<tr><td>'+escapeHtml(n[0])+'</td><td>'+escapeHtml(n[1])+'</td></tr>').join('')+'</table>'}
function openSku(i){let r=view.rows.find(r=>r.i===i);if(!r){let p=DATA.products[i];r={i,p,rev:0,cogs:0,profit:0,qty:0,buys:0,buyQty:0,stockQty:p[7],stock:p[8],coverage:p[14]>0?p[7]*refDays3/p[14]:null,abc:p[10],action:p[13]}}let p=r.p,stockRows=stockWare[i].filter(w=>w[1]>0).sort((a,b)=>b[1]-a[1]);let profile=[['Código',p[0]],['Categoría',DATA.categories[p[2]]],['Marca',DATA.brands[p[3]]],['Formato',productFormat(p)],['Proveedor de ficha',DATA.providers[p[4]]],['Costo de catálogo',usd(p[5],3)],['Precio de lista',usd(p[6],3)],['ABC ventas (subconjunto)',r.abc],['ABC utilidad global',p[11]],['XYZ global',p[12]],...(st.page==='xyz'?(function(){const r=xyzRowsCache.find(row=>row.i===i);return r?[['ABC × XYZ (filtros)',r.xyzGroup],['CV 12 meses',r.xyzCv===null?'No calculable':fmt(r.xyzCv,3)],['Meses con ventas',fmt(r.xyzActive)+' / 12']]:[]})():[]),['Cantidad vendida (período)',fmt(r.qty,2)+' '+unitForProduct(p).label],['Cantidad comprada (período)',fmt(r.buyQty,2)+' '+unitForProduct(p).label],['Valor compras período',usd(r.buys)],['Stock positivo',fmt(r.stockQty,2)+' '+unitForProduct(p).label],['Stock negativo global',fmt(p[9],2)],['Cobertura global estimada',r.coverage===null?'No calculable':fmt(r.coverage,0)+' días'],['Etiqueta global',DATA.actions[p[13]]]];let points=[];for(let m=st.start;m<=st.end;m++){let item=saleBySku[i].find(a=>a[0]===m);points.push(item?item[2]:0)}let max=Math.max(1,...points),W=450,H=130,coord=points.map((val,j)=>[10+(W-20)*(points.length<=1?.5:j/(points.length-1)),H-10-val/max*(H-30)]),poly=coord.map(c=>c.join(',')).join(' ');$('drawerContent').innerHTML='<div class="eyebrow">FICHA DE PRODUCTO</div><h2>'+escapeHtml(p[1])+'</h2>'+actionBadge(p[13])+'<div class="tc-photo-large" data-photo-sku="'+escapeHtml(p[0])+'"><span>Fotografía pendiente de vincular</span></div>'+'<div class="detail-kpis">'+[['Ventas',usd(r.rev)],['Utilidad bruta',usd(r.profit)],['Margen',pct(r.rev?r.profit/r.rev:0)],['Stock estimado',usd(r.stock)]].map(i=>'<div class="detail-kpi"><div class="l">'+i[0]+'</div><div class="v">'+i[1]+'</div></div>').join('')+'</div><h3 style="font-size:14px">Tendencia mensual de ventas</h3><svg viewBox="0 0 '+W+' '+H+'" style="width:100%;background:#f9fbfd;border-radius:9px" aria-label="Ventas mensuales del producto"><polyline points="'+poly+'" stroke="#199f92" stroke-width="3" fill="none"/>'+coord.map((c,j)=>'<circle cx="'+c[0]+'" cy="'+c[1]+'" r="3" fill="#199f92"><title>'+months[st.start+j]+' '+usd(points[j])+'</title></circle>').join('')+'</svg><div class="info-list">'+profile.map(i=>'<div class="info-row"><span class="n">'+escapeHtml(i[0])+'</span><span class="v">'+escapeHtml(i[1])+'</span></div>').join('')+'</div><h3 style="font-size:13px">Ubicaciones con stock positivo (máximo 12)</h3><div class="info-list">'+(stockRows.slice(0,12).map(a=>'<div class="info-row"><span class="n">'+escapeHtml(DATA.warehouses[a[0]])+'</span><span class="v">'+fmt(a[1],2)+' · '+usd(a[1]*Math.max(p[5],0))+'</span></div>').join('')||'<p class="small">Sin stock positivo en bodegas.</p>')+'</div><div class="tipbox"><b>Motivo de señal:</b> '+escapeHtml(p[18])+'<div style="margin-top:6px">Recomendación global histórica. Validar con operaciones antes de comprar o liquidar.</div></div>';fetchPhotoRefs([p[0]]);document.querySelectorAll('.tc-photo-large').forEach(renderPhoto);$('detailBack').classList.add('show');$('drawer').classList.add('show');}
function closeDrawer(){$('detailBack').classList.remove('show');$('drawer').classList.remove('show')}
// Un barrido inicial corto empieza automáticamente al abrir el explorador si
// el usuario dispone del permiso de importación. Las fotografías previamente
// vinculadas aparecen sin esperar a este barrido.
let initialPhotoScanStarted=false;
async function maybeAutoIndexPhotos(){
 if(initialPhotoScanStarted || document.querySelector('meta[name="transcash-can-upload"]')?.content!=='1')return;
 initialPhotoScanStarted=true;
 const csrf=document.querySelector('meta[name="transcash-csrf"]')?.content;
 if(!csrf)return;
 const payload=new FormData();payload.append('csrf_token',csrf);payload.append('limit','2');
 try{
  const res=await fetch('/transcash_inventory/photos/scan',{method:'POST',body:payload,credentials:'same-origin'});
  if(!res.ok)return;
  const result=await res.json();
  if(result.error) return;
  // Actualizar las miniaturas visibles tras descubrir nuevos vínculos.
  document.querySelectorAll('#productTable [data-photo-sku]').forEach(node=>photoQueriedAt.delete(node.getAttribute('data-photo-sku')));
  if(st.page==='productos') fetchPhotoRefs([...document.querySelectorAll('#productTable [data-photo-sku]')].map(node=>node.getAttribute('data-photo-sku')));
 }catch(e){console.info('Índice de imágenes en segundo plano no disponible:',e.message);}
}
// v1.9 · Análisis financiero por proveedor de ficha y proveedor real de compra.
const pfSupplier=$('pfSupplier'),pfFormat=$('pfFormat'),pfBrand=$('pfBrand');
for(const [id,values] of [['pfSupplierList',DATA.providers],['pfFormatList',explorerFormats],['pfBrandList',DATA.brands]]){
 $(id).innerHTML=values.map(x=>'<option value="'+escapeHtml(x)+'"></option>').join('');
}
function pfMatches(value,input){return !input||expNormal(value).includes(expNormal(input));}
function pfFilterRows(){return view.rows.filter(r=>pfMatches(DATA.providers[r.p[4]],pfSupplier.value.trim())&&pfMatches(productFormat(r.p),pfFormat.value.trim())&&pfMatches(DATA.brands[r.p[3]],pfBrand.value.trim()));}
function renderProviderProfit(){
 const rows=pfFilterRows(),tot={rev:0,profit:0,purchases:0,stock:0,sku:0},groups=new Map(),actual=new Map();
 for(const r of rows){
  const supplier=DATA.providers[r.p[4]],format=productFormat(r.p),key=supplier+'\u0001'+format;
  let ob=groups.get(key);if(!ob){ob={supplier,format,sku:0,rev:0,profit:0,buy:0,stock:0,qty:0};groups.set(key,ob)}
  ob.sku++;ob.rev+=r.rev;ob.profit+=r.profit;ob.buy+=r.buys;ob.stock+=r.stock;ob.qty+=r.qty;
  tot.rev+=r.rev;tot.profit+=r.profit;tot.purchases+=r.buys;tot.stock+=r.stock;tot.sku++;
  for(const [m,s,amt] of suppBySku[r.i])if(inPeriod(m)){
   const name=DATA.purchaseSuppliers[s];actual.set(name,(actual.get(name)||0)+amt);
  }
 }
 const ranked=[...groups.values()].sort((a,b)=>b.profit-a.profit);
 const rollup=new Map();for(const r of ranked){const a=rollup.get(r.supplier)||{name:r.supplier,profit:0,rev:0};a.profit+=r.profit;a.rev+=r.rev;rollup.set(r.supplier,a)}
 const profitBySup=[...rollup.values()].sort((a,b)=>b.profit-a.profit);
 const purchased=[...actual].map(([name,buy])=>({name,buy})).sort((a,b)=>b.buy-a.buy);
 $('pfScope').textContent=fmt(tot.sku)+' SKU · '+months[st.start]+' a '+months[st.end]+' · stock al corte disponible'+(st.wh>=0?' · ventas/compras corporativas para SKU de bodega seleccionada':'');
 $('pfKpis').innerHTML=kpi('Ventas cartera proveedor',compact(tot.rev),'Periodo seleccionado','↗')+
  kpi('Utilidad bruta de cartera',compact(tot.profit),'No atribuible a compras por lote','◉','good')+
  kpi('Margen bruto',pct(tot.rev?tot.profit/tot.rev:0),'Utilidad / ventas','%')+
  kpi('Compras de los SKU',compact(tot.purchases),'Todos los proveedores que suministraron los SKU','↘')+
  kpi('Valor stock cartera',compact(tot.stock),'Cantidad positiva × costo catálogo','▣');
 const bars=(id,array,key)=>{
  if(!array.length){$(id).innerHTML='<p class="empty">Sin resultados para estos filtros.</p>';return}
  const max=Math.max(1,...array.slice(0,12).map(x=>x[key]));
  $(id).innerHTML='<div class="barbox">'+array.slice(0,12).map(x=>'<div class="hbar" title="'+escapeHtml(x.name)+'"><span class="hlabel">'+escapeHtml(x.name)+'</span><span class="track"><span class="fill" style="display:block;width:'+Math.max(0,x[key]/max*100)+'%"></span></span><span class="hvalue">'+compact(x[key])+'</span></div>').join('')+'</div>';
 };
 bars('pfProfitBars',profitBySup,'profit');bars('pfPurchaseBars',purchased,'buy');
 $('pfTable').innerHTML=simpleTable(['Proveedor de ficha','Formato','SKU','Ventas netas','Utilidad bruta','Margen','Compras de SKU','Stock estimado'],ranked.slice(0,250).map(x=>[x.supplier,x.format,fmt(x.sku),usd(x.rev,2),usd(x.profit,2),pct(x.rev?x.profit/x.rev:0),usd(x.buy,2),usd(x.stock,2)]));
 $('pfActual').innerHTML=simpleTable(['Proveedor real de compra','Compras netas (USD)','% de compras filtradas'],purchased.slice(0,150).map(x=>[x.name,usd(x.buy,2),pct(tot.purchases?x.buy/tot.purchases:0)]));
}
for(const input of [pfSupplier,pfFormat,pfBrand])input.addEventListener('input',()=>{if(st.page==='provprofit')renderProviderProfit()});
$('pfClear').addEventListener('click',()=>{pfSupplier.value=pfFormat.value=pfBrand.value='';renderProviderProfit()});

// ChatGPT nunca ve una API Key: todas las llamadas pasan por rutas autenticadas del backend.
let aiBusy=false;
async function aiStatusCheck(){
 if(!allowAI)return;
 try{const res=await fetch('/transcash_inventory/ai/status',{credentials:'same-origin'});
 const data=await res.json();$('aiStatus').textContent=data.message||'No disponible';
 $('aiAsk').disabled=!data.enabled;
 }catch(e){$('aiStatus').textContent='No se pudo comprobar configuración';$('aiAsk').disabled=true;}
}
function aiMetricVal(metric,value){
 if(value===null||value===undefined)return '—';
 if(['ventas','utilidad','compras','stock_valor','costo_ventas','precio_promedio'].includes(metric))return usd(value,2);
 if(metric==='margen')return fmt(value,2)+' %';return fmt(value,3);
}
let aiController=null,aiCancelled=false;
function aiProgress(message){$('aiProgress').hidden=false;$('aiProgress').textContent=message;}
function aiStop(){if(aiController){aiController.abort();}aiCancelled=true;}
async function aiFetch(url,form,limitMs){
 const controller=new AbortController();aiController=controller;
 let expired=false;
 const timer=setTimeout(()=>{expired=true;controller.abort();},limitMs);
 try{
  const response=await fetch(url,{method:'POST',body:form,credentials:'same-origin',signal:controller.signal,cache:'no-store'});
  const type=response.headers.get('content-type')||'';
  if(!type.includes('application/json')){
   if(response.redirected||type.includes('text/html'))throw Error('El servidor devolvió una página HTML en lugar del resultado. Verifique que la sesión de Odoo continúe activa y consulte el log del servidor.');
   throw Error('Odoo devolvió una respuesta inesperada (HTTP '+response.status+').');
  }
  const data=await response.json();
  if(!response.ok||data.error){
   const errors={401:'La sesión de Odoo expiró.',403:'No tiene permiso para esta consulta.',409:'Existe otra consulta de IA en proceso.',502:'No se pudo completar la petición a OpenAI.',503:'El servicio no está disponible.'};
   throw Error(data.error||errors[response.status]||'Error HTTP '+response.status);
  }
  return data;
 }catch(e){
  if(e.name==='AbortError'){
   if(expired)throw Error('Tiempo de espera agotado. Revise la conectividad del servidor Odoo con OpenAI o utilice un modelo más rápido.');
   throw Error('Consulta cancelada.');
  }
  if(e instanceof TypeError&&String(e.message).toLowerCase().includes('fetch')){
   throw Error('No se pudo conectar con Odoo. Compruebe la red y los registros del servidor.');
  }
  throw e;
 }finally{clearTimeout(timer);if(aiController===controller)aiController=null;}
}
function aiShowCalculated(data){
 const r=data.result;
 if(!r||!Array.isArray(r.filas))throw Error('Odoo devolvió un indicador sin tabla válida.');
 $('aiAnswer').textContent=data.answer||'Cálculo terminado. Los resultados son verificables en Odoo.';
 $('aiMethod').textContent=(r.etiqueta||r.metrica||'Indicador')+' · '+(r.periodo?.desde||'')+' a '+(r.periodo?.hasta||'')+' · '+(r.grupos_evaluados||0)+' grupos · '+(r.sku_evaluados||0)+' SKU. '+(r.observaciones||[]).join(' ')+(data.warning?' '+data.warning:'');
 const hdr=['Grupo',r.etiqueta||'Resultado','Ventas','Utilidad','Compras','Margen','Stock USD'];
 $('aiResults').innerHTML='<div class="boxsub"><b>Total general:</b> '+aiMetricVal(r.metrica,r.total)+'</div>'+simpleTable(hdr,r.filas.map(row=>[row.grupo,aiMetricVal(r.metrica,row.valor),usd(row.ventas,2),usd(row.utilidad,2),usd(row.compras,2),row.margen===null?'—':fmt(row.margen,2)+' %',usd(row.stock_valor,2)]));
 $('aiResponse').hidden=false;
}
async function aiAsk(){
 if(aiBusy)return;
 const question=$('aiQuestion').value.trim();
 if(question.length<6){$('aiError').hidden=false;$('aiError').textContent='Escribe una pregunta de al menos seis caracteres.';return;}
 aiBusy=true;aiCancelled=false;
 $('aiAsk').disabled=true;$('aiCancel').hidden=false;
 $('aiError').hidden=true;$('aiResponse').hidden=true;
 const csrf=document.querySelector('meta[name="transcash-csrf"]')?.content;
 if(!csrf){$('aiError').hidden=false;$('aiError').textContent='No se obtuvo el token de seguridad. Recargue el dashboard.';aiBusy=false;$('aiAsk').disabled=false;$('aiCancel').hidden=true;return;}
 const form=new FormData();form.append('csrf_token',csrf);form.append('fast','1');
 form.append('question',question);form.append('desde',months[st.start]);form.append('hasta',months[st.end]);
 const sid=new URLSearchParams(window.location.search).get('snapshot_id');if(sid&&/^\d+$/.test(sid))form.append('snapshot_id',sid);
 if(st.cat>=0)form.append('categoria',DATA.categories[st.cat]);
 if(st.brand>=0)form.append('marca',DATA.brands[st.brand]);
 let calculated=false;
 try{
  $('aiAsk').textContent='Interpretando...';
  aiProgress('Paso 1 de 2 · ChatGPT interpreta la pregunta y Odoo calcula los indicadores. Máximo 40 segundos de espera.');
  const data=await aiFetch('/transcash_inventory/ai/ask',form,40000);
  if(aiCancelled)throw Error('Consulta cancelada.');
  aiShowCalculated(data);calculated=true;
  if(data.narration_signature&&data.narration_expiry){
   $('aiAsk').textContent='Explicando...';
   aiProgress('Paso 2 de 2 · Indicadores calculados. ChatGPT está preparando la explicación; la tabla ya está disponible.');
   const explanation=new FormData();explanation.append('csrf_token',csrf);
   explanation.append('question',question);
   explanation.append('result_json',JSON.stringify(data.result));
   explanation.append('signature',data.narration_signature);
   explanation.append('expires_at',String(data.narration_expiry));
   try{
    const narration=await aiFetch('/transcash_inventory/ai/explain',explanation,40000);
    if(!aiCancelled)$('aiAnswer').textContent=narration.answer;
   }catch(e){
    if(!aiCancelled){
     $('aiAnswer').textContent='El indicador se calculó correctamente, pero no se pudo obtener la explicación automática. '+e.message;
    }
   }
  }
 }catch(e){
  $('aiError').textContent=e.message||'No fue posible completar la consulta.';
  $('aiError').hidden=false;
  if(calculated)$('aiResponse').hidden=false;
 }finally{
  aiBusy=false;aiController=null;
  $('aiAsk').disabled=false;$('aiCancel').hidden=true;
  $('aiAsk').textContent='✧ Calcular con ChatGPT';
  $('aiProgress').hidden=true;
 }
}
$('aiAsk').addEventListener('click',aiAsk);
$('aiCancel').addEventListener('click',aiStop);
$('aiQuestion').addEventListener('keydown',e=>{if(e.ctrlKey&&e.key==='Enter'){e.preventDefault();aiAsk();}});
document.querySelectorAll('[data-ai-question]').forEach(btn=>btn.addEventListener('click',()=>{$('aiQuestion').value=btn.dataset.aiQuestion;$('aiQuestion').focus();}));
if(allowAI)aiStatusCheck();

function setPage(p){if(p==='asistente'&&!allowAI)return;st.page=p;mountExplorerFilters(p);for(let btn of document.querySelectorAll('#nav button'))btn.classList.toggle('active',btn.dataset.page===p);document.querySelectorAll('.section').forEach(n=>n.classList.toggle('on',n.id==='section-'+p));$('pageTitle').textContent=({resumen:'Panorama del inventario',abc:'ABC y rentabilidad',rotacion:'Cobertura y capital inmovilizado',comprasplan:'Simulador de reposición',bodegas:'Stock por ubicación',proveedores:'Compras y proveedores',productos:'Explorador de productos',provprofit:'Rentabilidad por proveedor',asistente:'Consultar con ChatGPT',xyz:'Análisis ABC × XYZ',calidad:'Control y metodología'})[p];renderAll();if(p==='productos'||p==='xyz')maybeAutoIndexPhotos();window.scrollTo({top:0,behavior:'smooth'})}
function exportCsv(){const v=view,rows=st.page==='xyz'?xyzSortRows(xyzSelectedRows()):st.page==='productos'?expFilterRows():st.page==='provprofit'?pfFilterRows():v.rows.filter(r=>(st.action<0||r.action===st.action)&&(st.abcFilter==='all'||r.abc===st.abcFilter)),head=['Codigo','Descripcion','Categoria','Marca','Formato','Proveedor_ficha','Ventas_USD_periodo','CostoVentas_USD_periodo','UtilidadBruta_USD_periodo','MargenBruto','ABC_ventas_filtrado','ABC_utilidad_filtrado','ABC_ventas_global_12m','XYZ_global_12m','ABC_XYZ_filtrado','XYZ_periodo','CV_XYZ_12m','Meses_ventas_12m','Compras_USD_periodo','Cantidad_vendida_periodo','Cantidad_comprada_periodo','Unidad_medida_referencial','Stock_cantidad','Stock_valorizado_estimado_USD','Cobertura_global_dias','Accion_global','Motivo_global'];const safe=s=>'"'+String(s??'').replace(/"/g,'""')+'"';const lines=[head.map(safe).join(';')];for(const r of rows){let p=r.p;const vals=[p[0],p[1],DATA.categories[p[2]],DATA.brands[p[3]],productFormat(p),DATA.providers[p[4]],r.rev.toFixed(2),r.cogs.toFixed(2),r.profit.toFixed(2),r.rev?(r.profit/r.rev).toFixed(5):'',r.abc,r.abcProfit,p[10],p[12],r.xyzGroup||'',r.xyz||'',r.xyzCv==null?'':r.xyzCv.toFixed(5),r.xyzActive==null?'':r.xyzActive,r.buys.toFixed(2),r.qty.toFixed(4),r.buyQty.toFixed(4),unitForProduct(p).label,r.stockQty.toFixed(4),r.stock.toFixed(2),r.coverage===null?'':r.coverage.toFixed(2),DATA.actions[p[13]],p[18]];lines.push(vals.map(safe).join(';'))}const blob=new Blob(['\ufeff'+lines.join('\r\n')],{type:'text/csv;charset=utf-8;'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='Transcash_analisis_filtrado_'+months[st.start]+'_'+months[st.end]+'.csv';document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),2000)}
function reset(){st.cat=-1;st.brand=-1;st.wh=-1;st.providerExp=-1;st.formatExp=-1;st.search='';st.action=-1;st.abcFilter='all';st.xyzCell='all';st.xyzPage=0;st.xyzSort='rev';st.xyzDesc=true;st.goalDays=60;$('goalDays').value='60';st.pagenum=0;st.sort='rev';st.desc=true;$('cat').value=$('brand').value=$('wh').value='-1';$('search').value='';if(openExpCombo)expClose(openExpCombo,false);expSyncValues();$('period').value='12';setPeriod('12')}
$('nav').addEventListener('click',e=>{const el=e.target.closest('[data-page]');if(el)setPage(el.dataset.page)});$('period').addEventListener('change',e=>setPeriod(e.target.value));for(let id of ['from','to'])$(id).addEventListener('change',()=>{let from=+$('from').value,to=+$('to').value;if(from>to){if(id==='from')$('to').value=from;else $('from').value=to}st.start=+$('from').value;st.end=+$('to').value;st.pagenum=0;update()});for(let [id,key]of [['cat','cat'],['brand','brand'],['wh','wh']])$(id).addEventListener('change',e=>{st[key]=+e.target.value;st.pagenum=0;update()});let debounce; $('search').addEventListener('input',e=>{clearTimeout(debounce);const value=e.target.value;debounce=setTimeout(()=>{st.search=value;st.pagenum=0;update()},180)});$('goalDays').addEventListener('change',e=>{st.goalDays=+e.target.value;renderPlan()});$('resetBtn').addEventListener('click',reset);$('exportBtn').addEventListener('click',exportCsv);$('helpBtn').addEventListener('click',()=>setPage('calidad'));$('drawerClose').addEventListener('click',closeDrawer);$('detailBack').addEventListener('click',closeDrawer);document.addEventListener('keydown',e=>{if(e.key==='Escape')closeDrawer()});document.addEventListener('click',e=>{const xy=e.target.closest('[data-xyz-cell]');if(xy){st.xyzCell=xy.dataset.xyzCell;st.xyzPage=0;renderXYZ();return;}const xySort=e.target.closest('[data-xyz-sort]');if(xySort){const key=xySort.dataset.xyzSort;if(key===st.xyzSort)st.xyzDesc=!st.xyzDesc;else{st.xyzSort=key;st.xyzDesc=!['sku','name','abcxyz','xyz'].includes(key);}st.xyzPage=0;renderXYZ();return;}const ab=e.target.closest('[data-abc]');if(ab&&ab.dataset.abc){st.abcFilter=ab.dataset.abc;st.pagenum=0;setPage('productos');return}const abcClear=e.target.closest('[data-abcclear]');if(abcClear){st.abcFilter='all';st.pagenum=0;renderProducts();return}const cat=e.target.closest('[data-cat]');if(cat){st.cat=+cat.dataset.cat;$('cat').value=st.cat;st.pagenum=0;update();return}const wh=e.target.closest('[data-wh]');if(wh){st.wh=+wh.dataset.wh;$('wh').value=st.wh;st.pagenum=0;update();return}const act=e.target.closest('[data-action]');if(act){st.action=+act.dataset.action;st.pagenum=0;renderProducts();return}const th=e.target.closest('[data-sort]');if(th){let key=th.dataset.sort;if(key===st.sort)st.desc=!st.desc;else{st.sort=key;st.desc=!['sku','name','category','abc','action'].includes(key)}st.pagenum=0;renderProducts();return}const sku=e.target.closest('[data-sku]');if(sku){openSku(+sku.dataset.sku);return}});[['firstPage',()=>st.pagenum=0],['prevPage',()=>st.pagenum--],['nextPage',()=>st.pagenum++],['lastPage',()=>{let n=expFilterRows().length;st.pagenum=Math.max(0,Math.ceil(n/st.pageSize)-1)}]].forEach(([id,fn])=>$(id).addEventListener('click',()=>{fn();renderProducts()}));[['xyzFirst',()=>st.xyzPage=0],['xyzPrev',()=>st.xyzPage--],['xyzNext',()=>st.xyzPage++],['xyzLast',()=>st.xyzPage=Math.max(0,Math.ceil(xyzSelectedRows().length/st.xyzPageSize)-1)]].forEach(([id,fn])=>$(id).addEventListener('click',()=>{fn();renderXYZ()}));expInit();update();
})().catch(e=>{console.error("Transcash - dashboard",e);showUnavailable("Error cargando indicadores: "+e.message);});
