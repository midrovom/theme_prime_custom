const APP_VERSION = "18.0.1.5.1";
const DB_NAME = "conedera-field-app";
const DB_VERSION = 2;
const STORE_META = "meta";
const STORE_PARTNERS = "partners";
const STORE_PENDING = "pending";
const STORE_VISITS = "visits";
const STORE_ORDERS = "orders";
const STORE_PRODUCTS = "products";
const STORE_CATALOG = "catalog";
const STORE_QUOTE_PRODUCTS = "quote_products";
const STORE_QUOTE_DETAILS = "quote_details";

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
  sessionBlocked: false,
  candidateMatches: [],
  candidateSelected: null,
  lookupPending: false,
  lookupTimer: null,
  quotePartnerId: null,
  quoteLines: [],
  quoteSearch: "",
  quoteResults: [],
  quoteSearching: false,
  quoteLookupTimer: null,
  quoteProducts: [],
  quoteDetails: [],
  currentQuoteId: null,
  quoteDetail: null,
  quoteVisitId: null,
  quoteClientRef: "",
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
  // Odoo almacena Datetime en UTC, no en hora local del navegador.
  return new Date().toISOString().slice(0,19).replace("T"," ");
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
      if (!idb.objectStoreNames.contains(STORE_QUOTE_PRODUCTS)) idb.createObjectStore(STORE_QUOTE_PRODUCTS, { keyPath: "key" });
      if (!idb.objectStoreNames.contains(STORE_QUOTE_DETAILS)) idb.createObjectStore(STORE_QUOTE_DETAILS, { keyPath: "key" });
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
  const [partners, pending, visits, orders, products, meta, catalog, quoteProducts, quoteDetails] = await Promise.all([
    idbGetAll(STORE_PARTNERS), idbGetAll(STORE_PENDING), idbGetAll(STORE_VISITS), idbGetAll(STORE_ORDERS), idbGetAll(STORE_PRODUCTS),
    idbGet(STORE_META, "bootstrap"), idbGet(STORE_CATALOG, "catalog"), idbGetAll(STORE_QUOTE_PRODUCTS), idbGetAll(STORE_QUOTE_DETAILS),
  ]);
  state.partners = partners;
  state.pending = pending.sort((a,b) => String(b.created_at).localeCompare(String(a.created_at)));
  state.visits = visits;
  state.orders = orders;
  state.products = products;
  state.meta = meta?.value || null;
  state.catalog = catalog?.value || state.catalog;
  state.quoteProducts = quoteProducts;
  state.quoteDetails = quoteDetails;
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
    const data = await rpc("/catastro/app/bootstrap");
    if (state.meta?.user && (Number(state.meta.user.id)!==Number(data.user.id) || Number(state.meta.user.company_id)!==Number(data.user.company_id)) && state.pending.some(x=>!["synced","warning","conflict"].includes(x.state))) {
      state.sessionBlocked=true;
      throw new Error("Hay operaciones de otra sesión en este dispositivo. Vuelva al usuario y compañía originales para sincronizar; no se mezclaron datos.");
    }
    state.sessionBlocked=false;
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
  if (state.sessionBlocked) return `<div class="connection error">Operaciones de otra sesión: sincronización bloqueada para proteger los datos.</div>`;
  if (state.syncing) return `<div class="connection"><span><i class="dot"></i>Sincronizando…</span><span>${state.pending.filter(x=>x.state!=="synced").length} pendientes</span></div>`;
  if (!state.online) return `<div class="connection offline"><span><i class="dot"></i>Sin cobertura / offline</span><span>Los datos quedan en este dispositivo</span></div>`;
  if (state.lastError) return `<div class="connection error"><span><i class="dot"></i>${esc(state.lastError)}</span><button class="btn btn-outline" style="min-height:34px;padding:4px 9px" data-action="refresh">Reintentar</button></div>`;
  return `<div class="connection"><span><i class="dot"></i>En línea</span><span>${state.pending.filter(x=>x.state!=="synced").length} pendientes</span></div>`;
}

function nav(active, desktop=false) {
  const item = (page, icon, label) => `<button class="nav-btn ${active===page?"active":""}" data-nav="${page}"><b>${icon}</b><span>${label}</span></button>`;
  return `<nav class="${desktop?"side-nav":"bottom-nav"}" aria-label="Navegación">${item("home","⌂","Catastros")}${item("visit","＋","Visita")}${item("quote","▤","Cotizar")}${item("pending","⇅","Pendientes")}${item("more","•••","Más")}${desktop?'<a class="nav-btn" href="/web" target="_blank" rel="noopener"><b>▦</b><span>Abrir Odoo</span></a>':""}</nav>`;
}
function shell(title, body, opts={}) {
  return `<div class="app-shell">
    <aside class="desktop-sidebar"><div class="brand-lockup"><strong>CATASTRO</strong><span>App de Campo</span></div>${nav(opts.nav||state.page,true)}</aside>
    <div class="app-main"><header class="topbar"><div><div class="eyebrow">Catastro de Campo</div><h1>${esc(title)}</h1></div><div class="row"><a class="odoo-top-link" href="/web" target="_blank" rel="noopener">Odoo</a><button class="icon-btn" data-action="refresh" aria-label="Actualizar">↻</button></div></header>
    <main class="content">${connectionBanner()}${body}</main>
    ${opts.fab ? `<button class="fab" data-action="new-catastro" aria-label="Nuevo catastro">＋</button>` : ""}
    ${nav(opts.nav || state.page)}</div>
  </div>`;
}

