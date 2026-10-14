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
  newCandidate: null,
  searchMatches: [],
  newDraft: {},
  editDraft: null,
  editHoursTouched: false,
  lookupNotice: "",
  requestKind: null,
  requestCandidate: null,
  matchFetching: false,
  draftGps: null,
  sessionMismatch: false,
};
let matchSearchTimer = null;
let matchSearchSeq = 0;

window.addEventListener("beforeinstallprompt", (event) => {
  event.preventDefault();
  installPrompt = event;
  if (state.page === "more") render();
});

window.addEventListener("online", async () => {
  state.online = true;
  state.lastError = "";
  render();
  await refreshFromServer(false);
  if(!state.sessionMismatch) await syncPending(true);
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
  return new Date().toISOString().slice(0, 19).replace("T", " ");
}
function localDateTimeToUTC(value) {
  if (!value) return "";
  const dt=new Date(value);
  return Number.isNaN(dt.getTime()) ? "" : dt.toISOString().slice(0, 19).replace("T", " ");
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
    // Offline records and queued operations belong to one user/company context.
    // Never upload a previous user's queue under a different authenticated session.
    const oldUser=state.meta?.user;
    if (oldUser && (oldUser.id !== data.user?.id || oldUser.company_id !== data.user?.company_id)) {
      state.sessionMismatch=true;
      state.lastError="Se inició sesión con otro usuario o empresa. Los datos anteriores no se sincronizarán.";
      return;
    }
    state.sessionMismatch=false;
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

function nav(active, cls="bottom-nav") {
  const item = (page, icon, label) => `<button type="button" class="nav-btn ${active===page?"active":""}" data-nav="${page}" ${active===page?'aria-current="page"':""}><b aria-hidden="true">${icon}</b><span>${label}</span></button>`;
  return `<nav class="${cls}" aria-label="Navegación principal">${item("home","▦","Catastros")}${item("visit","✚","Nueva visita")}${item("pending","⇅","Sincronización")}${item("more","⚙","Configuración")}</nav>`;
}
function shell(title, body, opts={}) {
  const pendingCount=state.pending.filter(x=>!["synced","warning"].includes(x.state)).length;
  return `<div class="app-shell">
    <aside class="desktop-sidebar" aria-label="Menú de aplicación">
      <div class="sidebar-brand"><span class="sidebar-logo">C</span><span><strong>Conedera</strong><small>Catastro de Campo</small></span></div>
      ${nav(opts.nav || state.page,"side-nav")}
      <button class="btn btn-primary sidebar-new" type="button" data-action="new-catastro">＋ Nuevo catastro</button>
      <div class="sidebar-bottom"><span class="sidebar-user">${esc(state.meta?.user?.name||"Equipo comercial")}</span><small>${esc(state.meta?.user?.company_name||"Catastro Comercial")}</small><small>${pendingCount} operaciones por revisar</small></div>
    </aside>
    <div class="app-workspace">
      <header class="topbar"><div><div class="eyebrow">Conedera / Catastro Comercial</div><h1>${esc(title)}</h1></div>
      <div class="header-actions"><span class="desktop-user">${esc(state.meta?.user?.name||"")}</span><button class="icon-btn" data-action="refresh" title="Actualizar desde Odoo" aria-label="Actualizar desde Odoo">↻</button></div></header>
      <main class="content" id="main-content">${connectionBanner()}<div class="view-content">${body}</div></main>
      ${opts.fab ? `<button class="fab" data-action="new-catastro" aria-label="Nuevo catastro">＋</button>` : ""}
      ${nav(opts.nav || state.page)}
    </div>
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
  return `<article class="card clickable" data-open-partner="${p.id}" role="button" tabindex="0" aria-label="Abrir catastro ${esc(partnerLabel(p))}">
    <div class="row space"><div><div class="card-title">${esc(partnerLabel(p))}</div><div class="card-sub">${esc(p.vat || "Sin RUC/cédula")}</div></div><span style="font-size:26px;color:var(--brand)">›</span></div>
    <div class="card-sub" style="margin-top:8px">${esc(p.name || "")}${partnerAddress(p)?` · ${esc(partnerAddress(p))}`:""}</div>
    <div class="chips">${locked?'<span class="chip ok">Protegido</span>':'<span class="chip warn">Borrador</span>'}${complete!==null?`<span class="chip">${complete}% completo</span>`:""}${p.census_team_id?`<span class="chip">${esc(relationName(p.census_team_id))}</span>`:""}</div>
  </article>`;
}

function renderHome() {
  const q = state.search.trim().toLowerCase();
  const partners = state.partners.filter(p => !q || [p.name,p.commercial_name,p.vat,p.city,p.phone,p.mobile].some(v => String(v||"").toLowerCase().includes(q)));
  const body = `<div class="home-header"><div><div class="section-kicker">GESTIÓN COMERCIAL</div><p class="page-intro">Consulta, registra y da seguimiento a los clientes de tu cartera.</p></div><button type="button" class="btn btn-primary new-catastro-cta" data-action="new-catastro">＋ Nuevo catastro</button></div>
    <div class="home-stats"><div class="stat"><strong>${state.partners.length}</strong><span>Catastros descargados</span></div><div class="stat"><strong>${state.pending.filter(x=>!["synced","warning"].includes(x.state)).length}</strong><span>Por revisar</span></div><div class="stat"><strong>${state.visits.length}</strong><span>Visitas registradas</span></div></div>
    <div class="search-wrap"><label class="visually-hidden" for="partner-search">Buscar catastros</label><input id="partner-search" class="search" placeholder="Buscar por RUC, nombre, ciudad…" value="${esc(state.search)}" autocomplete="off"/></div>
    <div class="result-count" id="result-count">${partners.length} catastros</div>
    <div class="cards" id="home-results">${partners.map(partnerCard).join("") || `<div class="empty"><b>No hay catastros en el dispositivo</b>${state.online?"Pulse actualizar o cree uno nuevo.":"Conéctese una vez para descargar sus catastros."}</div>`}</div>`;
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

function unlockStatus(p) {
  const labels={ pending:"Solicitud pendiente de revisión", approved:"Solicitud aprobada", rejected:"Solicitud rechazada", expired:"Autorización vencida" };
  const code=p.census_latest_unlock_state;
  if (!code) return "";
  return `<section class="status-banner ${code==="approved"?"":"warn"}" aria-live="polite"><strong>${esc(labels[code]||code)}</strong>${p.census_latest_unlock_review_note?`<div class="status-detail">Respuesta: ${esc(p.census_latest_unlock_review_note)}</div>`:""}${p.census_latest_unlock_valid_until?`<div class="status-detail">Válida hasta: ${esc(dateText(p.census_latest_unlock_valid_until))}</div>`:""}</section>`;
}
function unlockActions(p) {
  const editable=truthy(p.census_can_edit_master);
  if (editable) return `<button class="btn btn-outline" data-action="edit-partner">✎ Editar datos</button>`;
  if (!truthy(p.census_locked)) return `<div class="small">Este catastro pertenece a otro responsable.</div>`;
  return `<button class="btn btn-outline" data-action="request-unlock">Solicitar edición</button>`;
}
function hoursSummary(p) {
  if (Array.isArray(p.opening_hours_data) && p.opening_hours_data.length) {
    const names=new Map(hourDays().map(x=>[String(x.value),x.label]));
    return p.opening_hours_data.map(h=>`${names.get(String(h.day))||h.day}: ${h.from}–${h.to}`).join("\n");
  }
  return p.opening_hours_summary || p.census_opening_hours_summary || "";
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
    <div class="action-grid"><a class="btn btn-outline" href="/web#id=${p.id}&model=res.partner&view_type=form" title="Abrir ficha de cliente en Odoo">Proformas en Odoo</a>${unlockActions(p)}</div>
    ${unlockStatus(p)}
    ${!truthy(p.census_can_edit_master) && truthy(p.census_locked) ? `<section class="form-card request-card"><h2>Habilitación de edición</h2><p class="small">La aprobación es gestionada por el supervisor del módulo original. Podrás consultar el rechazo y sus observaciones aquí.</p><div class="field"><label for="unlock-reason">Motivo de la solicitud</label><textarea id="unlock-reason" placeholder="Explica qué información necesitas corregir…"></textarea></div><button type="button" data-action="send-unlock" class="btn btn-primary" ${!state.online?'disabled title="Requiere conexión"':''}>Enviar solicitud</button><button type="button" data-action="refresh" class="btn btn-secondary">↻ Consultar estado</button></section>`:""}
    <div class="section-title">Contacto</div><section class="card"><div class="card-sub">${esc(p.phone||p.mobile||"Sin teléfono")}<br>${esc(p.email||"Sin email")}<br>${esc(partnerAddress(p)||"Sin dirección")}</div>${hoursSummary(p)?`<div style="margin-top:10px;white-space:pre-line" class="card-sub"><strong>Horario</strong><br>${esc(hoursSummary(p))}</div>`:""}</section>
    <div class="section-title">Bitácora reciente</div><section class="card">${timeline(p.id)}</section>
    <div class="section-title">Productos proformados</div><section class="card">${prod.length?prod.map(x=>`<div class="product-row"><div><strong>${esc(x.product_name)}</strong><br><span>${x.lines} líneas · promedio ${money(x.avg_price)}</span></div><div style="text-align:right"><strong>${money(x.qty)}</strong><br><span>${money(x.subtotal)}</span></div></div>`).join(""):`<div class="empty">Sin productos almacenados todavía.</div>`}</section>`;
  $app.innerHTML = shell(partnerLabel(p), body, { nav:"home" });
}

function toggleHtml(name, label, value=false) {
  return `<div class="field"><label>${esc(label)}</label><div class="toggle-grid"><button type="button" class="toggle ${value===true?"active":""}" data-toggle="${name}" data-value="true">Sí</button><button type="button" class="toggle ${value===false?"active":""}" data-toggle="${name}" data-value="false">No</button></div><input type="hidden" name="${name}" value="${value?"true":"false"}"/></div>`;
}

function partnerOptions(selected) {
  return `<option value="">Seleccione cliente…</option>${[...state.partners].sort((a,b)=>partnerLabel(a).localeCompare(partnerLabel(b))).map(p=>`<option value="${p.id}" ${Number(selected)===p.id?"selected":""}>${esc(partnerLabel(p))} · ${esc(p.vat||"")}</option>`).join("")}`;
}
function renderVisit() {
  const selected = state.selectedPartnerId || "";
  const body = `<form id="visit-form">
    <section class="form-card"><h2>1. Cliente y resultado</h2><div class="field"><label>Catastro</label><select name="partner_id" required>${partnerOptions(selected)}</select></div>${toggleHtml("purchase_made","¿Realizó compra?",false)}${toggleHtml("has_stock","¿Tiene stock?",true)}${toggleHtml("no_credit_subject","¿No es sujeto de crédito?",false)}${toggleHtml("reschedule_visit","¿Reagendar visita?",false)}</section>
    <section class="form-card"><h2>2. Observaciones</h2><div class="field"><label>Detalle de la visita</label><textarea name="notes" placeholder="Qué encontró, acuerdos, próximos pasos…"></textarea></div><div class="field"><label>Otros / resultado adicional</label><input name="other_result_detail" placeholder="Opcional"/></div><div class="field"><label>Próxima visita (si reagenda)</label><input name="next_visit_datetime" type="datetime-local"/></div></section>
    <section class="form-card"><h2>3. Evidencia</h2><div class="photo-box"><div id="photo-preview"></div><label class="photo-trigger">📷 Tomar foto<input id="photo-input" type="file" accept="image/*" capture="environment"/></label></div><input type="hidden" name="photo"/><div class="gps-box"><button type="button" class="btn btn-secondary" data-action="capture-gps">◎ Capturar ubicación GPS</button><span class="small" id="gps-status">La ubicación queda en la visita, incluso sin conexión.</span></div><input type="hidden" name="gps_payload"/></section>
    <div class="sticky-actions"><button type="button" class="btn btn-secondary" data-action="save-visit-offline">Guardar offline</button><button type="submit" class="btn btn-primary">Finalizar visita</button></div>
  </form>`;
  $app.innerHTML = shell("Nueva visita", body, { nav:"visit" });
  bindPhotoInput();
}

function catalogChecks(name, items, selected=[]) {
  if (!items?.length) return `<div class="small">Se completará en Odoo cuando vuelva la conexión.</div>`;
  return `<div style="display:grid;gap:8px">${items.map(x=>`<label class="row" style="min-height:40px"><input type="checkbox" name="${name}" value="${x.id}" ${selected.includes(x.id)?"checked":""}/><span>${esc(x.name)}</span></label>`).join("")}</div>`;
}
function hourDays() {
  return state.meta?.capabilities?.opening_hour_days?.length
    ? state.meta.capabilities.opening_hour_days
    : ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"].map((label,i)=>({value:String(i),label}));
}
function hourRows(form) {
  return Array.from(form?.querySelectorAll(".hour-row") || []).map(row=>({
    day: row.querySelector("[data-hour-day]")?.value || "",
    from: row.querySelector("[data-hour-from]")?.value || "",
    to: row.querySelector("[data-hour-to]")?.value || "",
  }));
}
function hourEditor(rows=[]) {
  const days = hourDays();
  const rowMarkup = (r, i) => `<div class="hour-row" data-hour-row="${i}">
    <div class="field hour-day"><label>Día</label><select data-hour-day aria-label="Día del horario" required>${days.map(d=>`<option value="${esc(d.value)}" ${String(r.day)===String(d.value)?"selected":""}>${esc(d.label)}</option>`).join("")}</select></div>
    <div class="field"><label>Abre</label><input data-hour-from type="time" required value="${esc(r.from || "09:00")}"/></div>
    <div class="field"><label>Cierra</label><input data-hour-to type="${r.to==="24:00"?"text":"time"}" ${r.to==="24:00"?'inputmode="numeric" pattern="([01][0-9]|2[0-4]):[0-5][0-9]"':""} required value="${esc(r.to || "18:00")}"/></div>
    <button type="button" class="remove-hour" data-action="remove-hour" aria-label="Eliminar horario">×</button>
  </div>`;
  return `<div data-hours-container>${rows.map(rowMarkup).join("")}</div>
    <button class="btn btn-outline add-hour" type="button" data-action="add-hour">＋ Agregar horario</button>
    <p class="small" style="margin-top:9px">Puede agregar varios días y franjas, incluso dos turnos en el mismo día.</p>`;
}
function hoursSection(rows=[]) {
  const supported=state.meta?.capabilities?.opening_hour_model !== false;
  return `<section class="form-card"><h2>6. Horarios de atención</h2>
    ${!supported?`<div class="status-banner warn">El módulo base no reportó campos de horarios compatibles. Puede guardar otros datos, pero no se enviarán horarios hasta corregir su configuración.</div>`:""}
    ${hourEditor(rows)}
  </section>`;
}
function fieldValue(data, key, fallback="") { return esc(data?.[key] ?? fallback); }
function renderNewCatastro() {
  const d=state.newDraft || {};
  const existing=state.newCandidate;
  const body = `<form id="catastro-form">
    <section class="form-card"><h2>Buscar cliente antes de crear</h2>
      <div class="field"><label for="client-match-input">Nombre, cédula o RUC</label><input id="client-match-input" class="search" placeholder="Escriba para mostrar coincidencias…" autocomplete="off" value="${esc(d.search_term||"")}"/></div>
      <div id="client-matches" aria-live="polite">${renderMatchesHtml(state.searchMatches)}</div>
      <div id="lookup-notice" aria-live="polite">${state.lookupNotice?`<div class="status-banner warn">${esc(state.lookupNotice)}</div>`:""}</div>
      <div id="reassignment-form">${reassignmentForm()}</div>
      <div id="existing-selection">${existing?existingBanner(existing):""}</div>
    </section>
    <section class="form-card"><h2>1. Identificación</h2>
      <div class="field"><label>RUC / cédula</label><input name="vat" autocomplete="off" inputmode="numeric" value="${fieldValue(d,"vat")}"/></div>
      <div class="field"><label>Razón social / cliente *</label><input name="name" required value="${fieldValue(d,"name")}"/></div>
      <div class="field"><label>Nombre comercial *</label><input name="commercial_name" required value="${fieldValue(d,"commercial_name")}"/></div>
      <div class="compact-fields"><div class="field"><label>Número de tiendas *</label><input name="store_count" required type="number" min="1" inputmode="numeric" value="${fieldValue(d,"store_count")}"/></div><div class="field"><label>CAPA / compra *</label><input name="capa" required type="number" min="0" step="0.01" inputmode="decimal" value="${fieldValue(d,"capa")}"/></div></div>
    </section>
    <section class="form-card"><h2>2. Contactos</h2>
      <div class="field"><label>Dueño / propietario</label><input name="owner_contact_name" value="${fieldValue(d,"owner_contact_name")}"/></div><div class="field"><label>Teléfono del dueño</label><input name="owner_phone" inputmode="tel" value="${fieldValue(d,"owner_phone")}"/></div>
      <div class="field"><label>Contacto comercial</label><input name="commercial_contact_name" value="${fieldValue(d,"commercial_contact_name")}"/></div><div class="field"><label>Teléfono</label><input name="phone" inputmode="tel" value="${fieldValue(d,"phone")}"/></div>
      <div class="field"><label>Móvil / WhatsApp</label><input name="mobile" inputmode="tel" value="${fieldValue(d,"mobile")}"/></div><div class="field"><label>Email</label><input name="email" type="email" inputmode="email" value="${fieldValue(d,"email")}"/></div>
    </section>
    <section class="form-card"><h2>3. Ubicación</h2>
      <div class="field"><label>Dirección</label><input name="street" value="${fieldValue(d,"street")}"/></div>
      <div class="field"><label>Ciudad</label><input name="city" value="${fieldValue(d,"city")}"/></div>
      <div class="field"><label>Descripción del negocio</label><textarea name="business_description">${fieldValue(d,"business_description")}</textarea></div><div class="gps-box"><button type="button" class="btn btn-secondary" data-action="capture-gps">◎ Ubicación del local</button><span class="small" id="gps-status">${d.census_gps_payload?"Ubicación capturada":"Se puede capturar sin cobertura con GPS activo"}</span></div><input type="hidden" name="census_gps_payload" value="${fieldValue(d,"census_gps_payload")}"/>
    </section>
    <section class="form-card"><h2>4. Tipo de negocio</h2><div class="field"><label>Canal comercial</label><select name="customer_segment"><option value="">Seleccione…</option>${[["wholesaler","Mayorista"],["reseller","Revendedor / distribuidor"],["retail","Tienda al detalle"],["mixed","Mixto"],["other","Otro"]].map(([k,v])=>`<option value="${k}" ${d.customer_segment===k?"selected":""}>${v}</option>`).join("")}</select></div>${catalogChecks("business_type_ids",state.catalog.business_types,d.business_type_ids||[])}</section>
    <section class="form-card"><h2>5. Marcas de celulares <span class="small">(opcional)</span></h2>${catalogChecks("mobile_brand_ids",state.catalog.mobile_brands,d.mobile_brand_ids||[])}</section>
    ${hoursSection(d.opening_hours || [])}
    <div class="sticky-actions"><button type="button" class="btn btn-secondary" data-nav="home">Cancelar</button><button type="submit" class="btn btn-primary">${existing?"Guardar catastro existente":"Guardar catastro"}</button></div>
  </form>`;
  $app.innerHTML = shell("Nuevo catastro", body, { nav:"home" });
}
function normalizedMatch(value) { return String(value||"").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase(); }
function reassignmentForm() {
  const p=state.requestCandidate;
  if (!p || !p.can_request) return "";
  return `<div class="request-card"><strong>Cliente asignado a otro comercial</strong><p class="small">No se creará un duplicado. Puedes solicitar una reasignación al responsable correspondiente.</p><div class="field"><label for="reassign-reason">Motivo de reasignación</label><textarea id="reassign-reason" placeholder="Indica por qué necesitas esta ficha…"></textarea></div><button type="button" class="btn btn-primary" data-action="send-reassignment" ${!state.online?'disabled':''}>Enviar solicitud</button><button type="button" class="btn btn-outline" data-action="close-reassignment">Cancelar</button></div>`;
}
function locallyMatching(term) {
  const q=normalizedMatch(term.trim());
  if (q.length<2) return [];
  return state.partners.filter(p=>[p.name,p.commercial_name,p.vat].some(x=>normalizedMatch(x).includes(q))).slice(0,15);
}
function renderMatchesHtml(matches) {
  if (!matches?.length) return `<p class="small">Busque por nombre o identificación para evitar crear clientes duplicados.${!state.online?" Sin conexión: solo se consultan los clientes descargados.":""}</p>`;
  return `<div class="match-list">${matches.map(p=>`<div class="match-item"><div><strong>${esc(partnerLabel(p))}</strong><div class="small">${esc(p.vat||"Sin identificación")} · ${esc(p.status_label||(truthy(p.census_active)?"Catastro existente":"Cliente en Odoo"))}</div></div>
    <button type="button" class="btn btn-secondary" data-use-match="${p.id}">${p.can_request?"Solicitar":p.can_open || truthy(p.census_active)?"Ver":"Seleccionar"}</button></div>`).join("")}</div>`;
}
function existingBanner(p) {
  return `<div class="status-banner">Cliente seleccionado: <strong>${esc(partnerLabel(p))}</strong> (${esc(p.vat||"sin RUC")}). Se actualizará su ficha, sin duplicarla. <button type="button" class="link-button" data-action="deselect-match">Cambiar</button></div>`;
}
function updateMatchContainer() {
  const el=document.querySelector("#client-matches");
  if (el) el.innerHTML=renderMatchesHtml(state.searchMatches);
}
function searchPotentialMatches(value) {
  const term=String(value||"").trim();
  const input=document.querySelector("#client-match-input");
  if (input && document.activeElement !== input) input.value=term;
  state.newDraft.search_term=term;
  const notice=document.querySelector("#lookup-notice");
  if (notice) notice.textContent="";
  state.lookupNotice="";
  clearTimeout(matchSearchTimer);
  const seq=++matchSearchSeq;
  state.searchMatches=locallyMatching(term);
  updateMatchContainer();
  if (term.length<2 || !navigator.onLine) return;
  matchSearchTimer=setTimeout(async()=>{
    try {
      const res=await rpc("/conedera/app/partner_search", {term});
      if (seq!==matchSearchSeq || state.page!=="new") return;
      const map=new Map([...state.searchMatches,...(res.matches||[])].map(p=>[p.id,p]));
      state.searchMatches=Array.from(map.values()).slice(0,20);
      updateMatchContainer();
    } catch (err) {
      if (seq===matchSearchSeq) console.warn("Búsqueda online no disponible",err);
    }
  },300);
}
function captureDraft(form, isEdit=false) {
  if (!form) return;
  const result={...formObject(form),opening_hours:hourRows(form)};
  if (!isEdit) {
    result.search_term=document.querySelector("#client-match-input")?.value || state.newDraft.search_term || "";
    state.newDraft=result;
  } else state.editDraft=result;
}
function candidateById(id) { return state.searchMatches.find(p=>p.id===id) || state.partners.find(p=>p.id===id); }
function chooseMatch(p) {
  if (p.can_request) {
    state.requestCandidate=p; state.newCandidate=null;
    const panel=document.querySelector("#reassignment-form"); if(panel) panel.innerHTML=reassignmentForm();
    return;
  }
  if (p.can_open || (p.can_open===undefined && truthy(p.census_active))) {
    state.selectedPartnerId=p.id;
    if (!state.partners.some(x=>x.id===p.id)) {
      state.lookupNotice="Este catastro no está en los datos descargados; ábralo desde Odoo o actualice la aplicación.";
      if (state.online) { window.location.href=`/web#id=${p.id}&model=res.partner&view_type=form`; }
      return;
    }
    state.page="detail"; render(); return;
  }
  if (p.can_use===false) { state.lookupNotice="Este cliente no está disponible para su usuario."; document.querySelector("#lookup-notice").textContent=state.lookupNotice; return; }
  if (truthy(p.census_locked)) { alert("El cliente está protegido; solicite edición antes de continuar."); return; }
  state.newCandidate=p;state.requestCandidate=null;
  const panel=document.querySelector("#reassignment-form");if(panel)panel.innerHTML="";
  const form=document.querySelector("#catastro-form");
  const fields=["name","vat","commercial_name","phone","mobile","email","street","city","capa"];
  for (const field of fields) {
    const input=form?.elements.namedItem(field);
    if (input && (["name","vat","commercial_name"].includes(field) || !String(input.value||"").trim())) {
      input.value=p[field] || (field==="commercial_name"?p.name:"");
    }
  }
  const store=form?.elements.namedItem("store_count");
  if (store && !store.value) store.value=p.census_store_count || p.store_count || "";
  captureDraft(form);
  const selection=document.querySelector("#existing-selection");
  if (selection) selection.innerHTML=existingBanner(p);
  const submit=form?.querySelector('[type="submit"]');
  if (submit) submit.textContent="Guardar catastro existente";
}

function operationLabel(op) {
  return op.type === "visit" ? "Visita" : op.type === "catastro" ? "Nuevo catastro" : "Actualización";
}

function renderEditCatastro() {
  const p = selectedPartner();
  if (!p) { state.page="home"; return renderHome(); }
  const d=state.editDraft || {};
  const value=(name, fallback="")=>fieldValue(d,name,fallback);
  const hours=state.editDraft?.opening_hours || p.opening_hours_data || [];
  const body = `<form id="catastro-edit-form">
    <section class="form-card"><h2>Datos del catastro</h2><div class="status-banner warn">Los cambios se validarán al sincronizar. Si la ficha cambió en Odoo, no se sobrescribirá automáticamente.</div>
      <div class="field"><label>RUC / cédula</label><input name="vat" value="${value("vat",p.vat||"")}"/></div>
      <div class="field"><label>Razón social / cliente</label><input name="name" value="${value("name",p.name||"")}"/></div>
      <div class="field"><label>Nombre comercial</label><input name="commercial_name" value="${value("commercial_name",p.commercial_name||"")}"/></div>
      <div class="compact-fields"><div class="field"><label>Número de tiendas</label><input name="store_count" type="number" min="1" value="${value("store_count",p.census_store_count||p.store_count||"")}"/></div><div class="field"><label>CAPA</label><input name="capa" type="number" min="0" step="0.01" value="${value("capa",p.capa||"")}"/></div></div>
    </section>
    <section class="form-card"><h2>Contacto</h2><div class="field"><label>Teléfono</label><input name="phone" value="${value("phone",p.phone||"")}"/></div><div class="field"><label>Móvil</label><input name="mobile" value="${value("mobile",p.mobile||"")}"/></div><div class="field"><label>Email</label><input name="email" type="email" value="${value("email",p.email||"")}"/></div><div class="field"><label>Dirección</label><input name="street" value="${value("street",p.street||"")}"/></div><div class="field"><label>Ciudad</label><input name="city" value="${value("city",p.city||"")}"/></div><div class="field"><label>Especialidad / descripción</label><input name="business_description" value="${value("business_description",p.business_description||"")}"/></div></section>
    <section class="form-card"><h2>Clasificación</h2><div class="field"><label>Canal comercial</label><select name="customer_segment"><option value="">Seleccione…</option>${[["wholesaler","Mayorista"],["reseller","Revendedor / distribuidor"],["retail","Tienda al detalle"],["mixed","Mixto"],["other","Otro"]].map(([k,v])=>`<option value="${k}" ${(d.customer_segment??p.customer_segment)===k?"selected":""}>${v}</option>`).join("")}</select></div>${catalogChecks("business_type_ids",state.catalog.business_types,d.business_type_ids||p.business_type_ids||[])}<h2 class="sub-section">Marcas (opcional)</h2>${catalogChecks("mobile_brand_ids",state.catalog.mobile_brands,d.mobile_brand_ids||p.mobile_brand_ids||[])}</section>
    ${hoursSection(hours)}
    <div class="sticky-actions"><button type="button" class="btn btn-secondary" data-action="cancel-edit">Cancelar</button><button type="submit" class="btn btn-primary">Guardar cambios</button></div>
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
  if (state.editHoursTouched) {
    obj.opening_hours = hourRows(form);
    if (!validateHours(obj.opening_hours)) return;
  }
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
  if(state.sessionMismatch) {
    $app.innerHTML=`<div class="boot-screen session-warning"><div class="boot-logo">!</div><strong>Cambio de usuario o empresa</strong><p>Los catastros y las operaciones offline de la sesión anterior permanecen en este dispositivo. Para evitar enviarlos desde otra cuenta, la sincronización está detenida.</p><p>Inicia sesión con el usuario y empresa anteriores para enviarlos. Si ya no necesitas estos datos, puedes eliminarlos de este dispositivo.</p><button type="button" class="btn btn-danger" data-action="clear-local">Borrar datos locales</button><a href="/web" class="btn btn-secondary">Volver a Odoo</a></div>`;
    return;
  }
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
function validateHours(hours) {
  const byDay=new Map();
  const minutes=(text,end=false)=>{
    const match=/^([01]\d|2[0-4]):([0-5]\d)$/.exec(String(text||""));
    if(!match)return NaN;
    const n=Number(match[1])*60+Number(match[2]);
    return n<=1440 && (!(!end && n>=1440)) && (n!==1440 || match[2]==="00") ? n : NaN;
  };
  for (const row of hours) {
    if (!row.from || !row.to || row.day===undefined || row.day===null || row.day==="") { alert("Complete el día y las horas de cada horario."); return false; }
    const start=minutes(row.from),finish=minutes(row.to,true);
    if (!Number.isFinite(start) || !Number.isFinite(finish) || start>=finish) { alert("Revise apertura y cierre (HH:MM). El cierre debe ser posterior a la apertura."); return false; }
    const ranges=byDay.get(row.day)||[];
    if (ranges.some(([from,to])=>start < to && finish > from)) {
      alert("Hay horarios superpuestos el mismo día. Corrija las franjas."); return false;
    }
    ranges.push([start,finish]);byDay.set(row.day,ranges);
  }
  if (hours.length && state.meta?.capabilities?.opening_hour_model===false) {
    alert("No se puede guardar horarios: el módulo base no reporta campos compatibles. Contacte al administrador."); return false;
  }
  return true;
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
  obj.opening_hours = hourRows(form);
  if (!validateHours(obj.opening_hours)) return;
  const candidate=state.newCandidate;
  if (state.requestCandidate) { alert("Hay un cliente asignado a otro comercial. Solicite su reasignación antes de crear otro catastro."); return; }
  if (candidate) {
    if (candidate.can_use===false || truthy(candidate.census_locked)) { alert("Este cliente no está disponible para editar. Solicite asignación o habilitación."); return; }
    const normalized=(v)=>String(v||"").toUpperCase().replace(/[^A-Z0-9]/g, "");
    if (candidate.vat && normalized(candidate.vat)!==normalized(obj.vat)) {
      if (!confirm("El RUC/cédula es diferente al del cliente seleccionado. ¿Desea continuar y modificar ese cliente?")) return;
    }
    obj.partner_id=candidate.id;
    obj.base_write_date=candidate.write_date || "";
    obj.activate_census=true;
  }
  const op = await queueOperation(candidate?"catastro_update":"catastro", obj, `${obj.commercial_name || obj.name} · ${obj.vat}`);
  state.newCandidate=null;state.newDraft={};state.searchMatches=[];state.requestCandidate=null;
  state.page = "pending";
  render();
  if (navigator.onLine) await syncPending(false, [op.uuid]);
}

async function submitVisit(form, finalize=true) {
  const obj = formObject(form);
  const partner = state.partners.find(p=>p.id===Number(obj.partner_id));
  if (!partner) { alert("Seleccione un catastro."); return; }
  for (const name of ["purchase_made","has_stock","no_credit_subject","reschedule_visit"]) obj[name] = obj[name] === "true";
  obj.other_result=Boolean(String(obj.other_result_detail||"").trim());
  if (obj.next_visit_datetime) obj.next_visit_datetime=localDateTimeToUTC(obj.next_visit_datetime);
  obj.partner_id = Number(obj.partner_id);
  obj.visit_datetime = nowServerString();
  obj.finalize = finalize;
  const op = await queueOperation("visit", obj, `${partnerLabel(partner)} · ${finalize?"Finalizar":"Borrador"}`);
  state.page = "pending";
  render();
  if (navigator.onLine) await syncPending(false, [op.uuid]);
}

async function syncPending(silent=false, onlyUuids=null) {
  if (!navigator.onLine || state.syncing || state.sessionMismatch || !state.meta?.user) return;
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
  await hydrateLocalState(); state.sessionMismatch=false;state.page="home"; render();
  if(navigator.onLine) await refreshFromServer(false);
}

$app.addEventListener("input", (event) => {
  if (event.target?.id === "partner-search") {
    state.search = event.target.value;
    const q=normalizedMatch(state.search.trim());
    const list=state.partners.filter(p=>!q || [p.name,p.commercial_name,p.vat,p.city,p.phone,p.mobile].some(v=>normalizedMatch(v).includes(q)));
    const results=document.querySelector("#home-results");if(results)results.innerHTML=list.map(partnerCard).join("")||`<div class="empty">No se encontraron catastros.</div>`;
    const count=document.querySelector("#result-count");if(count)count.textContent=`${list.length} catastros`;
    return;
  }
  const form=event.target.closest("#catastro-form, #catastro-edit-form");
  if (!form) return;
  if (form.id==="catastro-form") {
    captureDraft(form);
    if (event.target.id==="client-match-input" || ["name","vat"].includes(event.target.name)) {
      searchPotentialMatches(event.target.value);
    }
    if (state.newCandidate && event.target.name==="vat") {
      const a=String(state.newCandidate.vat||"").replace(/\W/g,"");
      const b=String(event.target.value||"").replace(/\W/g,"");
      if (a && a!==b) {state.newCandidate=null;document.querySelector("#existing-selection").innerHTML="";}
    }
  } else {
    if (event.target.closest(".hour-row")) state.editHoursTouched=true;
    captureDraft(form,true);
  }
});
$app.addEventListener("change", (event)=>{
  const form=event.target.closest("#catastro-form, #catastro-edit-form");
  if (form) {
    if (form.id==="catastro-edit-form" && event.target.closest(".hour-row")) state.editHoursTouched=true;
    captureDraft(form,form.id==="catastro-edit-form");
  }
});

$app.addEventListener("click", async (event) => {
  const navEl = event.target.closest("[data-nav]");
  if (navEl) { state.page=navEl.dataset.nav; if(state.page!=="detail") state.selectedPartnerId=state.page==="visit"?state.selectedPartnerId:null; render(); return; }
  const partnerEl = event.target.closest("[data-open-partner]");
  if (partnerEl) { state.selectedPartnerId=Number(partnerEl.dataset.openPartner); state.page="detail"; render(); return; }
  const visitEl = event.target.closest("[data-action='visit-partner']");
  if (visitEl) { state.selectedPartnerId=Number(visitEl.dataset.id); state.page="visit"; render(); return; }
  const match=event.target.closest("[data-use-match]");
  if (match) {const p=candidateById(Number(match.dataset.useMatch));if(p)chooseMatch(p);return;}
  const action = event.target.closest("[data-action]")?.dataset.action;
  if (action === "refresh") { await syncPending(true); await refreshFromServer(true); return; }
  if (action === "new-catastro") { state.newDraft={};state.newCandidate=null;state.requestCandidate=null;state.searchMatches=[];state.lookupNotice="";state.page="new"; render(); return; }
  if (action === "edit-partner") { if(!truthy(selectedPartner()?.census_can_edit_master)){alert("Debe contar con permiso de edición vigente.");return;}state.editDraft=null;state.editHoursTouched=false;state.page="edit"; render(); return; }
  if (action === "deselect-match") { state.newCandidate=null;const el=document.querySelector("#existing-selection");if(el)el.innerHTML="";const btn=document.querySelector('#catastro-form [type="submit"]');if(btn)btn.textContent="Guardar catastro";return; }
  if (action === "add-hour" || action === "remove-hour") {
    const form=event.target.closest("form");if(!form)return;
    const rows=hourRows(form);
    if (form.id==="catastro-edit-form") state.editHoursTouched=true;
    if (action==="add-hour") rows.push({day:hourDays()[0]?.value||"0",from:"09:00",to:"18:00"});
    else rows.splice(Number(event.target.closest(".hour-row")?.dataset.hourRow),1);
    captureDraft(form,form.id==="catastro-edit-form");
    const container=form.querySelector("[data-hours-container]");
    if (container) { const template=document.createElement("div");template.innerHTML=hourEditor(rows);container.innerHTML=template.querySelector("[data-hours-container]").innerHTML; }
    captureDraft(form,form.id==="catastro-edit-form");
    return;
  }
  if (action === "cancel-edit") { state.editDraft=null;state.page="detail"; render(); return; }
  if (action === "request-unlock") { document.querySelector("#unlock-reason")?.focus();return; }
  if (action === "send-unlock") {
    const reason=document.querySelector("#unlock-reason")?.value?.trim()||"";
    const p=selectedPartner();
    if(!p || !state.online){alert("Necesita conexión para solicitar la habilitación.");return;}
    try{await rpc("/conedera/app/request_unlock",{partner_id:p.id,reason});alert("Solicitud enviada al supervisor.");await refreshFromServer(false);}catch(err){alert(err.message||String(err));}return;
  }
  if (action === "send-reassignment") {
    const p=state.requestCandidate;const reason=document.querySelector("#reassign-reason")?.value?.trim()||"";
    if(!p || !state.online){alert("Necesita conexión para solicitar reasignación.");return;}
    try{await rpc("/conedera/app/request_reassignment",{partner_id:p.id,reason});state.requestCandidate=null;state.lookupNotice="Solicitud enviada. El supervisor debe aprobarla para poder usar este cliente.";document.querySelector("#reassignment-form").innerHTML="";document.querySelector("#lookup-notice").textContent=state.lookupNotice;}catch(err){alert(err.message||String(err));}return;
  }
  if (action === "close-reassignment") {state.requestCandidate=null;document.querySelector("#reassignment-form").innerHTML="";return;}
  if (action === "capture-gps") {
    if(!navigator.geolocation){alert("Este dispositivo no dispone de geolocalización.");return;}
    const button=event.target.closest("button");button.disabled=true;
    const status=document.querySelector("#gps-status");if(status)status.textContent="Obteniendo ubicación…";
    navigator.geolocation.getCurrentPosition(pos=>{
      const payload=JSON.stringify({latitude:pos.coords.latitude,longitude:pos.coords.longitude,accuracy:pos.coords.accuracy});
      const form=button.closest("form");const target=form?.elements.namedItem(form.id==="visit-form"?"gps_payload":"census_gps_payload");if(target){target.value=payload;if(form.id!=="visit-form")captureDraft(form);}if(status)status.textContent=`GPS capturado · precisión ${Math.round(pos.coords.accuracy)} m`;button.disabled=false;
    },err=>{if(status)status.textContent=`GPS no disponible: ${err.message}`;button.disabled=false;},{enableHighAccuracy:true,timeout:16000,maximumAge:30000});return;
  }
  if (action === "sync") { await syncPending(false); return; }
  if (action === "save-visit-offline") { const form=document.querySelector("#visit-form"); if(form) await submitVisit(form,false); return; }
  if (action === "clear-local") { await clearLocal(); return; }
  if (action === "install" && installPrompt) { installPrompt.prompt(); await installPrompt.userChoice; installPrompt=null; render(); return; }
  const del = event.target.closest("[data-delete-pending]");
  if (del) { const id=del.dataset.deletePending; const op=state.pending.find(x=>x.uuid===id); if(op?.state==="synced" || confirm("Eliminar esta operación pendiente del dispositivo?")){await idbDelete(STORE_PENDING,id); await hydrateLocalState(); render();} }
  const toggle = event.target.closest("[data-toggle]");
  if (toggle) { const name=toggle.dataset.toggle; const value=toggle.dataset.value; const form=toggle.closest("form"); form.querySelector(`[name="${name}"]`).value=value; form.querySelectorAll(`[data-toggle="${name}"]`).forEach(el=>el.classList.toggle("active",el.dataset.value===value)); }
});

$app.addEventListener("keydown", (event)=>{
  if ((event.key==="Enter" || event.key===" ") && event.target.matches("[data-open-partner]")) {event.preventDefault();event.target.click();}
});
$app.addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    if (event.target.id === "catastro-form") await submitCatastro(event.target);
    if (event.target.id === "catastro-edit-form") await submitCatastroUpdate(event.target);
    if (event.target.id === "visit-form") await submitVisit(event.target,true);
  } catch (err) {alert(err.message||String(err));}
});

async function init() {
  db = await openDb();
  await hydrateLocalState();
  render();
  if (window.isSecureContext && "serviceWorker" in navigator) {
    try { await navigator.serviceWorker.register("/conedera/sw.js", { scope: "/conedera/" }); } catch (err) { console.warn("Service worker no disponible", err); }
  }
  if (navigator.onLine) {
    await refreshFromServer(false);
    if(!state.sessionMismatch) await syncPending(true);
  }
}

init().catch((err) => {
  console.error(err);
  $app.innerHTML = `<div class="boot-screen"><div class="boot-logo">!</div><strong>No se pudo iniciar la app</strong><span>${esc(err.message||err)}</span><a class="btn btn-primary" href="/web">Volver a Odoo</a></div>`;
});
