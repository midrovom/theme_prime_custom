const DB_NAME = "conedera-field-app";
const DB_VERSION = 1;
const STORE_META = "meta";
const STORE_PARTNERS = "partners";
const STORE_PENDING = "pending";
const STORE_VISITS = "visits";
const STORE_ORDERS = "orders";
const STORE_PRODUCTS = "products";
const STORE_CATALOG = "catalog";

const $app = document.querySelector("#app");
let db;
let installPrompt = null;
const state = {
  page: "home",
  selectedPartnerId: null,
  partners: [],
  pending: [],
  visits: [],
  orders: [],
  products: [],
  meta: null,
  catalog: { business_types: [], mobile_brands: [], teams: [] },
  search: "",
  online: navigator.onLine,
  syncing: false,
  lastError: "",
};

window.addEventListener("beforeinstallprompt", (event) => {
  event.preventDefault();
  installPrompt = event;
  if (state.page === "more") render();
});

window.addEventListener("online", async () => {
  state.online = true;
  state.lastError = "";
  render();
  await syncPending(true);
  await refreshFromServer(false);
});
window.addEventListener("offline", () => {
  state.online = false;
  render();
});

function uuid() {
  if (crypto.randomUUID) return crypto.randomUUID();
  return `${Date.now()}-${Math.random().toString(16).slice(2)}-${Math.random().toString(16).slice(2)}`;
}

function esc(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function relationName(value) {
  if (Array.isArray(value)) return value[1] || "";
  return value || "";
}
function relationId(value) {
  if (Array.isArray(value)) return value[0] || null;
  return typeof value === "number" ? value : null;
}
function money(value) {
  return new Intl.NumberFormat("es-EC", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(Number(value || 0));
}
function dateText(value) {
  if (!value) return "";
  const normalized = String(value).replace(" ", "T") + (String(value).includes("T") ? "" : "");
  const d = new Date(normalized);
  if (Number.isNaN(d.getTime())) return String(value);
  return new Intl.DateTimeFormat("es-EC", { dateStyle: "medium", timeStyle: "short" }).format(d);
}
function nowServerString() {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}
function truthy(value) { return value === true || value === "true" || value === 1 || value === "1"; }

function openDb() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = () => {
      const idb = req.result;
      if (!idb.objectStoreNames.contains(STORE_META)) idb.createObjectStore(STORE_META, { keyPath: "key" });
      if (!idb.objectStoreNames.contains(STORE_PARTNERS)) idb.createObjectStore(STORE_PARTNERS, { keyPath: "id" });
      if (!idb.objectStoreNames.contains(STORE_PENDING)) idb.createObjectStore(STORE_PENDING, { keyPath: "uuid" });
      if (!idb.objectStoreNames.contains(STORE_VISITS)) idb.createObjectStore(STORE_VISITS, { keyPath: "id" });
      if (!idb.objectStoreNames.contains(STORE_ORDERS)) idb.createObjectStore(STORE_ORDERS, { keyPath: "id" });
      if (!idb.objectStoreNames.contains(STORE_PRODUCTS)) idb.createObjectStore(STORE_PRODUCTS, { keyPath: "key" });
      if (!idb.objectStoreNames.contains(STORE_CATALOG)) idb.createObjectStore(STORE_CATALOG, { keyPath: "key" });
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

function tx(store, mode = "readonly") {
  return db.transaction(store, mode).objectStore(store);
}
function idbGetAll(store) {
  return new Promise((resolve, reject) => {
    const req = tx(store).getAll();
    req.onsuccess = () => resolve(req.result || []);
    req.onerror = () => reject(req.error);
  });
}
function idbGet(store, key) {
  return new Promise((resolve, reject) => {
    const req = tx(store).get(key);
    req.onsuccess = () => resolve(req.result || null);
    req.onerror = () => reject(req.error);
  });
}
function idbPut(store, value) {
  return new Promise((resolve, reject) => {
    const req = tx(store, "readwrite").put(value);
    req.onsuccess = () => resolve(value);
    req.onerror = () => reject(req.error);
  });
}
function idbDelete(store, key) {
  return new Promise((resolve, reject) => {
    const req = tx(store, "readwrite").delete(key);
    req.onsuccess = () => resolve();
    req.onerror = () => reject(req.error);
  });
}
function idbReplaceAll(store, values) {
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(store, "readwrite");
    const os = transaction.objectStore(store);
    os.clear();
    for (const value of values) os.put(value);
    transaction.oncomplete = () => resolve();
    transaction.onerror = () => reject(transaction.error);
  });
}

async function rpc(url, params = {}) {
  const res = await fetch(url, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ jsonrpc: "2.0", method: "call", params, id: Date.now() }),
  });
  if (!res.ok) {
    if (res.status === 401 || res.status === 403) throw new Error("Sesión vencida. Conéctese y vuelva a iniciar sesión en Odoo.");
    throw new Error(`Servidor no disponible (${res.status}).`);
  }
  const body = await res.json();
  if (body.error) throw new Error(body.error?.data?.message || body.error?.message || "Error del servidor");
  return body.result;
}

