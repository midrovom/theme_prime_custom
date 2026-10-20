(() => {
'use strict';
const $ = id => document.getElementById(id);
const csrf = document.querySelector('meta[name=transcash-csrf]').content;
const esc = s => String(s??'').replace(/[&<>"']/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt = n => new Intl.NumberFormat('es-EC').format(Number(n)||0);
let running=false, state={};
function message(text, bad=false){ $('status').textContent=text; $('status').classList.toggle('error',bad) }
async function req(url, payload=null){
 const opt={credentials:'same-origin',cache:'no-store'};
 if(payload){const body=new FormData();body.set('csrf_token',csrf);
   for(const [k,v] of Object.entries(payload))body.set(k,v);opt.method='POST';opt.body=body;}
 const r=await fetch(url,opt),d=await r.json().catch(()=>({error:'Respuesta inesperada'}));
 if(!r.ok)throw new Error(d.error||'Error HTTP '+r.status);
 return d;
}
function paint(d){
 state=d;
 $('totalProducts').textContent=fmt(d.total_products);$('examined').textContent=fmt(d.examined);
 $('matched').textContent=fmt(d.photos_linked);$('nextPage').textContent=String(d.next_page||1);
 $('bar').style.width=Math.min(100,(Math.max(1,d.next_page)-1)/Math.max(1,d.pages_limit||90)*100)+'%';
 $('details').textContent=`Fotografías verificadas: ${fmt(d.photos_linked)} · Pendientes: ${fmt(d.photos_pending)} · Para revisar: ${fmt(d.photos_failed)}`;
 if(d.finished){message('Recorrido del catálogo terminado. La búsqueda por SKU individual sigue disponible.');running=false;buttons();}
 else if(d.last_error)message(d.last_error,true);
}
function buttons(){$('start').disabled=running||state.finished;$('stop').disabled=!running;$('reset').disabled=running}
async function refresh(){try{paint(await req('/transcash_inventory/photos/status'))}catch(e){message(e.message,true)}}
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
async function start(){
 if(running)return;running=true;buttons();message('Consultando enlaces del catálogo…');
 while(running){try{let d=await req('/transcash_inventory/photos/scan',{limit:'2'});paint(d);
   if(d.finished||d.last_error||d.next_page>90){running=false;break;}
   message('Indexando enlaces… página '+d.next_page);await sleep(1000);
 }catch(e){running=false;message(e.message,true);break;}}
 buttons();
}
const statuses={verified:'Imagen verificada',queued:'Pendiente de búsqueda',unchecked:'Enlace por comprobar',
  not_found:'El SKU no apareció en la búsqueda pública',broken:'Ficha o imagen no válida',error:'Error consultando la tienda',unindexed:'Sin búsqueda registrada'};
function preview(d,sku){
 let title=statuses[d.status]||'No se encontró registro', details=d.error?'<p class="problem">'+esc(d.error)+'</p>':'';
 const photo=d.image_url&&(/^(?:https:\/\/(?:www\.)?transcash\.ec\/web\/(?:image|content)\/|\/transcash_inventory\/photos\/thumb\?sku=)/i.test(d.image_url))
  ?'<img src="'+esc(d.image_url)+'" alt="Foto de '+esc(sku)+'" referrerpolicy="no-referrer"/>'
  :'<div class="placeholder">'+esc(d.status==='error'?'Reintentar':d.status==='not_found'?'Sin coincidencia':'Sin foto')+'</div>';
 $('example').innerHTML=photo+'<div><b>'+esc(d.sku||sku)+'</b><p>'+esc(title)+'</p>'+details+
 (d.website_url?'<a href="'+esc(d.website_url)+'" target="_blank" rel="noopener noreferrer">Abrir ficha ↗</a>':'')+'</div>';
 const el=$('example').querySelector('img');
 if(el)el.addEventListener('error',()=>{el.replaceWith(Object.assign(document.createElement('div'),{className:'placeholder',textContent:'No carga la fotografía'}))},{once:true});
}
async function lookup(){let sku=$('sku').value.trim();if(!sku)return;
 try{let d=await req('/transcash_inventory/photos/lookup?sku='+encodeURIComponent(sku));preview(d,sku)}catch(e){message(e.message,true)} }
async function resolve(exact=false){
 const sku=$('sku').value.trim(),url=$('productUrl').value.trim();
 if(!sku || exact&&!url){message(exact?'Ingrese SKU y URL de la ficha':'Ingrese un SKU',true);return;}
 const btn=$(exact?'link':'resolve');btn.disabled=true;
 message(exact?'Comprobando la ficha y su imagen…':'Buscando SKU exacto en Transcash.ec…');
 try{
   const r=await req('/transcash_inventory/photos/resolve',exact?{sku,url}:{sku});
   preview(r,sku);message(r.ok?'Fotografía verificada y vinculada a '+r.sku:
     'No se pudo verificar la foto: '+(r.error||statuses[r.status]||'Revise el estado'),!r.ok);
   await refresh();
 }catch(e){message(e.message,true)}finally{btn.disabled=false}
}
$('start').addEventListener('click',start);
$('stop').addEventListener('click',()=>{running=false;buttons();message('Búsqueda detenida. Puedes retomarla después.')});
$('reload').addEventListener('click',refresh);
$('reset').addEventListener('click',async()=>{if(running||!confirm('¿Reiniciar índice público? No elimina fotos verificadas.'))return;
 try{paint(await req('/transcash_inventory/photos/reset',{confirm:'yes'}));message('Búsqueda de catálogo reiniciada.')}catch(e){message(e.message,true)}});
$('lookup').addEventListener('click',lookup);
$('resolve').addEventListener('click',()=>resolve(false));
$('link').addEventListener('click',()=>resolve(true));
$('sku').addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();lookup()}});
refresh();
})();