function partnerLabel(p) { return p.commercial_name || p.name || "Cliente"; }
function partnerAddress(p) { return [p.street, p.street2, p.city].filter(Boolean).join(", "); }
function partnerCompleteness(p) {
  const raw = p.census_completion_pct ?? p.census_completion_percent;
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
  const protectedCount=state.partners.filter(p=>truthy(p.census_locked)).length;
  const quoteShortcut=`<section class="quote-hero" aria-label="Acceso directo a cotizaciones">
      <div class="quote-hero-copy"><span class="quote-hero-eyebrow">VENTAS · COTIZACIONES</span><h2>Crea una cotización</h2>
      <p>Accede al cotizador desde aquí, sin buscar el botón entre los catastros. ${protectedCount?`${protectedCount} catastro(s) protegido(s) disponible(s).`:"Primero finaliza y protege un catastro para crear el borrador."}</p></div>
      <div class="quote-hero-actions"><button type="button" class="btn quote-hero-button" data-action="open-quote"><span aria-hidden="true">▤</span> Cotizar ahora</button><a class="quote-hero-native" href="${nativeQuotationsUrl()}" target="_blank" rel="noopener">Cotización completa (Odoo)</a></div>
    </section>`;
  const body = `${quoteShortcut}<div class="home-tools"><span>Mis clientes</span><button type="button" class="btn btn-outline" data-action="new-catastro">＋ Nuevo catastro</button></div>
    <input id="partner-search" class="search" placeholder="Buscar por RUC, nombre, ciudad…" value="${esc(state.search)}"/>
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

function unlockStateLabel(value) {
  return ({pending:"Solicitud pendiente",approved:"Solicitud aprobada",rejected:"Solicitud rechazada",expired:"Autorización vencida"})[value] || "Sin solicitudes";
}
function detailWorkflow(p) {
  const locked = truthy(p.census_locked);
  const canEdit = truthy(p.census_can_edit_master);
  const stateLabel = p.census_latest_unlock_state;
  const status = locked ? `La ficha está protegida. Solo se puede modificar con autorización.` : `Borrador. Para registrar visitas debe completar y proteger la ficha.`;
  let html = `<section class="card workflow-card"><div class="row space"><div><div class="card-title">Estado del catastro</div><div class="card-sub">${esc(status)}</div></div><span class="chip ${locked?"ok":"warn"}">${locked?"Protegido":"Borrador"}</span></div>`;
  if (!locked) {
    html += `<div class="progress-track"><span style="width:${Math.max(0,Math.min(100,partnerCompleteness(p)||0))}%"></span></div>`;
    if (p.census_missing_requirements) html+=`<div class="small" style="margin:10px 0">Pendiente: ${esc(p.census_missing_requirements)}</div>`;
    html += `<div class="action-grid"><button class="btn btn-secondary" data-action="edit-partner" ${canEdit?"":"disabled"}>Editar borrador</button><button class="btn btn-primary" data-action="finalize-partner">✓ Finalizar y proteger</button></div>`;
  } else {
    html += `<div class="status-banner ${stateLabel==="rejected"?"warn":""}" style="margin-top:12px"><strong>${esc(unlockStateLabel(stateLabel))}</strong>`;
    if (stateLabel==="approved" && p.census_latest_unlock_valid_until) html+=`<div class="small">Válida hasta ${esc(dateText(p.census_latest_unlock_valid_until))}</div>`;
    if (stateLabel==="rejected" && p.census_latest_unlock_review_note) html+=`<div>Motivo del rechazo: ${esc(p.census_latest_unlock_review_note)}</div>`;
    html += `</div>`;
    const isResponsible = relationId(p.user_id) === Number(state.meta?.user?.id);
    html += `<div class="action-grid">${canEdit?`<button class="btn btn-primary" data-action="edit-partner">Editar datos</button>${p.census_edit_state==="enabled"?'<button class="btn btn-secondary" data-action="finish-edit">Finalizar edición</button>':""}`:isResponsible?`<button class="btn btn-primary" data-action="show-unlock-form" ${stateLabel==="pending"?"disabled":""}>Solicitar habilitación</button>`:'<span class="small">Solo el responsable puede solicitar edición.</span>'}<button class="btn btn-outline" data-action="refresh-status">↻ Estado de solicitud</button></div>`;
    if (!canEdit && isResponsible) html += `<form id="unlock-form" class="unlock-form" hidden><div class="field"><label>Motivo de la solicitud de edición *</label><textarea name="reason" required minlength="5" maxlength="2000" placeholder="Indique qué necesita corregir y por qué"></textarea></div><div class="row"><button class="btn btn-primary" type="submit">Enviar solicitud</button><button class="btn btn-secondary" type="button" data-action="hide-unlock-form">Cancelar</button></div></form>`;
  }
  return html+`</section>`;
}
function formatTimeFloat(value) {
  const n=Number(value||0), h=Math.floor(n),m=Math.round((n-h)*60);
  return `${String(h+Math.floor(m/60)).padStart(2,"0")}:${String(m%60).padStart(2,"0")}`;
}
const DAYS=["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"];
function hoursSummary(p) {
  if (!p.opening_hours?.length) return `<div class="small">Aún no se ha registrado un horario.</div>`;
  return `<div class="hours-summary">${p.opening_hours.map(h=>`<div><strong>${esc(DAYS[Number(h.day)]||"Día")}</strong><span>${esc(formatTimeFloat(h.from))}–${esc(formatTimeFloat(h.to))}</span></div>`).join("")}</div>`;
}
function renderDetail() {
  const p = selectedPartner();
  if (!p) { state.page="home"; return renderHome(); }
  const prod = productsFor(p.id).slice(0,8);
  const locked=truthy(p.census_locked);
  const body = `<div class="detail-layout"><div class="detail-primary"><section class="card">
      <div class="row space"><div><div class="eyebrow">${esc(p.vat||"Sin identificación")}</div><div class="card-title" style="font-size:24px">${esc(partnerLabel(p))}</div><div class="card-sub">${esc(p.name||"")}</div></div></div>
      <div class="chips">${locked?'<span class="chip ok">Protegido</span>':'<span class="chip warn">Borrador</span>'}${p.census_company_id?`<span class="chip">${esc(relationName(p.census_company_id))}</span>`:""}</div>
      <div class="metric-grid"><div class="metric"><strong>${visitsFor(p.id).length}</strong><span>Visitas registradas</span></div><div class="metric"><strong>${ordersFor(p.id).length}</strong><span>Proformas</span></div></div>
    </section>
    ${detailWorkflow(p)}
    <div class="section-title">Operación comercial</div><div class="action-grid"><button class="btn btn-primary" data-action="visit-partner" data-id="${p.id}" ${locked?"":"disabled"}>＋ Nueva visita</button><button class="btn btn-secondary" data-action="quote-partner" data-id="${p.id}">▤ Cotizar ${locked?"ahora":"(requiere cierre)"}</button><a class="btn btn-outline" href="/web#id=${p.id}&model=res.partner&view_type=form" target="_blank" rel="noopener">Abrir en Odoo</a></div>
    <div class="section-title">Bitácora reciente</div><section class="card">${timeline(p.id)}</section></div>
    <div class="detail-secondary"><div class="section-title">Contacto</div><section class="card"><div class="card-sub">${esc(p.phone||p.mobile||"Sin teléfono")}<br>${esc(p.email||"Sin email")}<br>${esc(partnerAddress(p)||"Sin dirección")}</div><div class="section-title">Horario de atención</div>${hoursSummary(p)}</section>
    <div class="section-title">Productos proformados</div><section class="card">${prod.length?prod.map(x=>`<div class="product-row"><div><strong>${esc(x.product_name)}</strong><br><span>${x.lines} líneas · promedio ${money(x.avg_price)}</span></div><div style="text-align:right"><strong>${money(x.qty)}</strong><br><span>${money(x.subtotal)}</span></div></div>`).join(""):`<div class="empty">Sin productos almacenados todavía.</div>`}</section></div></div>`;
  $app.innerHTML = shell(partnerLabel(p), body, {nav:"home"});
}

function quoteCanCreate() {
  return Boolean(state.meta?.capabilities?.quote_create);
}
function quotePartner() { return state.partners.find(p=>p.id===Number(state.quotePartnerId))||null; }
function nativeQuotationsUrl() {
  const action=Number(state.meta?.capabilities?.sales_action_id||0);
  return action>0?`/web#action=${action}&model=sale.order&view_type=list`:'/web';
}
function availableQuoteProducts(term) {
  const user=state.meta?.user;
  if (!user) return [];
  const q=String(term||"").trim().toLowerCase();
  return state.quoteProducts.filter(p=>Number(p.user_id)===Number(user.id) && Number(p.company_id)===Number(user.company_id)
    && [p.name,p.code].some(x=>String(x||"").toLowerCase().includes(q))).slice(0,25);
}
function renderQuoteResults() {
  const box=document.querySelector("#quote-search-results"); if (!box) return;
  const found=state.quoteResults;
  box.innerHTML=state.quoteSearching?'<div class="small">Buscando en Odoo…</div>':
    !state.quoteSearch.trim()?'<div class="small">Escriba el nombre o código del producto.</div>':
    found.length?found.map(p=>`<button class="quote-pick" type="button" data-action="quote-add-product" data-id="${p.id}"><span><strong>${esc(p.name)}</strong><small>${esc(p.code||p.uom||"")}</small></span><b>＋ Agregar</b></button>`).join(""):
    `<div class="small">No se encontraron productos ${state.online?"disponibles":"guardados para uso offline"}.</div>`;
}
function quoteLinesMarkup() {
  return state.quoteLines.length?state.quoteLines.map((line,i)=>`<div class="quote-line" data-quote-line="${line.id}">
    <div class="quote-line-name"><strong>${esc(line.name)}</strong><span>${esc(line.code||line.uom||"")}</span></div>
    <div class="quote-line-controls"><label>Cantidad<input type="number" inputmode="decimal" min="0.001" max="100000" step="any" value="${esc(line.qty)}" data-quote-qty="${line.id}" required/></label>
    <button type="button" class="icon-btn quote-remove" title="Quitar producto" aria-label="Quitar ${esc(line.name)}" data-action="quote-remove-product" data-id="${line.id}">×</button></div></div>`).join(""):
    `<div class="empty"><b>Sin productos</b>Busca un producto y agrégalo a la cotización.</div>`;
}
function renderQuote() {
  const partner=quotePartner();
  const cap=state.meta?.capabilities||{};
  const clients=state.partners.filter(p=>truthy(p.census_locked) && (!p.census_company_id || relationId(p.census_company_id)===Number(state.meta?.user?.company_id)));
  const related=partner?ordersFor(partner.id).slice(0,10):[];
  const linkedVisits=partner?visitsFor(partner.id).filter(v=>v.state==="done"):[];
  const availabilityNote=clients.length?"":`<div class="status-banner warn">No hay catastros protegidos de la compañía actual para cotizar. Abre un catastro, completa los datos obligatorios y pulsa «Finalizar y proteger» antes de crear una cotización.</div>`;
  const permissionNote=cap.quote_create===false?`<div class="status-banner warn">Tu usuario no tiene permiso para crear cotizaciones en Odoo. Solicita al administrador los permisos correspondientes de Ventas. El acceso a esta pantalla sigue visible para que puedas identificar la causa.</div>`:"";
  const body=`${availabilityNote}${permissionNote}<div class="quote-layout"><form id="quote-form">
    <section class="form-card"><div class="row space"><h2>1. Cliente</h2><span class="chip">Empresa: ${esc(state.meta?.user?.company_name||"")}</span></div>
      <div class="field"><label>Catastro protegido *</label><select name="partner_id" required><option value="">Seleccione un cliente…</option>${clients.map(p=>`<option value="${p.id}" ${partner?.id===p.id?"selected":""}>${esc(partnerLabel(p))} · ${esc(p.vat||"")}</option>`).join("")}</select></div>
      <div class="field"><label>Vincular con visita (opcional)</label><select name="visit_id"><option value="">Sin visita asociada</option>${linkedVisits.map(v=>`<option value="${v.id}" ${Number(state.quoteVisitId)===v.id?"selected":""}>${esc(v.name||"Visita #"+v.id)} · ${esc(dateText(v.visit_datetime||v.visit_date||v.create_date))}</option>`).join("")}</select></div>
    </section>
    <section class="quote-mode-banner"><div><strong>Cotización rápida desde la PWA</strong><p>Este formulario genera borradores. Para utilizar condiciones comerciales, campos especiales y todas las personalizaciones, abre la pantalla nativa de cotizaciones.</p></div><a class="btn btn-outline" href="${nativeQuotationsUrl()}" target="_blank" rel="noopener" aria-label="Abrir cotizaciones completas en Odoo">Cotización completa en Odoo</a></section>
    <section class="form-card"><h2>2. Productos y cantidades</h2><div class="field"><label>Buscar por nombre o código</label><input id="quote-search" value="${esc(state.quoteSearch)}" placeholder="Ej. producto, código SKU" autocomplete="off" ${partner?"":"disabled"}/></div>
      <div id="quote-search-results" class="quote-results" aria-live="polite"></div><div class="quote-lines-head"><strong>Productos agregados (${state.quoteLines.length})</strong></div><div id="quote-lines">${quoteLinesMarkup()}</div>
      <div class="small">Los precios, descuentos automáticos e impuestos se calcularán en Odoo al guardar. No se fijan importes desde la PWA.</div>
    </section><section class="form-card"><h2>3. Referencia</h2><div class="field"><label>Referencia del cliente (opcional)</label><input name="client_order_ref" maxlength="100" value="${esc(state.quoteClientRef)}" placeholder="Orden de compra o referencia externa"/></div>
      <div class="status-banner warn">La cotización se guardará como <b>borrador</b>. Revise los importes definitivos antes de enviarla o confirmarla.</div></section>
      <div class="sticky-actions quote-submit"><button class="btn btn-outline" type="button" data-nav="home">Volver</button><button class="btn btn-primary" type="submit" ${!cap.quote_create?"disabled":""}>▤ Guardar cotización${state.online?"":" offline"}</button></div>
    </form><aside class="quote-side"><section class="card"><div class="card-title">Cotizaciones del cliente</div><div class="card-sub">Historial visible según permisos de Odoo</div>
      ${related.length?related.map(o=>`<button class="quote-history" type="button" data-action="view-quote" data-id="${o.id}"><span><strong>${esc(o.name)}</strong><small>${esc(dateText(o.date_order))} · ${esc(o.state||"")}</small></span><b>${esc(relationName(o.currency_id)||"")} ${money(o.amount_total)}</b></button>`).join(""):'<div class="small" style="margin-top:10px">Seleccione un cliente para consultar sus proformas.</div>'}</section></aside></div>`;
  $app.innerHTML=shell("Cotizaciones",body,{nav:"quote"});renderQuoteResults();
}
function renderQuoteDetail() {
  const q=state.quoteDetail;
  if (!q) {state.page="quote";return renderQuote();}
  const body=`<div class="quote-layout"><section class="form-card"><div class="row space"><div><div class="eyebrow">Cotización</div><h2>${esc(q.name)}</h2><div class="card-sub">${esc(q.partner_name)} · ${esc(q.company_name)} · ${esc(dateText(q.date_order))}</div></div><span class="chip">${esc(q.state)}</span></div>
    <div class="section-title">Detalle de productos</div>${q.lines.map(l=>`<div class="quote-detail-line"><div><strong>${esc(l.product_name||l.name)}</strong><div class="small">${esc(l.qty)} ${esc(l.uom)} × ${esc(q.currency)} ${money(l.price_unit)}${l.discount?` · descuento ${esc(l.discount)}%`:""}</div></div><strong>${esc(q.currency)} ${money(l.subtotal)}</strong></div>`).join("")}
    <div class="quote-total"><div><span>Subtotal</span><strong>${esc(q.currency)} ${money(q.amount_untaxed)}</strong></div><div><span>Impuestos</span><strong>${esc(q.currency)} ${money(q.amount_tax)}</strong></div><div class="grand"><span>Total</span><strong>${esc(q.currency)} ${money(q.amount_total)}</strong></div></div>
    <div class="status-banner warn">Importes suministrados por Odoo. Antes de enviar, verifique condiciones comerciales y personalizaciones de su instalación.</div>
    <div class="action-grid"><button class="btn btn-secondary" data-action="back-quote">← Cotizaciones</button><a class="btn btn-primary" href="/web#id=${Number(q.id)}&model=sale.order&view_type=form" target="_blank" rel="noopener">Abrir en Odoo</a></div></section>
    <aside class="quote-side"><section class="card"><div class="card-title">Registro</div><div class="card-sub">Referencia: ${esc(q.client_order_ref||"—")}<br>Visita: ${q.visit_id?"#"+Number(q.visit_id):"No asociada"}<br>Empresa: ${esc(q.company_name)}</div></section></aside></div>`;
  $app.innerHTML=shell(q.name,body,{nav:"quote"});
}
async function openQuote(id) {
  if (!id) return;
  const user=state.meta?.user||{};
  const key=`${user.id}:${user.company_id}:${id}`;
  const cached=state.quoteDetails.find(x=>x.key===key);
  state.currentQuoteId=id;
  if (cached) {state.quoteDetail=cached.value;state.page="quote-detail";render();}
  if (!navigator.onLine) {
    if (!cached) alert("Conéctese una vez para descargar el detalle de esta cotización.");
    return;
  }
  try {
    const quote=await rpc("/catastro/app/quote/read",{quote_id:id});
    await idbPut(STORE_QUOTE_DETAILS,{key,value:quote});
    state.quoteDetail=quote;state.page="quote-detail";render();
  } catch(err){alert(err.message||String(err));}
}
async function searchQuoteProducts(value) {
  const term=String(value||"").trim();state.quoteSearch=value;
  if (term.length<2) {state.quoteResults=[];state.quoteSearching=false;renderQuoteResults();return;}
  state.quoteResults=availableQuoteProducts(term);state.quoteSearching=state.online;renderQuoteResults();
  if (!state.online || !state.quotePartnerId){state.quoteSearching=false;renderQuoteResults();return;}
  try {
    const result=await rpc("/catastro/app/quote/products",{term,partner_id:state.quotePartnerId});
    if (!document.querySelector("#quote-search") || document.querySelector("#quote-search").value.trim()!==term) return;
    const user=state.meta?.user||{};
    for (const p of result) await idbPut(STORE_QUOTE_PRODUCTS,{...p,key:`${user.id}:${user.company_id}:${p.id}`,user_id:user.id,company_id:user.company_id});
    state.quoteProducts=await idbGetAll(STORE_QUOTE_PRODUCTS);
    state.quoteResults=result;
  } catch(err){state.quoteResults=availableQuoteProducts(term);state.lastError=err.message||String(err);}
  state.quoteSearching=false;renderQuoteResults();
}
async function submitQuote(form) {
  const p=quotePartner();
  if (!p||!truthy(p.census_locked)) {alert("Seleccione un catastro finalizado y protegido.");return;}
  if (!state.quoteLines.length){alert("Agregue al menos un producto.");return;}
  const lines=state.quoteLines.map(x=>({product_id:Number(x.id),qty:Number(x.qty)}));
  if(lines.some(x=>!Number.isInteger(x.product_id)||!Number.isFinite(x.qty)||x.qty<=0||x.qty>100000)) {alert("Revise las cantidades de los productos.");return;}
  if (!state.meta?.user?.id) {alert("Sin sesión descargada. Conéctese para empezar.");return;}
  if (state.online && !quoteCanCreate()){alert("Su usuario necesita permiso para crear cotizaciones en Ventas.");return;}
  if (!confirm(`¿Guardar una cotización en borrador para ${partnerLabel(p)} con ${lines.length} producto(s)? Los precios se calcularán al sincronizar.`))return;
  const payload={partner_id:p.id,visit_id:Number(form.querySelector('[name="visit_id"]')?.value||0),lines,
    client_order_ref:form.querySelector('[name="client_order_ref"]')?.value.trim()||""};
  const op=await queueOperation("quote",payload,`${partnerLabel(p)} · cotización de ${lines.length} productos`);
  state.quoteLines=[];state.quoteSearch="";state.quoteResults=[];state.quoteVisitId=null;state.quoteClientRef="";
  state.page="pending";render();
  if(navigator.onLine){
    await syncPending(false,[op.uuid]);
    const updated=state.pending.find(x=>x.uuid===op.uuid);
    if(updated?.state==="synced"&&updated.result_model==="sale.order")await openQuote(updated.result_id);
  }
}

