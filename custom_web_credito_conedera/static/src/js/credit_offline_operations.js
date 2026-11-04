/** Cola offline para corrección, croquis integrado y documentos del portal.
 * Mantiene archivos originales en IndexedDB; no usa localStorage ni Cache API
 * para datos personales. Ningún envío se considera exitoso sin respuesta Odoo.
 */
(function () {
    'use strict';
    const rootPath = '/my/credito/';
    const match = location.pathname.match(/^\/my\/credito\/(\d+)\/(editar|documentos)$/);
    if (!location.pathname.startsWith(rootPath)) { return; }
    const applicationId = match ? Number(match[1]) : 0;
    const mode = match ? (match[2] === 'documentos' ? 'documents' : 'update') : null;
    const DB = 'solicitud-credito-offline-v1';
    const MAX_TOTAL_BYTES = 160 * 1024 * 1024;
    let form, identity, baseKey, key, current, restoring = false, saveTimer, sending = false;
    let warning, removeButton;
    let writeQueue = Promise.resolve();
    const uuid = function () {
        if (crypto.randomUUID) { return crypto.randomUUID(); }
        return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
            const n = crypto.getRandomValues(new Uint8Array(1))[0] & 15;
            return (c === 'x' ? n : (n & 3 | 8)).toString(16);
        });
    };
    const openDb = () => new Promise((resolve, reject) => {
        const r = indexedDB.open(DB, 1);
        r.onupgradeneeded = () => {
            if (!r.result.objectStoreNames.contains('drafts')) { r.result.createObjectStore('drafts', {keyPath:'key'}); }
            if (!r.result.objectStoreNames.contains('templates')) { r.result.createObjectStore('templates', {keyPath:'key'}); }
        };
        r.onsuccess = () => resolve(r.result);
        r.onerror = () => reject(r.error);
    });
    async function dbTask(storeName, action, readwrite = false) {
        const db = await openDb();
        try {
            return await new Promise((resolve, reject) => {
                const tx = db.transaction(storeName, readwrite ? 'readwrite' : 'readonly');
                const r = action(tx.objectStore(storeName));
                r.onsuccess = () => resolve(r.result);
                r.onerror = () => reject(r.error);
                tx.onabort = () => reject(tx.error);
            });
        } finally { db.close(); }
    }
    const get = (s,k) => dbTask(s, x => x.get(k));
    const put = (s,v) => dbTask(s, x => x.put(v), true);
    const remove = (s,k) => dbTask(s, x => x.delete(k), true);
    const all = s => dbTask(s, x => x.getAll());
    function identityFromForm(f) {
        return {user_id:Number(f.dataset.creditUser), website_id:Number(f.dataset.creditWebsite), company_id:Number(f.dataset.creditCompany)};
    }
    function identityKey(i) {
        return [location.origin, i.website_id, i.company_id, i.user_id].join('|');
    }
    function banner(message, level = 'info') {
        if (!warning) { return; }
        warning.hidden = false;
        warning.textContent = message;
        warning.className = 'credit-offline-bar credit-offline-' + level;
    }
    function addBar() {
        warning = form.querySelector('[data-credit-offline-operation-status]');
        if (!warning) {
            warning = document.createElement('div');
            warning.dataset.creditOfflineOperationStatus = '1';
            warning.setAttribute('role','status'); warning.setAttribute('aria-live','polite');
            form.insertBefore(warning,form.firstChild);
        }
        warning.hidden = true;
        removeButton = form.querySelector('[data-credit-remove-local-operation]');
        if (!removeButton) {
            const actions = document.createElement('div');
            actions.className = 'credit-offline-actions';
            removeButton = document.createElement('button');
            removeButton.type = 'button';
            removeButton.className = 'btn btn-outline-danger btn-sm';
            removeButton.textContent = 'Eliminar borrador de este dispositivo';
            removeButton.dataset.creditRemoveLocalOperation = '1';
            actions.appendChild(removeButton);
            warning.after(actions);
        }
        removeButton.hidden = true;
        removeButton.addEventListener('click', async () => {
            if (!confirm('¿Eliminar los cambios y archivos pendientes guardados solo en este dispositivo?')) { return; }
            await remove('drafts',key);
            current = null;
            removeButton.hidden = true;
            banner('El borrador local se eliminó. Los cambios sin enviar no se guardaron en Odoo.');
        });
    }
    function snapshot() {
        const entries=[];
        let size=0;
        new FormData(form).forEach((value,name) => {
            if (name === 'csrf_token') { return; }
            if (value instanceof File) {
                if (!value.name || !value.size) { return; }
                size += value.size;
                entries.push({name,value,filename:value.name});
            } else { entries.push({name,value:String(value)}); }
        });
        if (size > MAX_TOTAL_BYTES) { throw new Error('Los archivos acumulados superan 160 MB. Reduzca el tamaño.'); }
        return entries;
    }
    function blankHtml() {
        const clone = form.cloneNode(true);
        clone.querySelectorAll('input[name="csrf_token"], [data-credit-offline-operation-status], [data-credit-remove-local-operation], .credit-offline-actions').forEach(n=>n.remove());
        clone.querySelectorAll('input,textarea').forEach(input => {
            if (input.type === 'file') { input.removeAttribute('value'); return; }
            if (input.type === 'checkbox' || input.type === 'radio') { input.removeAttribute('checked'); return; }
            input.removeAttribute('value');
            if (input.tagName === 'TEXTAREA') { input.textContent=''; }
        });
        clone.querySelectorAll('option').forEach(n=>n.removeAttribute('selected'));
        // La plantilla es de uso local: no guardar imágenes ni archivos privados del servidor.
        clone.querySelectorAll('img[src*="/my/credito/"],iframe[src*="/my/credito/"]').forEach(n=>n.remove());
        clone.querySelectorAll('[data-credit-document-list]').forEach(n=>n.replaceChildren());
        return clone.outerHTML;
    }
    async function cacheTemplate() {
        if (!navigator.onLine) { return; }
        const css = Array.from(document.querySelectorAll('link[rel="stylesheet"][href]'))
            .map(n=>n.href).filter(u=>new URL(u,location.href).origin===location.origin);
        const styles = Array.from(document.querySelectorAll('style')).map(n=>n.textContent||'')
            .filter(t=>t.includes('--credit-')).join('\n').slice(0,20000);
        await put('templates', {key,mode,applicationId,identity,html:blankHtml(),css,
            theme:styles,updatedAt:Date.now()});
        navigator.serviceWorker?.ready.then(reg => {
            (navigator.serviceWorker.controller||reg.active)?.postMessage({type:'CREDIT_CACHE_ASSETS',urls:css});
        }).catch(()=>{});
    }
    function save(pending, quiet = false) {
        // Serializar escrituras: un autoguardado anterior nunca puede sobrescribir
        // un envío ya marcado como pendiente en IndexedDB.
        const task = async () => {
            if (restoring || !form) { return null; }
            try {
                const entries = snapshot();
                const token = (current && current.status === 'pending') ? current.operation_uuid : uuid();
                const record = {key,mode,applicationId,identity,operation_uuid:token,
                    updatedAt:Date.now(),status:(pending || (current && current.status === 'pending'))?'pending':'draft',entries};
                await put('drafts',record);
                current=record;
                removeButton.hidden=false;
                if (!quiet) {
                    banner(pending ? 'Sin conexión. Guardado local pendiente de sincronización.' :
                        'Cambios guardados temporalmente en este dispositivo' + (navigator.onLine ? '.' : ' · Sin conexión.'),
                        pending?'pending':'info');
                }
                return record;
            } catch(error) {
                banner('No se pudo guardar: '+error.message+' Compruebe el espacio disponible del navegador.','error');
                return null;
            }
        };
        const next = writeQueue.then(task, task);
        writeQueue = next.catch(()=>{});
        return next;
    }
    function restoreEntries(record) {
        if (!record || !record.entries) { return; }
        restoring=true;
        try {
            const counts={};
            record.entries.forEach(e=>{if (/_count$/.test(e.name)) {counts[e.name]=Number(e.value);}});
            if (mode==='update') {
                const addVehicle=document.getElementById('credit-add-vehicle');
                const amount=Math.min(30,counts.vehicle_count||1);
                for (let i=1;i<amount && addVehicle;i++){addVehicle.click();}
                ['commercial','personal','bank'].forEach(kind=>{
                    const target=Math.min(30,counts[kind+'_count']||1);
                    const btn=form.querySelector('[data-credit-add-reference="'+kind+'"]');
                    const list=form.querySelector('[data-credit-reference-body="'+kind+'"]');
                    for(let j=list?list.children.length:0;j<target&&btn;j++){btn.click();}
                });
            }
            const fileMap={};
            const radios={};
            record.entries.forEach(e=>{
                if(e.name==='application_date'){return;}
                const node=form.elements.namedItem(e.name);
                if (!node){return;}
                if(e.value instanceof Blob){(fileMap[e.name]||(fileMap[e.name]=[])).push(e);return;}
                if(node instanceof RadioNodeList && !node.tagName){
                    Array.from(node).forEach(n=>{if(n.type==='radio'){n.checked=n.value===e.value;}});
                } else if(node.type==='checkbox'){node.checked=true;}
                else if('value' in node){node.value=e.value;}
            });
            Object.keys(fileMap).forEach(name=>{
                const node=form.elements.namedItem(name);
                if (!node || node.type!=='file'){return;}
                try {
                    const dt=new DataTransfer();
                    fileMap[name].forEach(e=>dt.items.add(e.value instanceof File ? e.value :
                        new File([e.value],e.filename||'archivo',{type:e.value.type})));
                    node.files=dt.files;
                    node.dispatchEvent(new Event('change',{bubbles:true}));
                } catch(error){banner('No se pudieron restaurar todos los archivos. Vuelva a seleccionarlos.','error');}
            });
            document.getElementById('credit-applicant-type')?.dispatchEvent(new Event('change',{bubbles:true}));
            ['credit-identification-type','credit-employment-relationship','credit-employer-type'].forEach(id=>{
                document.getElementById(id)?.dispatchEvent(new Event('change',{bubbles:true}));
            });
            if(mode==='update' && window.creditWizardGoto){window.creditWizardGoto(6);}
            banner(record.status==='pending' ? 'Pendiente de enviar a Odoo cuando vuelva internet y exista una sesión válida.' :
                'Se recuperó el borrador local. Revise los cambios antes de Guardar.',record.status);
            removeButton.hidden=false;
        }finally{restoring=false;}
    }
    async function fetchWithTimeout(url, options, timeoutMs) {
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), timeoutMs);
        try { return await fetch(url, Object.assign({}, options, {signal: controller.signal})); }
        catch (error) {
            if (error && (error.name === 'TypeError' || error.name === 'AbortError')) {
                error.creditNetworkFailure = true;
            }
            throw error;
        }
        finally { clearTimeout(timeout); }
    }
    function isConnectivityFailure(error) {
        return Boolean(error && error.creditNetworkFailure === true);
    }
    async function send(record, silent = false, force = false) {
        if (!record || (!force && record.status !== 'pending') || sending) { return; }
        sending=true;
        banner('Guardando los cambios en Odoo…','info');
        try {
            const response=await fetchWithTimeout(rootPath+'offline/context',{credentials:'same-origin',cache:'no-store'},20000);
            if(!response.ok){throw new Error('No se verificó la sesión (HTTP '+response.status+'). Inicie sesión de nuevo.');}
            if(!(response.headers.get('content-type')||'').includes('application/json')){
                throw new Error('Odoo devolvió una página en lugar de la sesión. Vuelva a iniciar sesión.');
            }
            const context=await response.json();
            if(identityKey(context)!==identityKey(record.identity)){
                throw new Error('La sesión actual no corresponde a la empresa y usuario del borrador.');
            }
            const body=new FormData();
            record.entries.forEach(e=>{
                if(e.value instanceof Blob){body.append(e.name,e.value,e.filename||e.value.name||'archivo');}
                else{body.append(e.name,e.value);}
            });
            body.set('csrf_token',context.csrf_token);
            body.set('offline_operation',record.mode);
            body.set('offline_application_id',String(record.applicationId));
            body.set('offline_operation_uuid',record.operation_uuid);
            body.set('offline_website_id',String(record.identity.website_id));
            body.set('offline_company_id',String(record.identity.company_id));
            const posted=await fetchWithTimeout(rootPath+'offline/dispatch',{method:'POST',credentials:'same-origin',cache:'no-store',body},180000);
            if(!posted.ok){throw new Error('Odoo rechazó el envío (HTTP '+posted.status+'). Revise la sesión o el servidor.');}
            if(!(posted.headers.get('content-type')||'').includes('application/json')){
                throw new Error('Odoo devolvió una respuesta inesperada. Vuelva a iniciar sesión si corresponde.');
            }
            const answer=await posted.json();
            if(answer.status==='sent'){
                await remove('drafts',record.key);
                if(current && current.operation_uuid===record.operation_uuid){current=null;}
                banner('Los cambios se guardaron correctamente en Odoo.','success');
                if(!silent){
                    location.assign(record.mode==='documents'?rootPath+'historial?documentos_guardados=1':
                        rootPath+record.applicationId+'?updated=1');
                }
                return;
            }
            // Una respuesta de Odoo, incluso 'retry', no es una desconexión.
            record.status='draft';await put('drafts',record);current=record;
            banner((answer.message||'Odoo no pudo guardar la operación.')+' '+(answer.errors||[]).join(' · '),'error');
        }catch(error){
            if(isConnectivityFailure(error)){
                record.status='pending';await put('drafts',record);current=record;
                banner('No hubo respuesta de red. Cambios guardados localmente, pendientes de sincronización.','pending');
                askBackgroundSync();
            }else{
                record.status='draft';await put('drafts',record);current=record;
                banner('Odoo no guardó la operación: '+error.message+' Puede volver a pulsar Guardar.','error');
            }
        }finally{sending=false;}
    }
    async function syncAll() {
        if(!navigator.onLine||!baseKey){return;}
        const records=await all('drafts');
        const mine=records.filter(r=>r.mode && r.status==='pending' && identityKey(r.identity||{})===baseKey);
        for(const r of mine){await send(r);}
    }
    function askBackgroundSync(){
        navigator.serviceWorker?.ready.then(reg=>reg.sync?.register('credit-send-pending')).catch(()=>{});
    }
    async function sendNewApplication(record, context) {
        try {
            const body = new FormData();
            record.entries.forEach(e => {
                if (e.value instanceof Blob) { body.append(e.name,e.value,e.filename||e.value.name||'archivo'); }
                else { body.append(e.name,e.value); }
            });
            body.set('csrf_token',context.csrf_token);
            const response = await fetch(rootPath+'offline/submit',{
                method:'POST',credentials:'same-origin',cache:'no-store',body
            });
            if(!response.ok || !(response.headers.get('content-type')||'').includes('application/json')){return;}
            const answer = await response.json();
            if(answer.status==='sent') { await remove('drafts',record.key); }
            else if(answer.status==='review'||answer.status==='blocked') {
                record.status='draft';await put('drafts',record);
            }
        } catch(error) { /* No se elimina el borrador sin confirmación del servidor. */ }
    }
    // iOS no implementa Background Sync de manera uniforme. Mientras cualquier
    // página del portal esté abierta, reintentar cambios de este mismo usuario,
    // dominio y empresa, aunque ya haya salido del formulario original.
    async function syncFromPortal() {
        if (!navigator.onLine) { return; }
        try {
            const response = await fetch(rootPath+'offline/context',{credentials:'same-origin',cache:'no-store'});
            if (!response.ok || !(response.headers.get('content-type')||'').includes('application/json')) { return; }
            const currentIdentity = await response.json();
            const scope = identityKey(currentIdentity);
            const pending = (await all('drafts')).filter(r => r.status==='pending' &&
                (r.mode ? identityKey(r.identity||{}) === scope : r.key === scope));
            baseKey = scope;
            for (const record of pending) {
                if (record.mode === 'update' || record.mode === 'documents') { await send(record,true); }
                else if (!record.mode) { await sendNewApplication(record,currentIdentity); }
            }
        } catch (error) { /* Pendientes retenidos: volverán a intentarse con conexión/sesión. */ }
    }
    async function init(){
        if (!match) {
            // El formulario nuevo tiene su propio gestor de cola; no duplicarlo.
            if (location.pathname === rootPath+'nueva') { return; }
            window.addEventListener('online',syncFromPortal);
            document.addEventListener('visibilitychange',()=>{if(!document.hidden){syncFromPortal();}});
            if (navigator.onLine) { syncFromPortal(); }
            return;
        }
        const offlineRoot=document.getElementById('credit-offline-root');
        if(offlineRoot){
            const templates=await all('templates');
            const saved=templates.find(t=>t.key.endsWith('|'+mode+'|'+applicationId)&&
                t.key.startsWith(location.origin+'|'));
            if(!saved){offlineRoot.textContent='Para editar esta solicitud sin conexión, primero debe abrir este formulario conectado desde este dispositivo.';return;}
            identity=saved.identity;
            saved.css.forEach(url=>{const link=document.createElement('link');link.rel='stylesheet';link.href=url;document.head.appendChild(link);});
            if(saved.theme){const style=document.createElement('style');style.textContent=saved.theme;document.head.appendChild(style);}
            offlineRoot.innerHTML='<div class="credit-offline-heading"><h2>Modo sin conexión</h2><p>Los cambios y archivos se guardarán en este dispositivo hasta confirmar su recepción. No utilice un teléfono compartido.</p></div>'+saved.html;
            form=offlineRoot.querySelector('form.credit-form');
            if(form){window.creditInitPortal?.();}
        }else{
            form=document.querySelector('form.credit-form[data-credit-offline-operation]');
            if(!form){return;}
            identity=identityFromForm(form);
        }
        if(!form||!identity||!identity.user_id||!identity.company_id||!identity.website_id){return;}
        baseKey=identityKey(identity);
        key=baseKey+'|'+mode+'|'+applicationId;
        addBar();
        if(!offlineRoot){
            try{await cacheTemplate();}catch(error){banner('No se pudo preparar el formulario para abrirlo sin conexión.','error');}
        }
        const existing=await get('drafts',key);
        if(existing){restoreEntries(existing);}
        else if(!navigator.onLine){banner('Sin conexión. Al pulsar Guardar se almacenará en este dispositivo.','pending');}
        // Captura el submit ANTES de la validación del asistente. El servidor ejecuta
        // la validación definitiva al sincronizar; nunca se pierde un archivo por
        // un error de red durante la navegación normal del navegador.
        form.addEventListener('submit',event=>{
            event.preventDefault();event.stopImmediatePropagation();
            if(sending){return;}
            clearTimeout(saveTimer);
            const btn=form.querySelector('[type="submit"]');
            (async()=>{
                // Capturar primero el formulario como borrador; solo ponerlo en cola
                // si realmente falla la comunicación con Odoo.
                const record=await save(false,true);
                if(!record){return;}
                // El indicador navigator.onLine puede equivocarse. Siempre intentar
                // entregar a Odoo; pasar a pendiente solo tras un fallo de transporte.
                await send(record,false,true);
            })().catch(error=>banner('No se pudo preparar el envío: '+error.message,'error'))
                .finally(()=>{if(btn){btn.disabled=false;}});
        },true);
        const onChange=()=>{
            if(restoring){return;}
            clearTimeout(saveTimer);
            saveTimer=setTimeout(()=>save(false),750);
        };
        form.addEventListener('input',onChange);
        form.addEventListener('change',onChange);
        window.addEventListener('online',()=>syncAll());
        document.addEventListener('visibilitychange',()=>{if(!document.hidden){syncAll();}});
        window.addEventListener('offline',()=>banner('Sin conexión. Puede pulsar Guardar: los datos quedarán pendientes en este dispositivo.','pending'));
        navigator.serviceWorker?.addEventListener('message',event=>{
            if(event.data?.type==='CREDIT_OPERATION_SENT' && event.data?.key===key){
                remove('drafts',key).catch(()=>{});
                location.assign(mode==='documents'?rootPath+'historial?documentos_guardados=1':rootPath+applicationId+'?updated=1');
            }
        });
        if(navigator.onLine){syncAll();}
    }
    if(document.readyState==='loading'){document.addEventListener('DOMContentLoaded',()=>init().catch(console.error),{once:true});}
    else{init().catch(console.error);}
}());
