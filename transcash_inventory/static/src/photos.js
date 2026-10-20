(() => {
'use strict';
const $=id=>document.getElementById(id);
const csrf=document.querySelector('meta[name=transcash-csrf]').content;
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let running=false;
let state={};
const fmt=v=>new Intl.NumberFormat('es-EC').format(v||0);
function message(text,isError=false){$('status').textContent=text;$('status').classList.toggle('error',isError)}
async function jsonFetch(url,postData=null){
 const opts={credentials:'same-origin',cache:'no-store'};
 if(postData){const body=new FormData();body.set('csrf_token',csrf);Object.entries(postData).forEach(([k,v])=>body.set(k,v));opts.method='POST';opts.body=body}
 const response=await fetch(url,opts);const data=await response.json().catch(()=>({error:'Respuesta inválida del servidor'}));if(!response.ok)throw new Error(data.error||'HTTP '+response.status);return data;
}
function paint(data){state=data; $('totalProducts').textContent=fmt(data.total_products);$('examined').textContent=fmt(data.examined);$('matched').textContent=fmt(data.photos_linked);$('nextPage').textContent=String(data.next_page||1);$('bar').style.width=Math.min(100,100*(Math.max(1,data.next_page)-1)/Math.max(1,Number(data.pages_limit||90)))+'%';if(data.finished){message('Búsqueda finalizada. '+fmt(data.photos_linked)+' SKU con vínculo de fotografía.');running=false;buttons();}else if(data.last_error){message(data.last_error,true)} }
function buttons(){$('start').disabled=running||state.finished;$('stop').disabled=!running;$('reset').disabled=running}
async function refresh(){try{paint(await jsonFetch('/transcash_inventory/photos/status'));}catch(e){message(e.message,true)}}
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function start(){if(running)return;running=true;buttons();message('Consultando Transcash.ec…');while(running){let next;try{next=await jsonFetch('/transcash_inventory/photos/scan',{'limit':'2'});paint(next);if(next.last_error||next.finished||next.next_page>90){running=false;break;}message('Buscando imágenes… página '+next.next_page+' · '+fmt(next.photos_linked)+' vínculos encontrados');await sleep(950)}catch(e){running=false;message(e.message,true);break;}}buttons()}
$('start').addEventListener('click',start);
$('stop').addEventListener('click',()=>{running=false;buttons();message('Búsqueda detenida. Puedes retomarla después.')});
$('reload').addEventListener('click',refresh);
$('reset').addEventListener('click',async()=>{if(running||!confirm('¿Reiniciar desde la primera página del catálogo? Se conservan las imágenes vinculadas.'))return;try{paint(await jsonFetch('/transcash_inventory/photos/reset',{'confirm':'yes'}));message('Búsqueda reiniciada. Las imágenes existentes se conservaron.')}catch(e){message(e.message,true)}});
$('link').addEventListener('click',async()=>{let sku=$('sku').value.trim(),url=$('productUrl').value.trim();if(!sku||!url){message('Ingrese SKU y URL de la ficha.',true);return;}try{const result=await jsonFetch('/transcash_inventory/photos/link',{sku,url});message('Ficha vinculada por SKU exacto: '+result.sku);await refresh();$('lookup').click();}catch(e){message(e.message,true)}});
$('lookup').addEventListener('click',async()=>{let sku=$('sku').value.trim();if(!sku)return;try{let d=await jsonFetch('/transcash_inventory/photos/lookup?sku='+encodeURIComponent(sku));$('example').innerHTML=d.image_url?'<img src="'+esc(d.image_url)+'" alt="Foto de producto" referrerpolicy="no-referrer" onerror="this.style.visibility=\'hidden\'"/><div><b>'+esc(sku)+'</b><p>Coincidencia: '+esc(d.match_type||'SKU')+'</p><a href="'+esc(d.website_url)+'" target="_blank" rel="noopener noreferrer">Abrir ficha en Transcash.ec ↗</a></div>':'<div class="placeholder">Sin imagen</div><div><b>'+esc(sku)+'</b><p>Aún no existe una fotografía vinculada a este código.</p></div>'}catch(e){message(e.message,true)}});
refresh();
})();