function toggleHtml(name, label, value=false) {
  return `<div class="field"><label>${esc(label)}</label><div class="toggle-grid"><button type="button" class="toggle ${value===true?"active":""}" data-toggle="${name}" data-value="true">Sí</button><button type="button" class="toggle ${value===false?"active":""}" data-toggle="${name}" data-value="false">No</button></div><input type="hidden" name="${name}" value="${value?"true":"false"}"/></div>`;
}

function partnerOptions(selected) {
  return `<option value="">Seleccione cliente protegido…</option>${state.partners.filter(p=>truthy(p.census_locked)).sort((a,b)=>partnerLabel(a).localeCompare(partnerLabel(b))).map(p=>`<option value="${p.id}" ${Number(selected)===p.id?"selected":""}>${esc(partnerLabel(p))} · ${esc(p.vat||"")}</option>`).join("")}`;
}
function renderVisit() {
  const selected = truthy(selectedPartner()?.census_locked)?state.selectedPartnerId:"";
  const body = `<form id="visit-form">
    <section class="form-card"><h2>1. Cliente y resultado</h2><div class="field"><label>Catastro</label><select name="partner_id" required>${partnerOptions(selected)}</select></div>${toggleHtml("purchase_made","¿Realizó compra?",false)}${toggleHtml("has_stock","¿Tiene stock?",true)}${toggleHtml("not_creditworthy","¿No es sujeto de crédito?",false)}${toggleHtml("reschedule_visit","¿Reagendar visita?",false)}${toggleHtml("other_result","¿Otros resultados?",false)}<div class="field"><label>Detalle de otro resultado (si aplica)</label><input name="other_result_detail"/></div><div class="field"><label>Fecha de próxima visita (si reagenda)</label><input name="next_visit_datetime" type="datetime-local"/></div></section>
    <section class="form-card"><h2>2. Observaciones</h2><div class="field"><label>Detalle de la visita</label><textarea name="notes" placeholder="Qué encontró, acuerdos, próximos pasos…"></textarea></div></section>
    <section class="form-card"><h2>3. Evidencia</h2><div class="row" style="margin-bottom:12px"><button type="button" class="btn btn-secondary" data-action="capture-gps">⌖ Capturar ubicación GPS</button><span data-gps-preview class="small">Ubicación opcional</span></div><input type="hidden" name="gps_capture_payload"/><div class="photo-box"><div id="photo-preview"></div><label class="photo-trigger">📷 Tomar foto<input id="photo-input" type="file" accept="image/*" capture="environment"/></label></div><input type="hidden" name="photo"/></section>
    <div class="sticky-actions"><button type="button" class="btn btn-secondary" data-action="save-visit-offline">Guardar offline</button><button type="submit" class="btn btn-primary">Finalizar visita</button></div>
  </form>`;
  $app.innerHTML = shell("Nueva visita", body, { nav:"visit" });
  bindPhotoInput();
}