async function hydrateLocalState() {
  const [partners, pending, visits, orders, products, meta, catalog] = await Promise.all([
    idbGetAll(STORE_PARTNERS), idbGetAll(STORE_PENDING), idbGetAll(STORE_VISITS), idbGetAll(STORE_ORDERS), idbGetAll(STORE_PRODUCTS),
    idbGet(STORE_META, "bootstrap"), idbGet(STORE_CATALOG, "catalog"),
  ]);
  state.partners = partners;
  state.pending = pending.sort((a,b) => String(b.created_at).localeCompare(String(a.created_at)));
  state.visits = visits;
  state.orders = orders;
  state.products = products;
  state.meta = meta?.value || null;
  state.catalog = catalog?.value || state.catalog;
}

async function persistBootstrap(data) {
  const products = (data.products || []).map((x, idx) => ({ ...x, key: `${x.partner_id}-${x.product_id}-${idx}` }));
  await Promise.all([
    idbReplaceAll(STORE_PARTNERS, data.partners || []),
    idbReplaceAll(STORE_VISITS, data.visits || []),
    idbReplaceAll(STORE_ORDERS, data.orders || []),
    idbReplaceAll(STORE_PRODUCTS, products),
    idbPut(STORE_META, { key: "bootstrap", value: { user: data.user, capabilities: data.capabilities, server_time: data.server_time, saved_at: new Date().toISOString() } }),
    idbPut(STORE_CATALOG, { key: "catalog", value: { teams: data.teams || [], business_types: data.business_types || [], mobile_brands: data.mobile_brands || [] } }),
  ]);
}

async function refreshFromServer(showMessage = true) {
  if (!navigator.onLine || state.syncing) return;
  try {
    state.syncing = true;
    render();
    const data = await rpc("/conedera/app/bootstrap");
    await persistBootstrap(data);
    await hydrateLocalState();
    state.lastError = "";
  } catch (err) {
    state.lastError = err.message || String(err);
    if (showMessage) console.warn(err);
  } finally {
    state.syncing = false;
    render();
  }
}

function connectionBanner() {
  if (state.syncing) return `<div class="connection"><span><i class="dot"></i>Sincronizando…</span><span>${state.pending.filter(x=>x.state!=="synced").length} pendientes</span></div>`;
  if (!state.online) return `<div class="connection offline"><span><i class="dot"></i>Sin cobertura / offline</span><span>Los datos quedan en este dispositivo</span></div>`;
  if (state.lastError) return `<div class="connection error"><span><i class="dot"></i>${esc(state.lastError)}</span><button class="btn btn-outline" style="min-height:34px;padding:4px 9px" data-action="refresh">Reintentar</button></div>`;
  return `<div class="connection"><span><i class="dot"></i>En línea</span><span>${state.pending.filter(x=>x.state!=="synced").length} pendientes</span></div>`;
}

function nav(active) {
  const item = (page, icon, label) => `<button class="nav-btn ${active===page?"active":""}" data-nav="${page}"><b>${icon}</b><span>${label}</span></button>`;
  return `<nav class="bottom-nav">${item("home","⌂","Catastros")}${item("visit","＋","Visita")}${item("pending","⇅","Pendientes")}${item("more","•••","Más")}</nav>`;
}
function shell(title, body, opts={}) {
  return `<div class="app-shell">
    <header class="topbar"><div><div class="eyebrow">Catastro de Campo</div><h1>${esc(title)}</h1></div><button class="icon-btn" data-action="refresh" aria-label="Actualizar">↻</button></header>
    <main class="content">${connectionBanner()}${body}</main>
    ${opts.fab ? `<button class="fab" data-action="new-catastro" aria-label="Nuevo catastro">＋</button>` : ""}
    ${nav(opts.nav || state.page)}
  </div>`;
}