function catalogChecks(name, items, selected=[]) {
  if (!items?.length) return `<div class="small">${name==="business_type_ids"?"Descargue el catálogo con conexión para seleccionar tipos de negocio.":"Sin marcas disponibles en el catálogo descargado."}</div>`;
  return `<div style="display:grid;gap:8px">${items.map(x=>`<label class="row" style="min-height:40px"><input type="checkbox" name="${name}" value="${x.id}" ${selected.includes(x.id)?"checked":""}/><span>${esc(x.name)}</span></label>`).join("")}</div>`;
}
function hourRow(day="0", begin="09:00", end="18:00") {
  return `<div class="hour-row" data-hour-row><div class="field"><label>Día</label><select data-hour-day>${DAYS.map((d,i)=>`<option value="${i}" ${String(i)===String(day)?"selected":""}>${esc(d)}</option>`).join("")}</select></div><div class="field"><label>Desde</label><input data-hour-from type="time" value="${esc(begin)}" /></div><div class="field"><label>Hasta</label><input data-hour-to type="time" value="${esc(end)}" /></div><button class="icon-btn remove-hour" type="button" data-action="remove-hour" aria-label="Eliminar horario">×</button></div>`;
}
function hoursEditor(hours=[]) {
  return `<section class="form-card"><div class="row space"><h2>Horario de atención</h2><button type="button" class="btn btn-outline" data-action="add-hour">＋ Agregar horario</button></div><div class="small" style="margin-bottom:10px">Puede registrar varias franjas por día. Para finalizar, se necesita al menos una.</div><div id="hours-list">${hours.length?hours.map(h=>hourRow(h.day,formatTimeFloat(h.from),formatTimeFloat(h.to))).join(""):hourRow()}</div></section>`;
}
function selectOptions(name, choices, selected="") {
  return `<div class="field"><label>${esc(name)}</label><select name="customer_segment"><option value="">Seleccione el canal comercial…</option>${choices.map(x=>`<option value="${x[0]}" ${x[0]===selected?"selected":""}>${esc(x[1])}</option>`).join("")}</select></div>`;
}
function renderNewCatastro() {
  state.candidateSelected = null;
  state.candidateMatches=[];
  const body = `<form id="catastro-form" novalidate>
    <section class="form-card"><h2>1. Identificación y búsqueda de cliente</h2><div class="field"><label>Buscar por nombre, cédula o RUC</label><input id="lookup-field" name="lookup_query" autocomplete="off" placeholder="Empiece a escribir para ver coincidencias" /></div><div id="lookup-results" role="status" aria-live="polite" class="lookup-results"></div><input type="hidden" name="selected_partner_id" value=""/><div class="field"><label>RUC / cédula *</label><input name="vat" autocomplete="off" inputmode="numeric"/></div><div class="field"><label>Razón social / cliente *</label><input name="name"/></div><div class="field"><label>Nombre comercial / local *</label><input name="commercial_name"/></div><div class="field"><label>Número de tiendas *</label><input name="store_count" type="number" min="0" inputmode="numeric"/></div><div class="field"><label>CAPA / capacidad de compra *</label><input name="capa" type="number" step="0.01" min="0" inputmode="decimal"/></div></section>
    <section class="form-card"><h2>2. Contactos *</h2><div class="field"><label>Nombre del dueño</label><input name="owner_contact_name"/></div><div class="field"><label>Teléfono del dueño</label><input name="owner_phone" inputmode="tel"/></div><div class="field"><label>Contacto comercial</label><input name="commercial_contact_name"/></div><div class="field"><label>Teléfono</label><input name="phone" inputmode="tel"/></div><div class="field"><label>Móvil / WhatsApp</label><input name="mobile" inputmode="tel"/></div><div class="field"><label>Email</label><input name="email" type="email" inputmode="email"/></div></section>
    <section class="form-card"><h2>3. Ubicación *</h2><div class="field"><label>Dirección</label><input name="street"/></div><div class="field"><label>Ciudad</label><input name="city"/></div><div class="field"><label>Especialidad / detalle</label><textarea name="business_description"></textarea></div><div class="row"><button type="button" class="btn btn-secondary" data-action="capture-gps">⌖ Capturar GPS del local</button><span data-gps-preview class="small">Opcional · requiere HTTPS</span></div><input type="hidden" name="census_gps_payload"/></section>
    <section class="form-card"><h2>4. Clasificación *</h2><div class="field"><label>Equipo comercial</label><select name="team_id"><option value="">Asignación automática</option>${state.catalog.teams.filter(t=>!relationId(t.company_id)||relationId(t.company_id)===state.meta?.user?.company_id).map(t=>`<option value="${t.id}" ${t.id===state.meta?.user?.team_id?"selected":""}>${esc(t.name)}</option>`).join("")}</select></div>${selectOptions("Canal comercial",[["wholesaler","Mayorista"],["reseller","Revendedor / distribuidor"],["retail","Tienda al detalle"],["mixed","Mixto"],["other","Otro"]])}<div class="field"><label>Tipo(s) de negocio</label>${catalogChecks("business_type_ids",state.catalog.business_types)}</div><h2>Marcas de celulares <span class="small">(opcional)</span></h2>${catalogChecks("mobile_brand_ids",state.catalog.mobile_brands)}</section>
    ${hoursEditor()}
    <div id="form-validation" role="alert"></div>
    <div class="sticky-actions"><button type="submit" name="save_mode" value="draft" class="btn btn-secondary">Guardar borrador</button><button type="submit" name="save_mode" value="finalize" class="btn btn-primary">✓ Finalizar y proteger</button></div>
  </form>`;
  $app.innerHTML = shell("Nuevo catastro", body, {nav:"home"});
}