function partnerLabel(p) { return p.commercial_name || p.name || "Cliente"; }
function partnerAddress(p) { return [p.street, p.street2, p.city].filter(Boolean).join(", "); }
function partnerCompleteness(p) {
  const raw = p.census_completion_percent;
  if (typeof raw === "number") return Math.round(raw);
  return null;
}
function partnerCard(p) {
  const complete = partnerCompleteness(p);
  const locked = truthy(p.census_locked);
  return `<article class="card clickable" data-open-partner="${p.id}">
    <div class="row space"><div><div class="card-title">${esc(partnerLabel(p))}</div><div class="card-sub">${esc(p.vat || "Sin RUC/cédula")}</div></div><span style="font-size:26px;color:var(--brand)">›</span></div>
    <div class="card-sub" style="margin-top:8px">${esc(p.name || "")}${partnerAddress(p)?` · ${esc(partnerAddress(p))}`:""}</div>
    <div class="chips">${locked?'<span class="chip ok">Protegido</span>':'<span class="chip warn">Borrador</span>'}${complete!==null?`<span class="chip">${complete}% completo</span>`:""}${p.census_team_id?`<span class="chip">${esc(relationName(p.census_team_id))}</span>`:""}</div>
  </article>`;
}

function renderHome() {
  const q = state.search.trim().toLowerCase();
  const partners = state.partners.filter(p => !q || [p.name,p.commercial_name,p.vat,p.city,p.phone,p.mobile].some(v => String(v||"").toLowerCase().includes(q)));
  const body = `<input id="partner-search" class="search" placeholder="Buscar por RUC, nombre, ciudad…" value="${esc(state.search)}"/>
    <div class="cards">${partners.map(partnerCard).join("") || `<div class="empty"><b>No hay catastros en el dispositivo</b>${state.online?"Pulse actualizar o cree uno nuevo.":"Conéctese una vez para descargar sus catastros."}</div>`}</div>`;
  $app.innerHTML = shell("Mis catastros", body, { fab:true, nav:"home" });
}

function selectedPartner() { return state.partners.find(p => p.id === state.selectedPartnerId) || null; }
function visitsFor(partnerId) {
  return state.visits.filter(v => relationId(v.partner_id || v.customer_id) === partnerId).sort((a,b)=>String(b.visit_datetime||b.visit_date||b.date||b.create_date||"").localeCompare(String(a.visit_datetime||a.visit_date||a.date||a.create_date||"")));
}
function ordersFor(partnerId) {
  return state.orders.filter(o => relationId(o.commercial_partner_id || o.partner_id) === partnerId).sort((a,b)=>String(b.date_order||"").localeCompare(String(a.date_order||"")));
}
function productsFor(partnerId) { return state.products.filter(x => Number(x.partner_id) === Number(partnerId)).sort((a,b)=>Number(b.qty||0)-Number(a.qty||0)); }

function timeline(partnerId) {
  const items = [];
  for (const v of visitsFor(partnerId).slice(0,8)) items.push({date:v.visit_datetime||v.visit_date||v.date||v.create_date, title:"Visita", detail:[relationName(v.user_id||v.salesperson_id), v.state, truthy(v.purchase_made)?"Compra: Sí":""].filter(Boolean).join(" · ")});
  for (const o of ordersFor(partnerId).slice(0,8)) items.push({date:o.date_order, title:o.name||"Proforma", detail:`${relationName(o.user_id)} · ${money(o.amount_total)}`});
  items.sort((a,b)=>String(b.date||"").localeCompare(String(a.date||"")));
  if (!items.length) return `<div class="empty"><b>Sin actividad almacenada</b>Las visitas y proformas aparecerán aquí al sincronizar.</div>`;
  return `<div class="timeline">${items.slice(0,10).map(i=>`<div class="timeline-item"><strong>${esc(i.title)}</strong><div>${esc(dateText(i.date))}</div><div>${esc(i.detail)}</div></div>`).join("")}</div>`;
}

function renderDetail() {
  const p = selectedPartner();
  if (!p) { state.page="home"; return renderHome(); }
  const prod = productsFor(p.id).slice(0,8);
  const body = `<section class="card">
      <div class="row space"><div><div class="eyebrow">${esc(p.vat||"Sin identificación")}</div><div class="card-title" style="font-size:24px">${esc(partnerLabel(p))}</div><div class="card-sub">${esc(p.name||"")}</div></div></div>
      <div class="chips">${truthy(p.census_locked)?'<span class="chip ok">Protegido</span>':'<span class="chip warn">Borrador</span>'}${p.census_company_id?`<span class="chip">${esc(relationName(p.census_company_id))}</span>`:""}</div>
      <div class="metric-grid"><div class="metric"><strong>${visitsFor(p.id).length}</strong><span>Visitas almacenadas</span></div><div class="metric"><strong>${ordersFor(p.id).length}</strong><span>Proformas almacenadas</span></div></div>
    </section>
    <div class="action-grid"><button class="btn btn-primary" data-action="visit-partner" data-id="${p.id}">＋ Nueva visita</button><a class="btn btn-secondary" href="/web#id=${p.id}&model=res.partner&view_type=form">Abrir en Odoo</a></div>
    <div class="action-grid"><a class="btn btn-outline" href="/web#id=${p.id}&model=res.partner&view_type=form">Crear proforma</a>${truthy(p.census_locked)?`<a class="btn btn-outline" href="/web#id=${p.id}&model=res.partner&view_type=form">Solicitar edición</a>`:`<button class="btn btn-outline" data-action="edit-partner">Editar datos</button>`}</div>
    <div class="section-title">Contacto</div><section class="card"><div class="card-sub">${esc(p.phone||p.mobile||"Sin teléfono")}<br>${esc(p.email||"Sin email")}<br>${esc(partnerAddress(p)||"Sin dirección")}</div>${p.opening_hours_summary||p.census_opening_hours_summary?`<div style="margin-top:10px;white-space:pre-line" class="card-sub"><strong>Horario</strong><br>${esc(p.opening_hours_summary||p.census_opening_hours_summary)}</div>`:""}</section>
    <div class="section-title">Bitácora reciente</div><section class="card">${timeline(p.id)}</section>
    <div class="section-title">Productos proformados</div><section class="card">${prod.length?prod.map(x=>`<div class="product-row"><div><strong>${esc(x.product_name)}</strong><br><span>${x.lines} líneas · promedio ${money(x.avg_price)}</span></div><div style="text-align:right"><strong>${money(x.qty)}</strong><br><span>${money(x.subtotal)}</span></div></div>`).join(""):`<div class="empty">Sin productos almacenados todavía.</div>`}</section>`;
  $app.innerHTML = shell(partnerLabel(p), body, { nav:"home" });
}

function toggleHtml(name, label, value=false) {
  return `<div class="field"><label>${esc(label)}</label><div class="toggle-grid"><button type="button" class="toggle ${value===true?"active":""}" data-toggle="${name}" data-value="true">Sí</button><button type="button" class="toggle ${value===false?"active":""}" data-toggle="${name}" data-value="false">No</button></div><input type="hidden" name="${name}" value="${value?"true":"false"}"/></div>`;
}

function partnerOptions(selected) {
  return `<option value="">Seleccione cliente…</option>${state.partners.sort((a,b)=>partnerLabel(a).localeCompare(partnerLabel(b))).map(p=>`<option value="${p.id}" ${Number(selected)===p.id?"selected":""}>${esc(partnerLabel(p))} · ${esc(p.vat||"")}</option>`).join("")}`;
}
function renderVisit() {
  const selected = state.selectedPartnerId || "";
  const body = `<form id="visit-form">
    <section class="form-card"><h2>1. Cliente y resultado</h2><div class="field"><label>Catastro</label><select name="partner_id" required>${partnerOptions(selected)}</select></div>${toggleHtml("purchase_made","¿Realizó compra?",false)}${toggleHtml("has_stock","¿Tiene stock?",true)}${toggleHtml("no_credit_subject","¿No es sujeto de crédito?",false)}${toggleHtml("reschedule_visit","¿Reagendar visita?",false)}</section>
    <section class="form-card"><h2>2. Observaciones</h2><div class="field"><label>Detalle de la visita</label><textarea name="notes" placeholder="Qué encontró, acuerdos, próximos pasos…"></textarea></div><div class="field"><label>Otros / resultado adicional</label><input name="other_result" placeholder="Opcional"/></div></section>
    <section class="form-card"><h2>3. Evidencia</h2><div class="photo-box"><div id="photo-preview"></div><label class="photo-trigger">📷 Tomar foto<input id="photo-input" type="file" accept="image/*" capture="environment"/></label></div><input type="hidden" name="photo"/></section>
    <div class="sticky-actions"><button type="button" class="btn btn-secondary" data-action="save-visit-offline">Guardar offline</button><button type="submit" class="btn btn-primary">Finalizar visita</button></div>
  </form>`;
  $app.innerHTML = shell("Nueva visita", body, { nav:"visit" });
  bindPhotoInput();
}