function operationLabel(op) {
  return op.type === "quote" ? "Cotización / Proforma" : op.type === "visit" ? "Visita" : op.type === "catastro" ? (op.payload?.finalize?"Nuevo catastro · finalizar":"Nuevo catastro · borrador") : op.type === "catastro_finalize"?"Finalizar y proteger":"Actualización";
}

function renderEditCatastro() {
  const p = selectedPartner();
  if (!p) { state.page="home"; return renderHome(); }
  if (!truthy(p.census_can_edit_master)) { state.page="detail"; return renderDetail(); }
  const val=(name)=>esc(p[name]||"");
  const body = `<form id="catastro-edit-form" novalidate>
    <section class="form-card"><h2>Datos del catastro</h2><div class="status-banner warn">Los cambios se validan en Odoo al sincronizar. Si la autorización vence, no se aplicarán modificaciones protegidas.</div><div class="field"><label>RUC / cédula</label><input name="vat" value="${val("vat")}"/></div><div class="field"><label>Razón social / cliente</label><input name="name" value="${val("name")}"/></div><div class="field"><label>Nombre comercial</label><input name="commercial_name" value="${val("commercial_name")}"/></div><div class="row"><div class="field" style="flex:1"><label>Número de tiendas</label><input name="store_count" type="number" min="0" value="${p.census_store_count||0}"/></div><div class="field" style="flex:1"><label>CAPA</label><input name="capa" type="number" min="0" step="0.01" value="${p.capa||0}"/></div></div></section>
    <section class="form-card"><h2>Contacto</h2>${["owner_contact_name","owner_phone","commercial_contact_name","phone","mobile","email","street","city","business_description"].map(name=>`<div class="field"><label>${esc(({owner_contact_name:"Dueño",owner_phone:"Teléfono del dueño",commercial_contact_name:"Contacto comercial",phone:"Teléfono",mobile:"Móvil",email:"Email",street:"Dirección",city:"Ciudad",business_description:"Especialidad"})[name])}</label><input name="${name}" value="${val(name)}"/></div>`).join("")}</section>
    <section class="form-card"><div class="row"><button type="button" class="btn btn-secondary" data-action="capture-gps">⌖ Actualizar GPS del local</button><span data-gps-preview class="small">Opcional</span></div><input type="hidden" name="census_gps_payload"/></section><section class="form-card"><h2>Clasificación comercial</h2>${selectOptions("Canal comercial",[["wholesaler","Mayorista"],["reseller","Revendedor"],["retail","Detalle"],["mixed","Mixto"],["other","Otro"]],p.customer_segment||"")}<div class="field"><label>Tipos de negocio</label>${catalogChecks("business_type_ids",state.catalog.business_types,p.business_type_ids||[])}</div><div class="field"><label>Marcas de celulares</label>${catalogChecks("mobile_brand_ids",state.catalog.mobile_brands,p.mobile_brand_ids||[])}</div></section>
    ${hoursEditor(p.opening_hours||[])}<div id="form-validation" role="alert"></div>
    <div class="sticky-actions"><button type="button" class="btn btn-secondary" data-action="cancel-edit">Cancelar</button><button type="submit" class="btn btn-primary">Guardar cambios</button></div>
  </form>`;
  $app.innerHTML = shell("Editar catastro", body, {nav:"home"});
}
async function submitCatastroUpdate(form) {
  const p = selectedPartner();
  if (!p) return;
  const obj = formObject(form);
  if (!state.catalog.business_types?.length) delete obj.business_type_ids;
  if (!state.catalog.mobile_brands?.length) delete obj.mobile_brand_ids;
  try { obj.opening_hours=buildHours(form); } catch(err) { showFormError(err.message); return; }
  obj.partner_id = p.id;
  obj.base_write_date = p.write_date || "";
  obj.store_count = Number(obj.store_count || 0);
  obj.capa = Number(obj.capa || 0);
  const op = await queueOperation("catastro_update", obj, `${partnerLabel(p)} · actualización`);
  state.page = "pending"; render();
  if (navigator.onLine) await syncPending(false, [op.uuid]);
}

function renderPending() {
  const pending = [...state.pending].sort((a,b)=>String(b.created_at).localeCompare(String(a.created_at)));
  const body = `<div class="row" style="margin-bottom:12px"><button class="btn btn-primary" style="width:100%" data-action="sync">⇅ Sincronizar ahora</button></div>
    <div class="cards">${pending.map(op=>`<section class="card pending-item"><div><div class="card-title">${esc(operationLabel(op))}</div><div class="card-sub">${esc(op.label||"")}</div><div class="chips"><span class="chip ${op.state==="error"?"danger":op.state==="conflict"?"warn":op.state==="synced"?"ok":""}">${esc(op.state||"pendiente")}</span></div>${op.message?`<div class="small ${op.state==="error"?"danger-text":""}" style="margin-top:8px">${esc(op.message)}</div>`:""}${op.result_model==="res.partner" && op.result_id && ["synced","warning"].includes(op.state)?`<button class="btn btn-outline" style="margin-top:10px" data-action="open-result" data-id="${op.result_id}">Ver catastro</button>`:""}${op.result_model==="sale.order" && op.result_id && op.state==="synced"?`<button class="btn btn-outline" style="margin-top:10px" data-action="open-quote-result" data-id="${op.result_id}">Ver cotización</button>`:""}<div class="pending-meta">${esc(dateText(op.created_at))}</div></div><div><button class="icon-btn" data-delete-pending="${op.uuid}" title="Eliminar del dispositivo">×</button></div></section>`).join("") || `<div class="empty"><b>Todo sincronizado</b>No hay información pendiente en este dispositivo.</div>`}</div>`;
  $app.innerHTML = shell("Pendientes", body, { nav:"pending" });
}