function catalogChecks(name, items, selected=[]) {
  if (!items?.length) return `<div class="small">Se completará en Odoo cuando vuelva la conexión.</div>`;
  return `<div style="display:grid;gap:8px">${items.map(x=>`<label class="row" style="min-height:40px"><input type="checkbox" name="${name}" value="${x.id}" ${selected.includes(x.id)?"checked":""}/><span>${esc(x.name)}</span></label>`).join("")}</div>`;
}
function renderNewCatastro() {
  const body = `<form id="catastro-form">
    <section class="form-card"><h2>1. Identificación</h2><div class="field"><label>RUC / cédula *</label><input name="vat" required inputmode="numeric" autocomplete="off"/></div><div class="field"><label>Razón social / cliente *</label><input name="name" required/></div><div class="field"><label>Nombre comercial *</label><input name="commercial_name" required/></div><div class="row"><div class="field" style="flex:1"><label>Número de tiendas *</label><input name="store_count" required type="number" min="1" inputmode="numeric"/></div><div class="field" style="flex:1"><label>CAPA / compra *</label><input name="capa" required type="number" min="0" step="0.01" inputmode="decimal"/></div></div></section>
    <section class="form-card"><h2>2. Contactos</h2><div class="field"><label>Dueño / propietario</label><input name="owner_contact_name"/></div><div class="field"><label>Teléfono del dueño</label><input name="owner_phone" inputmode="tel"/></div><div class="field"><label>Contacto comercial</label><input name="commercial_contact_name"/></div><div class="field"><label>Teléfono</label><input name="phone" inputmode="tel"/></div><div class="field"><label>Móvil / WhatsApp</label><input name="mobile" inputmode="tel"/></div><div class="field"><label>Email</label><input name="email" type="email" inputmode="email"/></div></section>
    <section class="form-card"><h2>3. Ubicación</h2><div class="field"><label>Dirección</label><input name="street"/></div><div class="field"><label>Ciudad</label><input name="city"/></div><div class="field"><label>Descripción del negocio</label><textarea name="business_description"></textarea></div></section>
    <section class="form-card"><h2>4. Tipo de negocio</h2>${catalogChecks("business_type_ids",state.catalog.business_types)}</section>
    <section class="form-card"><h2>5. Marcas de celulares <span class="small">(opcional)</span></h2>${catalogChecks("mobile_brand_ids",state.catalog.mobile_brands)}</section>
    <section class="form-card"><h2>6. Horario principal</h2><div class="small" style="margin-bottom:10px">Puede registrar una franja ahora y completar horarios especiales luego en Odoo.</div><div class="row"><div class="field" style="flex:1"><label>Día</label><select name="opening_day"><option value="">Sin horario</option><option value="0">Lunes</option><option value="1">Martes</option><option value="2">Miércoles</option><option value="3">Jueves</option><option value="4">Viernes</option><option value="5">Sábado</option><option value="6">Domingo</option></select></div><div class="field" style="flex:1"><label>Desde</label><input name="opening_from" type="time" value="09:00"/></div><div class="field" style="flex:1"><label>Hasta</label><input name="opening_to" type="time" value="18:00"/></div></div></section>
    <div class="sticky-actions"><button type="button" class="btn btn-secondary" data-nav="home">Cancelar</button><button type="submit" class="btn btn-primary">Guardar en dispositivo</button></div>
  </form>`;
  $app.innerHTML = shell("Nuevo catastro", body, { nav:"home" });
}

function operationLabel(op) {
  return op.type === "visit" ? "Visita" : op.type === "catastro" ? "Nuevo catastro" : "Actualización";
}

function renderEditCatastro() {
  const p = selectedPartner();
  if (!p) { state.page="home"; return renderHome(); }
  const body = `<form id="catastro-edit-form">
    <section class="form-card"><h2>Datos del catastro</h2><div class="status-banner warn">Los cambios quedan en el dispositivo y se validan al sincronizar. Si el servidor cambió desde la última descarga, no se sobrescribe automáticamente.</div><div class="field"><label>RUC / cédula</label><input name="vat" value="${esc(p.vat||"")}"/></div><div class="field"><label>Razón social / cliente</label><input name="name" value="${esc(p.name||"")}"/></div><div class="field"><label>Nombre comercial</label><input name="commercial_name" value="${esc(p.commercial_name||"")}"/></div><div class="row"><div class="field" style="flex:1"><label>Número de tiendas</label><input name="store_count" type="number" min="1" value="${esc(p.census_store_count||p.store_count||"")}"/></div><div class="field" style="flex:1"><label>CAPA</label><input name="capa" type="number" step="0.01" value="${esc(p.capa||"")}"/></div></div></section>
    <section class="form-card"><h2>Contacto</h2><div class="field"><label>Teléfono</label><input name="phone" value="${esc(p.phone||"")}"/></div><div class="field"><label>Móvil</label><input name="mobile" value="${esc(p.mobile||"")}"/></div><div class="field"><label>Email</label><input name="email" type="email" value="${esc(p.email||"")}"/></div><div class="field"><label>Dirección</label><input name="street" value="${esc(p.street||"")}"/></div><div class="field"><label>Ciudad</label><input name="city" value="${esc(p.city||"")}"/></div></section>
    <div class="sticky-actions"><button type="button" class="btn btn-secondary" data-action="cancel-edit">Cancelar</button><button type="submit" class="btn btn-primary">Guardar offline</button></div>
  </form>`;
  $app.innerHTML = shell("Editar catastro", body, { nav:"home" });
}

async function submitCatastroUpdate(form) {
  const p = selectedPartner();
  if (!p) return;
  const obj = formObject(form);
  obj.partner_id = p.id;
  obj.base_write_date = p.write_date || "";
  obj.store_count = Number(obj.store_count || 0);
  obj.capa = Number(obj.capa || 0);
  const op = await queueOperation("catastro_update", obj, `${partnerLabel(p)} · actualización`);
  state.page = "pending";
  render();
  if (navigator.onLine) await syncPending(false, [op.uuid]);
}

function renderPending() {
  const pending = [...state.pending].sort((a,b)=>String(b.created_at).localeCompare(String(a.created_at)));
  const body = `<div class="row" style="margin-bottom:12px"><button class="btn btn-primary" style="width:100%" data-action="sync">⇅ Sincronizar ahora</button></div>
    <div class="cards">${pending.map(op=>`<section class="card pending-item"><div><div class="card-title">${esc(operationLabel(op))}</div><div class="card-sub">${esc(op.label||"")}</div><div class="chips"><span class="chip ${op.state==="error"?"danger":op.state==="conflict"?"warn":op.state==="synced"?"ok":""}">${esc(op.state||"pendiente")}</span></div>${op.message?`<div class="small ${op.state==="error"?"danger-text":""}" style="margin-top:8px">${esc(op.message)}</div>`:""}<div class="pending-meta">${esc(dateText(op.created_at))}</div></div><div><button class="icon-btn" data-delete-pending="${op.uuid}" title="Eliminar del dispositivo">×</button></div></section>`).join("") || `<div class="empty"><b>Todo sincronizado</b>No hay información pendiente en este dispositivo.</div>`}</div>`;
  $app.innerHTML = shell("Pendientes", body, { nav:"pending" });
}

function renderMore() {
  const secure = window.isSecureContext;
  const saved = state.meta?.saved_at ? dateText(state.meta.saved_at) : "Nunca";
  const canInstall = Boolean(installPrompt);
  const body = `<section class="card ${secure?"":"install-card"}"><div class="card-title">${secure?"Modo offline completo":"Modo offline limitado por HTTP"}</div><div class="card-sub" style="${secure?"":"color:rgba(255,255,255,.86)"}">${secure?"La app puede abrirse y capturar datos sin cobertura después de haber sincronizado una vez.":"Puede seguir capturando si pierde señal mientras esta pantalla permanece abierta. Para abrir la app desde cero sin Internet e instalarla como PWA, el servidor debe usar HTTPS."}</div>${canInstall?'<button class="btn" data-action="install">Instalar app</button>':""}</section>
    <section class="card"><div class="card-title">Datos del dispositivo</div><div class="card-sub">Usuario: ${esc(state.meta?.user?.name||"Sin descargar")}<br>Empresa: ${esc(state.meta?.user?.company_name||"")}<br>Última descarga: ${esc(saved)}<br>Pendientes: ${state.pending.filter(x=>x.state!=="synced").length}</div><div class="action-grid"><button class="btn btn-outline" data-action="refresh">Descargar datos</button><button class="btn btn-danger" data-action="clear-local">Borrar caché local</button></div></section>
    <section class="card"><div class="card-title">Odoo completo</div><div class="card-sub">Use Odoo para proformas, aprobaciones, reasignaciones, permisos y administración avanzada.</div><a class="btn btn-primary" style="width:100%;margin-top:12px" href="/web">Abrir Odoo</a></section>`;
  $app.innerHTML = shell("Más", body, { nav:"more" });
}