function renderMore() {
  const secure = window.isSecureContext;
  const saved = state.meta?.saved_at ? dateText(state.meta.saved_at) : "Nunca";
  const canInstall = Boolean(installPrompt);
  const body = `<section class="card ${secure?"":"install-card"}"><div class="card-title">${secure?"Modo offline completo":"Modo offline limitado por HTTP"}</div><div class="card-sub" style="${secure?"":"color:rgba(255,255,255,.86)"}">${secure?"La app puede abrirse y capturar datos sin cobertura después de haber sincronizado una vez.":"Puede seguir capturando si pierde señal mientras esta pantalla permanece abierta. Para abrir la app desde cero sin Internet e instalarla como PWA, el servidor debe usar HTTPS."}</div>${canInstall?'<button class="btn" data-action="install">Instalar app</button>':""}</section>
    <section class="card"><div class="card-title">Datos del dispositivo</div><div class="card-sub">Usuario: ${esc(state.meta?.user?.name||"Sin descargar")}<br>Empresa: ${esc(state.meta?.user?.company_name||"")}<br>Última descarga: ${esc(saved)}<br>Pendientes: ${state.pending.filter(x=>x.state!=="synced").length}</div><div class="action-grid"><button class="btn btn-outline" data-action="refresh">Descargar datos</button><button class="btn btn-danger" data-action="clear-local">Borrar caché local</button></div></section>
    <section class="card"><div class="card-title">Versión de la aplicación: ${esc(APP_VERSION)}</div><div class="card-sub">Si no aparece el botón «Cotizar ahora» o ves una versión anterior, actualiza la interfaz. Esta acción no elimina catastros, visitas ni cotizaciones pendientes de sincronización.</div><button class="btn btn-secondary" style="width:100%;margin-top:12px" type="button" data-action="update-ui">↻ Actualizar interfaz PWA</button></section>
    <section class="card"><div class="card-title">Odoo completo</div><div class="card-sub">La PWA crea borradores rápidos. Para todas las funciones nativas, extensiones y campos personalizados de Ventas, utiliza el formulario completo de Odoo hasta que integremos los módulos que modifican tus proformas.</div><a class="btn btn-primary" style="width:100%;margin-top:12px" href="${nativeQuotationsUrl()}" target="_blank" rel="noopener">Abrir cotizaciones completas</a></section>`;
  $app.innerHTML = shell("Más", body, { nav:"more" });
}