function render() {
  switch (state.page) {
    case "detail": return renderDetail();
    case "visit": return renderVisit();
    case "new": return renderNewCatastro();
    case "edit": return renderEditCatastro();
    case "pending": return renderPending();
    case "more": return renderMore();
    default: return renderHome();
  }
}

function formObject(form) {
  const data = new FormData(form);
  const obj = Object.fromEntries(data.entries());
  for (const name of ["business_type_ids", "mobile_brand_ids"]) obj[name] = data.getAll(name).map(Number);
  return obj;
}
function timeToFloat(value) {
  if (!value || !value.includes(":")) return 0;
  const [h,m] = value.split(":").map(Number);
  return h + (m/60);
}
function buildHours(obj) {
  if (obj.opening_day === "" || obj.opening_day == null) return [];
  return [{ day: obj.opening_day, from: timeToFloat(obj.opening_from), to: timeToFloat(obj.opening_to) }];
}

async function queueOperation(type, payload, label) {
  const op = { uuid: uuid(), type, payload, label, state: "pending", message: "", created_at: new Date().toISOString() };
  await idbPut(STORE_PENDING, op);
  await hydrateLocalState();
  render();
  return op;
}

async function submitCatastro(form) {
  const obj = formObject(form);
  obj.store_count = Number(obj.store_count || 0);
  obj.capa = Number(obj.capa || 0);
  obj.opening_hours = buildHours(obj);
  delete obj.opening_day; delete obj.opening_from; delete obj.opening_to;
  const op = await queueOperation("catastro", obj, `${obj.commercial_name || obj.name} · ${obj.vat}`);
  state.page = "pending";
  render();
  if (navigator.onLine) await syncPending(false, [op.uuid]);
}

async function submitVisit(form, finalize=true) {
  const obj = formObject(form);
  const partner = state.partners.find(p=>p.id===Number(obj.partner_id));
  if (!partner) { alert("Seleccione un catastro."); return; }
  for (const name of ["purchase_made","has_stock","no_credit_subject","reschedule_visit"]) obj[name] = obj[name] === "true";
  obj.partner_id = Number(obj.partner_id);
  obj.visit_datetime = nowServerString();
  obj.finalize = finalize;
  const op = await queueOperation("visit", obj, `${partnerLabel(partner)} · ${finalize?"Finalizar":"Borrador"}`);
  state.page = "pending";
  render();
  if (navigator.onLine) await syncPending(false, [op.uuid]);
}

async function syncPending(silent=false, onlyUuids=null) {
  if (!navigator.onLine || state.syncing) return;
  const candidates = state.pending.filter(x => !["synced","warning","conflict"].includes(x.state) && (!onlyUuids || onlyUuids.includes(x.uuid)));
  if (!candidates.length) return;
  try {
    state.syncing = true; render();
    const payload = candidates.map(({uuid,type,payload})=>({uuid,type,payload}));
    const response = await rpc("/conedera/app/sync", { operations: payload });
    for (const result of response.results || []) {
      const op = state.pending.find(x=>x.uuid===result.uuid);
      if (!op) continue;
      op.state = result.state;
      op.message = result.message || "";
      op.result_model = result.result_model;
      op.result_id = result.result_id;
      op.synced_at = new Date().toISOString();
      await idbPut(STORE_PENDING, op);
    }
    await hydrateLocalState();
    state.lastError = "";
    if (!silent && response.results?.some(x=>x.state==="conflict")) alert("Hay un conflicto. Revise la sección Pendientes.");
  } catch (err) {
    state.lastError = err.message || String(err);
    if (!silent) alert(state.lastError);
  } finally {
    state.syncing = false; render();
  }
  if (navigator.onLine) await refreshFromServer(false);
}

async function fileToCompressedDataUrl(file) {
  const dataUrl = await new Promise((resolve,reject)=>{ const r=new FileReader(); r.onload=()=>resolve(r.result); r.onerror=()=>reject(r.error); r.readAsDataURL(file); });
  const img = await new Promise((resolve,reject)=>{ const i=new Image(); i.onload=()=>resolve(i); i.onerror=reject; i.src=dataUrl; });
  const max = 1600;
  const scale = Math.min(1, max / Math.max(img.width,img.height));
  const canvas = document.createElement("canvas"); canvas.width=Math.max(1,Math.round(img.width*scale)); canvas.height=Math.max(1,Math.round(img.height*scale));
  canvas.getContext("2d").drawImage(img,0,0,canvas.width,canvas.height);
  return canvas.toDataURL("image/jpeg",.78);
}
function bindPhotoInput() {
  const input = document.querySelector("#photo-input");
  if (!input) return;
  input.addEventListener("change", async () => {
    const file = input.files?.[0]; if (!file) return;
    const url = await fileToCompressedDataUrl(file);
    document.querySelector('[name="photo"]').value = url;
    document.querySelector("#photo-preview").innerHTML = `<img src="${url}" alt="Foto de la visita"/>`;
    const label = input.closest("label"); if (label) label.childNodes[0].textContent = "📷 Tomar otra foto";
  });
}

async function clearLocal() {
  if (!confirm("Esto borra los datos descargados y pendientes SOLO de este dispositivo. No borra nada del servidor. ¿Continuar?")) return;
  const stores=[STORE_META,STORE_PARTNERS,STORE_PENDING,STORE_VISITS,STORE_ORDERS,STORE_PRODUCTS,STORE_CATALOG];
  await Promise.all(stores.map(store=>idbReplaceAll(store,[]).catch(async()=>{ const all=await idbGetAll(store); await Promise.all(all.map(x=>idbDelete(store,x.id||x.uuid||x.key))); })));
  await hydrateLocalState(); state.page="home"; render();
}

$app.addEventListener("input", (event) => {
  if (event.target?.id === "partner-search") { state.search = event.target.value; renderHome(); const input=document.querySelector("#partner-search"); if(input){input.focus(); input.setSelectionRange(state.search.length,state.search.length);} }
});

$app.addEventListener("click", async (event) => {
  const navEl = event.target.closest("[data-nav]");
  if (navEl) { state.page=navEl.dataset.nav; if(state.page!=="detail") state.selectedPartnerId=state.page==="visit"?state.selectedPartnerId:null; render(); return; }
  const partnerEl = event.target.closest("[data-open-partner]");
  if (partnerEl) { state.selectedPartnerId=Number(partnerEl.dataset.openPartner); state.page="detail"; render(); return; }
  const visitEl = event.target.closest("[data-action='visit-partner']");
  if (visitEl) { state.selectedPartnerId=Number(visitEl.dataset.id); state.page="visit"; render(); return; }
  const action = event.target.closest("[data-action]")?.dataset.action;
  if (action === "refresh") { await syncPending(true); await refreshFromServer(true); return; }
  if (action === "new-catastro") { state.page="new"; render(); return; }
  if (action === "edit-partner") { state.page="edit"; render(); return; }
  if (action === "cancel-edit") { state.page="detail"; render(); return; }
  if (action === "sync") { await syncPending(false); return; }
  if (action === "save-visit-offline") { const form=document.querySelector("#visit-form"); if(form) await submitVisit(form,false); return; }
  if (action === "clear-local") { await clearLocal(); return; }
  if (action === "install" && installPrompt) { installPrompt.prompt(); await installPrompt.userChoice; installPrompt=null; render(); return; }
  const del = event.target.closest("[data-delete-pending]");
  if (del) { const id=del.dataset.deletePending; const op=state.pending.find(x=>x.uuid===id); if(op?.state==="synced" || confirm("Eliminar esta operación pendiente del dispositivo?")){await idbDelete(STORE_PENDING,id); await hydrateLocalState(); render();} }
  const toggle = event.target.closest("[data-toggle]");
  if (toggle) { const name=toggle.dataset.toggle; const value=toggle.dataset.value; const form=toggle.closest("form"); form.querySelector(`[name="${name}"]`).value=value; form.querySelectorAll(`[data-toggle="${name}"]`).forEach(el=>el.classList.toggle("active",el.dataset.value===value)); }
});

$app.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (event.target.id === "catastro-form") await submitCatastro(event.target);
  if (event.target.id === "catastro-edit-form") await submitCatastroUpdate(event.target);
  if (event.target.id === "visit-form") await submitVisit(event.target,true);
});

async function init() {
  db = await openDb();
  await hydrateLocalState();
  render();
  if (window.isSecureContext && "serviceWorker" in navigator) {
    try { await navigator.serviceWorker.register("/conedera/sw.js", { scope: "/conedera/" }); } catch (err) { console.warn("Service worker no disponible", err); }
  }
  if (navigator.onLine) {
    await syncPending(true);
    await refreshFromServer(false);
  }
}

init().catch((err) => {
  console.error(err);
  $app.innerHTML = `<div class="boot-screen"><div class="boot-logo">!</div><strong>No se pudo iniciar la app</strong><span>${esc(err.message||err)}</span><a class="btn btn-primary" href="/web">Volver a Odoo</a></div>`;
});