function render() {
  switch (state.page) {
    case "detail": return renderDetail();
    case "visit": return renderVisit();
    case "quote": return renderQuote();
    case "quote-detail": return renderQuoteDetail();
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
  if (!/^\d{2}:\d{2}$/.test(value||"")) throw new Error("Ingrese una hora válida en formato HH:MM.");
  const [h,m] = value.split(":").map(Number);
  if (h>24 || m>59 || (h===24 && m!==0)) throw new Error("La hora debe estar entre 00:00 y 24:00.");
  return h+m/60;
}
function buildHours(form) {
  const hours = [...form.querySelectorAll("[data-hour-row]")].map(row=>({day:row.querySelector("[data-hour-day]").value,
    from:timeToFloat(row.querySelector("[data-hour-from]").value), to:timeToFloat(row.querySelector("[data-hour-to]").value)}));
  if (hours.length>35) throw new Error("Puede registrar como máximo 35 franjas horarias.");
  for (const h of hours) {
    if (h.from>=h.to || h.from>=24 || h.to<=0) throw new Error("La hora de cierre debe ser posterior a la apertura.");
    if (hours.some(x=>x!==h && x.day===h.day && x.from<h.to && x.to>h.from)) throw new Error("Hay horarios superpuestos en el mismo día.");
  }
  return hours;
}
function showFormError(message) {
  const box=document.querySelector("#form-validation");
  if (box) {box.innerHTML=`<div class="status-banner warn">${esc(message)}</div>`;box.scrollIntoView({behavior:"smooth",block:"nearest"});}
  else alert(message);
}
function validateForFinalize(obj) {
  const fields=[
    ["name","Razón social"],["vat","RUC / cédula"],["commercial_name","Nombre comercial"],
    ["owner_contact_name","Nombre del dueño"],["owner_phone","Teléfono del dueño"],
    ["commercial_contact_name","Contacto comercial"],["email","Email"],
    ["street","Dirección"],["city","Ciudad"],["customer_segment","Canal comercial"],
  ];
  const missing=fields.filter(([key])=>!String(obj[key]||"").trim()).map(([,name])=>name);
  if (Number(obj.store_count)<=0) missing.push("Número de tiendas");
  if (Number(obj.capa)<=0) missing.push("CAPA");
  if (!(obj.business_type_ids||[]).length) missing.push("Tipos de negocio");
  if (!(String(obj.phone||"").trim() || String(obj.mobile||"").trim())) missing.push("Teléfono/móvil del contacto");
  if (!(obj.opening_hours||[]).length) missing.push("Horario de atención");
  return missing;
}
async function queueOperation(type, payload, label) {
  const op={uuid:uuid(),type,payload,label,state:"pending",message:"",created_at:new Date().toISOString(),
    user_id:state.meta?.user?.id||null,company_id:state.meta?.user?.company_id||null};
  await idbPut(STORE_PENDING,op); await hydrateLocalState();render();return op;
}
async function submitCatastro(form, finalize=false) {
  const obj=formObject(form);
  try {obj.opening_hours=buildHours(form);} catch(err){showFormError(err.message);return;}
  obj.store_count=Number(obj.store_count||0);
  obj.capa=Number(obj.capa||0);
  obj.finalize=finalize;
  if (!String(obj.name||obj.vat||"").trim()){showFormError("Indique al menos el nombre o RUC/cédula para guardar el borrador.");return;}
  if (finalize) {
    const missing=validateForFinalize(obj);
    if (missing.length){showFormError(`Faltan campos para finalizar: ${missing.join(", ")}. Puede guardar como borrador.`);return;}
  }
  if (state.candidateMatches?.some(c=>c.census_active && (String(c.vat||"").replace(/\W/g,"")===String(obj.vat||"").replace(/\W/g,"") || String(c.name||"").toLowerCase()===String(obj.name||"").toLowerCase())) && !obj.selected_partner_id) {
    showFormError("Ya existen coincidencias. Revise la búsqueda antes de crear otra ficha.");return;
  }
  const op=await queueOperation("catastro",obj,`${obj.commercial_name||obj.name} · ${obj.vat||"sin identificación"}`);
  state.page="pending";render();
  if (navigator.onLine) await syncPending(false,[op.uuid]);
}

async function submitVisit(form, finalize=true) {
  const obj = formObject(form);
  const partner = state.partners.find(p=>p.id===Number(obj.partner_id));
  if (!partner) { alert("Seleccione un catastro."); return; }
  if (!truthy(partner.census_locked)) {alert("Primero finalice y proteja el catastro para poder registrar visitas.");return;}
  for (const name of ["purchase_made","has_stock","not_creditworthy","reschedule_visit","other_result"]) obj[name] = obj[name] === "true" ? "yes" : "no";
  if (obj.reschedule_visit === "yes" && !obj.next_visit_datetime){alert("Indique cuándo será la próxima visita.");return;}
  if (obj.other_result === "yes" && !obj.other_result_detail?.trim()){alert("Describa el resultado adicional.");return;}
  if (obj.next_visit_datetime) obj.next_visit_datetime=new Date(obj.next_visit_datetime).toISOString().slice(0,19).replace("T"," ");
  obj.partner_id = Number(obj.partner_id);
  obj.visit_datetime = nowServerString();
  obj.finalize = finalize;
  const op = await queueOperation("visit", obj, `${partnerLabel(partner)} · ${finalize?"Finalizar":"Borrador"}`);
  state.page = "pending";
  render();
  if (navigator.onLine) await syncPending(false, [op.uuid]);
}

async function syncPending(silent=false, onlyUuids=null) {
  if (!navigator.onLine || state.syncing || state.sessionBlocked) return;
  const candidates = state.pending.filter(x => !["synced","warning","conflict"].includes(x.state) && (!onlyUuids || onlyUuids.includes(x.uuid))).sort((a,b)=>String(a.created_at).localeCompare(String(b.created_at)));
  if (!candidates.length) return;
  try {
    state.syncing = true; render();
    const session=await rpc("/catastro/app/ping");
    if (state.meta?.user && (Number(state.meta.user.id)!==Number(session.user_id) || Number(state.meta.user.company_id)!==Number(session.company_id))) {
      state.sessionBlocked=true;
      throw new Error("La sesión cambió. Las operaciones offline pertenecen a otro usuario o compañía y no se enviarán.");
    }
    const payload=candidates.filter(op=>!op.user_id || Number(op.user_id)===Number(session.user_id)).map(({uuid,type,payload,user_id,company_id})=>({uuid,type,payload,user_id,company_id}));
    if (payload.length!==candidates.length) throw new Error("Hay operaciones registradas por otro usuario; sincronización bloqueada.");
    const response = await rpc("/catastro/app/sync", { operations: payload });
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
  const stores=[STORE_META,STORE_PARTNERS,STORE_PENDING,STORE_VISITS,STORE_ORDERS,STORE_PRODUCTS,STORE_CATALOG,STORE_QUOTE_PRODUCTS,STORE_QUOTE_DETAILS];
  await Promise.all(stores.map(store=>idbReplaceAll(store,[]).catch(async()=>{ const all=await idbGetAll(store); await Promise.all(all.map(x=>idbDelete(store,x.id||x.uuid||x.key))); })));
  await hydrateLocalState(); state.page="home"; render();
}

function renderCandidateResults() {
  const el=document.querySelector("#lookup-results");
  if (!el) return;
  if (state.lookupPending) {el.innerHTML='<div class="small">Buscando coincidencias…</div>';return;}
  const results=state.candidateMatches||[];
  el.innerHTML=results.length?`<div class="small">Se encontraron ${results.length} coincidencia(s). Seleccione una si corresponde al cliente.</div>${results.map(c=>`<div class="candidate-row"><div><strong>${esc(c.name)}</strong><div class="small">${esc(c.vat||"")} · ${esc(c.status_label||"")}</div></div><button type="button" class="btn ${c.can_use?"btn-primary":"btn-outline"}" data-action="choose-candidate" data-id="${c.id}" ${c.can_use||c.can_open?"":"disabled"}>${c.can_use?"Usar cliente":c.can_open?"Abrir":"Restringido"}</button></div>`).join("")}`:'<div class="small">Sin coincidencias conocidas. La creación se verificará nuevamente en Odoo al sincronizar.</div>';
}
async function searchCandidates(value) {
  const term=(value||"").trim();
  if (term.length<2) {state.candidateMatches=[];state.lookupPending=false;renderCandidateResults();return;}
  const local=state.partners.filter(p=>[p.name,p.commercial_name,p.vat].some(v=>String(v||"").toLowerCase().includes(term.toLowerCase()))).slice(0,8).map(p=>({id:p.id,name:p.name,vat:p.vat,commercial_name:p.commercial_name,status_label:"Catastro almacenado",can_open:true,can_use:false,census_active:true}));
  state.candidateMatches=local;state.lookupPending=state.online;renderCandidateResults();
  if (!state.online){state.lookupPending=false;renderCandidateResults();return;}
  try {
    const matches=await rpc("/catastro/app/lookup",{term});
    if (document.querySelector("#lookup-field")?.value.trim()!==term) return;
    state.candidateMatches=matches||[];
  } catch(err){state.lastError=err.message;state.candidateMatches=local;}
  state.lookupPending=false;renderCandidateResults();
}
async function submitUnlockRequest(form) {
  const p=selectedPartner();if(!p)return;
  if (!navigator.onLine){alert("Para solicitar edición debe conectarse a Odoo.");return;}
  const reason=form.querySelector('[name="reason"]')?.value.trim()||"";
  if(reason.length<5){alert("Describa el motivo del cambio (mínimo 5 caracteres).");return;}
  try {await rpc("/catastro/app/catastro/request-unlock",{partner_id:p.id,reason});
    await refreshFromServer(false);alert("Solicitud enviada al supervisor. Puede consultar su estado desde esta ficha.");}
  catch(err){alert(err.message||String(err));}
}
async function refreshPartnerStatus() {
  const p=selectedPartner();if(!p)return;
  if(!navigator.onLine){alert("Se necesita conexión para consultar el estado actualizado.");return;}
  try {const status=await rpc("/catastro/app/catastro/status",{partner_id:p.id});
    const fresh={...p,...status};await idbPut(STORE_PARTNERS,fresh);await hydrateLocalState();render();}
  catch(err){alert(err.message||String(err));}
}

$app.addEventListener("input", (event) => {
  if (event.target?.id === "lookup-field") {
    const value=event.target.value;
    const form=event.target.closest("form");
    if(form) form.querySelector('[name="selected_partner_id"]').value="";
    state.candidateSelected=null;
    clearTimeout(state.lookupTimer);
    state.lookupTimer=setTimeout(()=>searchCandidates(value),300);
  }
  if (event.target?.id === "quote-search") {
    const value=event.target.value;state.quoteSearch=value;
    clearTimeout(state.quoteLookupTimer);state.quoteLookupTimer=setTimeout(()=>searchQuoteProducts(value),300);
  }
  if (event.target?.matches('#quote-form [name="client_order_ref"]')) {
    state.quoteClientRef=event.target.value;
  }
  if (event.target?.matches("[data-quote-qty]")) {
    const line=state.quoteLines.find(x=>x.id===Number(event.target.dataset.quoteQty));
    if(line)line.qty=event.target.value;
  }
  if (event.target?.id === "partner-search") { state.search = event.target.value; renderHome(); const input=document.querySelector("#partner-search"); if(input){input.focus(); input.setSelectionRange(state.search.length,state.search.length);} }
});

$app.addEventListener("change", (event) => {
  if (event.target?.matches('#quote-form [name="partner_id"]')) {
    state.quotePartnerId=Number(event.target.value)||null;
    state.quoteVisitId=null;
    state.quoteLines=[];state.quoteResults=[];state.quoteSearch="";renderQuote();
  }
  if (event.target?.matches('#quote-form [name="visit_id"]')) {
    state.quoteVisitId=Number(event.target.value)||null;
  }
});

$app.addEventListener("click", async (event) => {
  const navEl = event.target.closest("[data-nav]");
  if (navEl) { state.page=navEl.dataset.nav;
    if (state.page==="quote") { state.quotePartnerId=state.selectedPartnerId||state.quotePartnerId;state.quoteDetail=null; }
    if(state.page!=="detail") state.selectedPartnerId=["visit","quote"].includes(state.page)?state.selectedPartnerId:null;
    render(); return; }
  const partnerEl = event.target.closest("[data-open-partner]");
  if (partnerEl) { state.selectedPartnerId=Number(partnerEl.dataset.openPartner); state.page="detail"; render(); return; }
  const visitEl = event.target.closest("[data-action='visit-partner']");
  if (visitEl) { state.selectedPartnerId=Number(visitEl.dataset.id); if(!truthy(selectedPartner()?.census_locked)){alert("Finalice y proteja primero el catastro.");return;} state.page="visit"; render(); return; }
  const action = event.target.closest("[data-action]")?.dataset.action;
  if (action === "open-quote") {state.quotePartnerId=null;state.quoteDetail=null;state.quoteVisitId=null;state.quoteClientRef="";state.quoteLines=[];state.quoteSearch="";state.quoteResults=[];state.page="quote";render();return;}
  if (action === "quote-partner") {const id=Number(event.target.closest("[data-id]")?.dataset.id);const partner=state.partners.find(x=>x.id===id);state.quotePartnerId=truthy(partner?.census_locked)?id:null;state.quoteVisitId=null;state.quoteClientRef="";state.quoteLines=[];state.quoteResults=[];state.quoteSearch="";state.quoteDetail=null;state.page="quote";render();return;}
  if (action === "update-ui") {
    if (!navigator.onLine) {alert("Conéctese a Internet para descargar la nueva versión. Sus registros locales se conservan.");return;}
    if ((state.quoteLines.length || ["new","edit","visit"].includes(state.page)) && !confirm("¿Actualizar interfaz ahora? Se conservarán los datos sincronizados y las operaciones pendientes, pero los cambios todavía no guardados en pantalla pueden perderse.")) return;
    try {
      const reg=await navigator.serviceWorker?.getRegistration("/catastro/");
      if (reg) await reg.update();
      window.location.replace(`/catastro/app?version=${encodeURIComponent(APP_VERSION)}&t=${Date.now()}`);
    } catch(err) {alert(`No se pudo actualizar la interfaz: ${err.message||err}`);}
    return;
  }
  if (action === "quote-add-product") {
    const id=Number(event.target.closest("[data-id]")?.dataset.id);
    const product=state.quoteResults.find(x=>x.id===id);
    if(!product)return;
    const existing=state.quoteLines.find(x=>x.id===id);
    if(existing)existing.qty=Number(existing.qty||0)+1;
    else state.quoteLines.push({id:product.id,name:product.name,code:product.code,uom:product.uom,qty:1});
    state.quoteSearch="";state.quoteResults=[];renderQuote();return;
  }
  if (action === "quote-remove-product") {state.quoteLines=state.quoteLines.filter(x=>x.id!==Number(event.target.closest("[data-id]").dataset.id));renderQuote();return;}
  if (action === "view-quote") {await openQuote(Number(event.target.closest("[data-id]").dataset.id));return;}
  if (action === "back-quote") {state.page="quote";state.quoteDetail=null;render();return;}
  if (action === "capture-gps") {
    const form=event.target.closest("form");
    const preview=form?.querySelector("[data-gps-preview]");
    const field=form?.querySelector('[name="census_gps_payload"], [name="gps_capture_payload"]');
    if (!form||!field||!navigator.geolocation){alert("Este dispositivo no permite capturar la ubicación.");return;}
    if(preview)preview.textContent="Obteniendo ubicación…";
    navigator.geolocation.getCurrentPosition((pos)=>{
      field.value=JSON.stringify({latitude:pos.coords.latitude,longitude:pos.coords.longitude,accuracy:pos.coords.accuracy});
      if(preview)preview.textContent=`GPS capturado · precisión ${Math.round(pos.coords.accuracy||0)} m`;
    },(err)=>{if(preview)preview.textContent=`No se pudo capturar GPS: ${err.message}`;},
    {enableHighAccuracy:true,timeout:20000,maximumAge:0});return;
  }
  if (action === "add-hour") {document.querySelector("#hours-list")?.insertAdjacentHTML("beforeend",hourRow());return;}
  if (action === "remove-hour") {event.target.closest("[data-hour-row]")?.remove();return;}
  if (action === "choose-candidate") {
    const id=Number(event.target.closest("[data-id]")?.dataset.id);
    const c=state.candidateMatches.find(x=>x.id===id);
    if (!c) return;
    if (c.can_open) {const p=state.partners.find(x=>x.id===id);if(p){state.selectedPartnerId=id;state.page="detail";render();}else window.open(`/web#id=${id}&model=res.partner&view_type=form`,"_blank","noopener");return;}
    if (!c.can_use) return;
    const form=document.querySelector("#catastro-form");if(!form)return;
    form.querySelector('[name="selected_partner_id"]').value=String(id);
    state.candidateSelected=c;
    for(const field of ["name","vat","commercial_name","phone","mobile","email","street","city"]) {
      const input=form.querySelector(`[name="${field}"]`);if(input && c[field]) input.value=c[field];
    }
    const box=document.querySelector("#lookup-results");if(box)box.innerHTML=`<div class="status-banner">Cliente seleccionado: ${esc(c.name)}. Se utilizará su ficha existente.</div>`;
    return;
  }
  if (action === "show-unlock-form") {const form=document.querySelector("#unlock-form");if(form){form.hidden=false;form.querySelector("textarea")?.focus();}return;}
  if (action === "hide-unlock-form") {const form=document.querySelector("#unlock-form");if(form)form.hidden=true;return;}
  if (action === "refresh-status") {await refreshPartnerStatus();return;}
  if (action === "open-quote-result") {await openQuote(Number(event.target.closest("[data-id]").dataset.id));return;}
  if (action === "open-result") {state.selectedPartnerId=Number(event.target.closest("[data-id]").dataset.id);state.page="detail";if(!selectedPartner()&&navigator.onLine) await refreshFromServer(false);render();return;}
  if (action === "finalize-partner") {
    const p=selectedPartner();if(!p)return;
    if(!confirm(`¿Finalizar y proteger el catastro de ${partnerLabel(p)}? Solo se podrá editar con autorización posterior.`))return;
    const op=await queueOperation("catastro_finalize",{partner_id:p.id,base_write_date:p.write_date||""},`${partnerLabel(p)} · proteger`);
    state.page="pending";render();if(navigator.onLine) await syncPending(false,[op.uuid]);return;
  }
  if (action === "finish-edit") {
    const p=selectedPartner();if(!p||!navigator.onLine){alert("Se necesita conexión para cerrar la edición autorizada.");return;}
    if (state.pending.some(op=>op.type==="catastro_update" && Number(op.payload?.partner_id)===p.id && !["synced","warning","conflict"].includes(op.state))) {
      await syncPending(false);
      if (state.pending.some(op=>op.type==="catastro_update" && Number(op.payload?.partner_id)===p.id && !["synced","warning"].includes(op.state))) {
        alert("Primero resuelva y sincronice los cambios pendientes antes de cerrar la edición.");return;
      }
    }
    if(!confirm("¿Finalizar edición y volver a proteger el catastro?"))return;
    try{await rpc("/catastro/app/catastro/finish-edit",{partner_id:p.id});await refreshFromServer(false);}
    catch(err){alert(err.message||String(err));}return;
  }
  if (action === "refresh") { await syncPending(true); await refreshFromServer(true); return; }
  if (action === "new-catastro") { state.page="new"; render(); return; }
  if (action === "edit-partner") {if(!truthy(selectedPartner()?.census_can_edit_master)){alert("El catastro está protegido; solicite habilitación.");return;} state.page="edit"; render(); return; }
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
  if (event.target.id === "catastro-form") await submitCatastro(event.target,event.submitter?.value==="finalize");
  if (event.target.id === "catastro-edit-form") await submitCatastroUpdate(event.target);
  if (event.target.id === "visit-form") await submitVisit(event.target,true);
  if (event.target.id === "quote-form") await submitQuote(event.target);
  if (event.target.id === "unlock-form") await submitUnlockRequest(event.target);
});

async function init() {
  db = await openDb();
  await hydrateLocalState();
  render();
  if (window.isSecureContext && "serviceWorker" in navigator) {
    try { await navigator.serviceWorker.register("/catastro/sw.js", { scope: "/catastro/" }); } catch (err) { console.warn("Service worker no disponible", err); }
  }
  if (navigator.onLine) {
    await refreshFromServer(false);
    await syncPending(true);
  }
}

init().catch((err) => {
  console.error(err);
  $app.innerHTML = `<div class="boot-screen"><div class="boot-logo">!</div><strong>No se pudo iniciar la app</strong><span>${esc(err.message||err)}</span><a class="btn btn-primary" href="/web">Volver a Odoo</a></div>`;
});
