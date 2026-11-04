const APP_VERSION = "18.0.1.5.9";
const DB_NAME = "conedera-field-app";
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
  storageError: "",
  localReady: false,
  serverSnapshot: null,
  starting: true,
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
  quoteSelections: {},
  quoteWarehouseId: null,
  quotePricelistId: null,
  quotePriceTimer: null,
  quotePriceRequest: 0,
  quoteImageZoom: 1,
  quotePaymentOptionId: null,
  quoteLoyaltyCode: "",
  quoteRetail: false,
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
  // No solicitar cambios de esquema al inicio: las bases previas pueden contener
  // catastros, visitas o cotizaciones sin sincronizar. Esta apertura es asíncrona
  // y NO tiene un tiempo límite artificial que genere fallos falsos.
  return new Promise((resolve, reject) => {
    let req;
    try { req = indexedDB.open(DB_NAME); }
    catch (error) { reject(error); return; }
    req.onblocked = () => {
      // Una pestaña anterior puede completar una transacción. Esperamos sin
      // declarar falsamente que el almacenamiento está averiado.
      console.info("Catastro: esperando acceso a IndexedDB; la pantalla sigue disponible.");
    };
    req.onupgradeneeded = () => {
      const local = req.result;
      const stores = [
        [STORE_META, "key"], [STORE_PARTNERS, "id"],
        [STORE_PENDING, "uuid"], [STORE_VISITS, "id"],
        [STORE_ORDERS, "id"], [STORE_PRODUCTS, "key"],
        [STORE_CATALOG, "key"],
        [STORE_QUOTE_PRODUCTS, "key"], [STORE_QUOTE_DETAILS, "key"],
      ];
      for (const [name, keyPath] of stores) {
        if (!local.objectStoreNames.contains(name)) local.createObjectStore(name, { keyPath });
      }
    };
    req.onsuccess = () => {
      const opened = req.result;
      opened.onversionchange = () => {
        // Otra versión necesita actualizar el esquema. No bloquearla.
        opened.close();
        if (db === opened) {
          db = null;
          state.localReady = false;
          setTimeout(() => { if (!state.localReady) void restoreLocalStorage(); }, 750);
        }
      };
      resolve(opened);
    };
    req.onerror = () => reject(req.error || new Error("No se pudo abrir la base de datos local."));
  });
}

function tx(store, mode = "readonly") {
  if (!db) throw new Error("El almacenamiento local no está disponible.");
  return db.transaction(store, mode).objectStore(store);
}
function quoteLegacyPrefix(store) { return `quote-cache:${store}:`; }
function isLegacyQuoteStore(store) {
  return store === STORE_QUOTE_PRODUCTS || store === STORE_QUOTE_DETAILS;
}
function legacyQuoteStore(store) {
  return Boolean(db && isLegacyQuoteStore(store) && !db.objectStoreNames.contains(store));
}
function idbGetAll(store) {
  if (legacyQuoteStore(store)) {
    // Las instalaciones v1 no tienen estas dos stores. Reutilizar meta evita
    // una migracion forzosa y conserva la cola offline existente.
    return idbGetAll(STORE_META).then(rows => rows
      .filter(row => String(row.key || "").startsWith(quoteLegacyPrefix(store)))
      .map(row => row.value));
  }
  return new Promise((resolve, reject) => {
    const req = tx(store).getAll();
    req.onsuccess = () => resolve(req.result || []);
    req.onerror = () => reject(req.error);
  });
}
function idbGet(store, key) {
  if (legacyQuoteStore(store)) {
    return idbGet(STORE_META, quoteLegacyPrefix(store) + key).then(row => row?.value || null);
  }
  return new Promise((resolve, reject) => {
    const req = tx(store).get(key);
    req.onsuccess = () => resolve(req.result || null);
    req.onerror = () => reject(req.error);
  });
}
function idbPut(store, value) {
  if (legacyQuoteStore(store)) {
    return idbPut(STORE_META, {key:quoteLegacyPrefix(store) + value.key, value}).then(() => value);
  }
  return new Promise((resolve, reject) => {
    const req = tx(store, "readwrite").put(value);
    req.onsuccess = () => resolve(value);
    req.onerror = () => reject(req.error);
  });
}
function idbDelete(store, key) {
  if (legacyQuoteStore(store)) return idbDelete(STORE_META, quoteLegacyPrefix(store) + key);
  return new Promise((resolve, reject) => {
    const req = tx(store, "readwrite").delete(key);
    req.onsuccess = () => resolve();
    req.onerror = () => reject(req.error);
  });
}
function idbReplaceAll(store, values) {
  if (legacyQuoteStore(store)) {
    return idbGetAll(STORE_META).then(async rows => {
      for (const row of rows.filter(row => String(row.key || "").startsWith(quoteLegacyPrefix(store))))
        await idbDelete(STORE_META, row.key);
      for (const value of values) await idbPut(store, value);
    });
  }
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
  // Una petición colgada no debe dejar la interfaz en "Sincronizando" indefinidamente.
  // Los cambios se reintentan por UUID en Odoo para evitar duplicados.
  const timeout = url.endsWith("/sync") ? 90000 : url.endsWith("/bootstrap") ? 50000 : 30000;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);
  try {
    const res = await fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ jsonrpc: "2.0", method: "call", params, id: Date.now() }),
      signal: controller.signal,
    });
    if (!res.ok) {
      if (res.status === 401 || res.status === 403) throw new Error("Sesión vencida. Vuelva a iniciar sesión en Odoo.");
      throw new Error(`Servidor no disponible (${res.status}).`);
    }
    const type = res.headers.get("content-type") || "";
    if (res.redirected || !type.toLowerCase().includes("json")) {
      throw new Error("Odoo devolvió una página en lugar de datos. Compruebe que su sesión esté activa e inicie sesión de nuevo.");
    }
    const body = await res.json();
    if (body.error) throw new Error(body.error?.data?.message || body.error?.message || "Error del servidor");
    return body.result;
  } catch (err) {
    if (err?.name === "AbortError") throw new Error("Odoo tardó demasiado en responder. Revise la conexión y vuelva a sincronizar; los registros pendientes siguen guardados.");
    throw err;
  } finally {
    clearTimeout(timer);
  }
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

function applyBootstrapInMemory(data) {
  // Consulta online disponible incluso si IndexedDB falla.
  state.partners = data.partners || [];
  state.visits = data.visits || [];
  state.orders = data.orders || [];
  state.products = (data.products || []).map((x, idx) => ({ ...x, key:`${x.partner_id}-${x.product_id}-${idx}` }));
  state.meta = {user:data.user, capabilities:data.capabilities, server_time:data.server_time, saved_at:new Date().toISOString()};
  state.catalog = {teams:data.teams || [], business_types:data.business_types || [], mobile_brands:data.mobile_brands || []};
}
async function refreshFromServer(showMessage = true, prefetchedBootstrap = null) {
  if (!navigator.onLine || state.syncing) return;
  try {
    state.syncing = true;
    render();
    const data = prefetchedBootstrap || await rpc("/catastro/app/bootstrap");
    if (state.meta?.user && (Number(state.meta.user.id)!==Number(data.user.id) || Number(state.meta.user.company_id)!==Number(data.user.company_id)) && state.pending.some(x=>!["synced","warning","conflict"].includes(x.state))) {
      state.sessionBlocked=true;
      throw new Error("Hay operaciones de otra sesión en este dispositivo. Vuelva al usuario y compañía originales para sincronizar; no se mezclaron datos.");
    }
    state.sessionBlocked=false;
    state.serverSnapshot = data;
    if (db && state.localReady) {
      try {
        await persistBootstrap(data);
        await hydrateLocalState();
        state.storageError = "";
      } catch (storageFailure) {
        // Un fallo al escribir la copia offline no invalida los datos en Odoo.
        // Nunca borrar ni recrear IndexedDB, ni detener la interfaz.
        console.warn("No se pudo actualizar la copia local", storageFailure);
        state.storageError = storageFailure.message || String(storageFailure);
        applyBootstrapInMemory(data);
      }
    } else {
      applyBootstrapInMemory(data);
    }
    state.lastError = "";
  } catch (err) {
    state.lastError = err.message || String(err);
    if (showMessage) console.warn(err);
  } finally {
    state.syncing = false;
    state.starting = false;
    render();
  }
}

function connectionBanner() {
  // El almacenamiento se inicializa en segundo plano. Evitar avisos rojos
  // persistentes por una apertura lenta; registrar detalles técnicos en «Más».
  if (state.starting && !state.partners.length) return `<div class="connection"><span><i class="dot"></i>Conectando con Odoo…</span></div>`;
  if (state.sessionBlocked) return `<div class="connection error">Operaciones de otra sesión: sincronización bloqueada para proteger los datos.</div>`;
  if (state.syncing) return `<div class="connection"><span><i class="dot"></i>Sincronizando…</span><span>${state.pending.filter(x=>x.state!=="synced").length} pendientes</span></div>`;
  if (!state.online) return `<div class="connection offline"><span><i class="dot"></i>Sin cobertura / offline</span><span>${state.localReady?"Los datos quedan en este dispositivo":"Almacenamiento local aún no disponible; evite guardar cambios"}</span></div>`;
  if (state.lastError) return `<div class="connection error"><span><i class="dot"></i>${esc(state.lastError)}</span><button class="btn btn-outline" style="min-height:34px;padding:4px 9px" data-action="refresh">Reintentar</button></div>`;
  return `<div class="connection"><span><i class="dot"></i>En línea</span><span>${state.pending.filter(x=>x.state!=="synced").length} pendientes</span></div>`;
}

function nav(active, desktop=false) {
  const item = (page, icon, label) => `<button class="nav-btn ${active===page?"active":""}" data-nav="${page}"><b>${icon}</b><span>${label}</span></button>`;
  const retailOnly=state.meta?.capabilities?.census_role===false;
  return `<nav class="${desktop?"side-nav":"bottom-nav"}" aria-label="Navegación">${item("home","⌂",retailOnly?"Tienda":"Catastros")}${retailOnly?'':item("visit","＋","Visita")}${item("pending","⇅","Pendientes")}${item("more","•••","Más")}${desktop?'<a class="nav-btn" href="/web" target="_blank" rel="noopener"><b>▦</b><span>Abrir Odoo</span></a>':""}</nav>`;
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
  const retail=state.meta?.capabilities?.quote_retail_partner;
  const retailButton=state.meta?.capabilities?.quote_retail_enabled
    ?`<section class="partner-quote-cta"><div><strong>Venta directa · Consumidor Final</strong><p>Crear proforma sin catastro. Precios de lista, promociones Loyalty y recargos por condición de pago.</p></div><button class="btn btn-primary" type="button" data-action="quote-retail">▤ Cotizar consumidor final</button></section>`:"";
  const isCensus=state.meta?.capabilities?.census_role!==false;
  const body = `${retailButton}${isCensus?`<div class="home-tools"><span>Mis clientes</span><button type="button" class="btn btn-outline" data-action="new-catastro">＋ Nuevo catastro</button></div>
    <input id="partner-search" class="search" placeholder="Buscar por RUC, nombre, ciudad…" value="${esc(state.search)}"/>
    <div class="cards">${partners.map(partnerCard).join("") || `<div class="empty"><b>No hay catastros en el dispositivo</b>${state.online?"Pulse actualizar o cree uno nuevo.":"Conéctese una vez para descargar sus catastros."}</div>`}</div>`:''}`;
  $app.innerHTML = shell(state.meta?.capabilities?.census_role===false?"Cotizador de tienda":"Mis catastros", body, { fab:state.meta?.capabilities?.census_role!==false, nav:"home" });
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
    <section class="partner-quote-cta" aria-label="Cotización para este catastro">
      <div><strong>Proformas y cotizaciones</strong><p>${locked?"Crear una cotización para este cliente y consultar sus proformas.":"Para cotizar primero debe finalizar y proteger este catastro."}</p></div>
      <button type="button" class="btn btn-primary partner-quote-button" data-action="quote-partner" data-id="${p.id}" ${locked?"":"disabled"}>▤ Crear cotización</button>
    </section>
    ${detailWorkflow(p)}
    <div class="section-title">Operación comercial</div><div class="action-grid"><button class="btn btn-primary" data-action="visit-partner" data-id="${p.id}" ${locked?"":"disabled"}>＋ Nueva visita</button><a class="btn btn-outline" href="/web#id=${p.id}&model=res.partner&view_type=form" target="_blank" rel="noopener">Abrir en Odoo</a></div>
    <div class="section-title">Bitácora reciente</div><section class="card">${timeline(p.id)}</section></div>
    <div class="detail-secondary"><div class="section-title">Contacto</div><section class="card"><div class="card-sub">${esc(p.phone||p.mobile||"Sin teléfono")}<br>${esc(p.email||"Sin email")}<br>${esc(partnerAddress(p)||"Sin dirección")}</div><div class="section-title">Horario de atención</div>${hoursSummary(p)}</section>
    <div class="section-title">Productos proformados</div><section class="card">${prod.length?prod.map(x=>`<div class="product-row"><div><strong>${esc(x.product_name)}</strong><br><span>${x.lines} líneas · promedio ${money(x.avg_price)}</span></div><div style="text-align:right"><strong>${money(x.qty)}</strong><br><span>${money(x.subtotal)}</span></div></div>`).join(""):`<div class="empty">Sin productos almacenados todavía.</div>`}</section></div></div>`;
  $app.innerHTML = shell(partnerLabel(p), body, {nav:"home"});
}

function quoteCanCreate() {
  return Boolean(state.meta?.capabilities?.quote_create);
}
function quotePartner() { return state.partners.find(p=>p.id===Number(state.quotePartnerId))
  || (state.quoteRetail&&Number(state.quotePartnerId)===Number(state.meta?.capabilities?.quote_retail_partner?.id)?state.meta.capabilities.quote_retail_partner:null); }
function nativeQuotationsUrl() {
  const action=Number(state.meta?.capabilities?.sales_action_id||0);
  return action>0?`/web#action=${action}&model=sale.order&view_type=list`:'/web';
}
function quoteSelectionCount(){return Object.keys(state.quoteSelections).length;}
function quoteImage(product, large=false) {
  if (!product?.has_image) return '<span class="quote-no-photo" aria-hidden="true">▧</span>';
  const url=large?product.zoom_url:product.image_url;
  return `<img src="${esc(url)}" alt="${esc(product.name)}" loading="lazy" />`;
}
function quoteStock(product){
  if(product.stock_kind==='not_applicable') return 'Stock: no aplica a servicios';
  if(product.stock_qty === null || product.stock_qty === undefined) return 'Stock a mano: no disponible';
  const shortage=product.qty && Number(product.stock_qty)<Number(product.qty)?' · ⚠ stock menor a cantidad':'';
  return `A mano: ${money(product.stock_qty)} ${esc(product.uom||'')} · ${esc(product.stock_label||'')}${shortage}`;
}
function quoteListPrice(product){
  if (product.price === null || product.price === undefined) return 'Precio por consultar en Odoo';
  return `Precio lista: ${esc(product.currency||'')} ${money(product.price)}`;
}
function availableQuoteProducts(term) {
  const user=state.meta?.user;
  if (!user) return [];
  if (!state.quoteWarehouseId) return [];
  const q=String(term||"").trim().toLowerCase();
  return state.quoteProducts.filter(p=>Number(p.stock_qty)>0 && ['available','physical'].includes(p.stock_kind) &&Number(p.user_id)===Number(user.id) && Number(p.company_id)===Number(user.company_id)
    && Number(p.partner_id)===Number(state.quotePartnerId) && Number(p.warehouse_id||0)===Number(state.quoteWarehouseId||0) && Number(p.pricelist_id||0)===Number(state.quotePricelistId||0)
    && [p.name,p.code].some(x=>String(x||"").toLowerCase().includes(q))).slice(0,35);
}
function renderQuoteResults() {
  const box=document.querySelector("#quote-search-results"); if (!box) return;
  const found=state.quoteResults.filter(p=>Number(p.stock_qty)>0 && ['available','physical'].includes(p.stock_kind) && Number(p.warehouse_id)===Number(state.quoteWarehouseId));
  const rows=found.map(p=>{
    const chosen=state.quoteSelections[p.id];
    return `<article class="quote-search-product">
      <button type="button" class="quote-thumb" data-action="quote-image" data-id="${p.id}" title="Ampliar fotografía" ${p.has_image?'':'disabled'}>${quoteImage(p)}</button>
      <div class="quote-search-main"><strong>${esc(p.name)}</strong><small>${esc(p.code||p.uom||'')}</small>
        <div class="quote-product-price">${quoteListPrice(p)}</div><div class="quote-product-stock">Lista: ${esc(p.pricelist||'Sin identificar')} · ${quoteStock(p)}</div>
      </div>
      <div class="quote-search-choose"><label class="quote-checkbox"><input type="checkbox" data-quote-select="${p.id}" ${chosen?'checked':''}/> Seleccionar</label>
      <label>Cantidad <input type="number" data-quote-search-qty="${p.id}" step="any" min="0.001" max="100000" inputmode="decimal" value="${esc(chosen?.qty??1)}"/></label>
      <button type="button" class="btn btn-outline quote-one" data-action="quote-add-product" data-id="${p.id}">＋ Agregar</button></div>
    </article>`;
  }).join('');
  box.innerHTML=`${state.quoteSearching?'<div class="small">Actualizando precio y stock desde Odoo…</div>':''}
    ${!state.quoteWarehouseId?'<div class="small">Seleccione una bodega para buscar productos con stock.</div>':
    !state.quoteSearch.trim()?'<div class="small">Busque por nombre o código. Solo aparecerán productos con stock a mano mayor que cero en esta bodega.</div>':
    found.length?rows:`<div class="small">No hay productos con stock físico positivo en las ubicaciones internas de esta bodega ${state.online?'':'(según la última consulta guardada)'}. Si Inventario muestra otra cifra, revise la variante y la ubicación raíz del almacén.</div>`}
    ${quoteSelectionCount()?`<div class="quote-batch"><strong>${quoteSelectionCount()} seleccionado(s)</strong><button class="btn btn-primary" type="button" data-action="quote-add-selected">Agregar seleccionados</button></div>`:''}`;
}
function quoteLinePriceMarkup(line) {
  return `<div class="quote-price-info" data-quote-price-info="${line.id}"><span>${quoteListPrice(line)} <small>para ${esc(line.qty)} ${esc(line.uom||'')} · lista ${esc(line.pricelist||'sin confirmar')}</small></span><span>${quoteStock(line)}</span></div>`;
}
function quoteLinesMarkup() {
  return state.quoteLines.length?state.quoteLines.map(line=>`<div class="quote-line" data-quote-line="${line.id}">
    <button class="quote-thumb" type="button" data-action="quote-image" data-id="${line.id}" title="Ampliar foto" ${line.has_image?'':'disabled'}>${quoteImage(line)}</button>
    <div class="quote-line-name"><strong>${esc(line.name)}</strong><span>${esc(line.code||line.uom||'')}</span>${quoteLinePriceMarkup(line)}</div>
    <div class="quote-line-controls"><label>Cantidad<input type="number" inputmode="decimal" min="0.001" max="100000" step="any" value="${esc(line.qty)}" data-quote-qty="${line.id}" required/></label>
    ${state.meta?.capabilities?.quote_can_negotiate?`<label>Precio negociado (negotiable_price) · ${esc(line.currency||'moneda de lista')}<input type="number" data-quote-negotiable="${line.id}" inputmode="decimal" min="0" max="1000000000" step="any" placeholder="Sin negociar" value="${esc(line.negotiable_price??'')}" /></label>`:'<span class="small">Precio según lista de Odoo · negociación no autorizada para este perfil</span>'}
    <button type="button" class="icon-btn quote-remove" title="Quitar producto" aria-label="Quitar ${esc(line.name)}" data-action="quote-remove-product" data-id="${line.id}">×</button></div></div>`).join(''):
    `<div class="empty"><b>Sin productos</b>Busque y seleccione varios productos para esta cotización.</div>`;
}
function quoteTotals() {
  const rows=state.quoteLines;
  const currencies=new Set(rows.map(row=>String(row.currency||'')).filter(Boolean));
  const currency=currencies.size===1?[...currencies][0]:'';
  let list=0, negotiated=0, ready=rows.length>0, current=state.online;
  for(const line of rows){
    const qty=Number(line.qty), price=Number(line.price);
    if(line.price===null||line.price===undefined||!Number.isFinite(price)||!Number.isFinite(qty)||qty<=0){ ready=false;break; }
    const entered=line.negotiable_price===null||line.negotiable_price===undefined||String(line.negotiable_price).trim()===''
      ?price:Number(line.negotiable_price);
    if(!Number.isFinite(entered)||entered<0){ready=false;break;}
    list+=qty*price;
    negotiated+=qty*entered;
    if(Number(line.qty_priced)!==qty) current=false;
  }
  if(currencies.size>1)ready=false;
  return {list,negotiated,ready,current,currency};
}
function quoteTotalsMarkup(){
  const t=quoteTotals();
  const fmt=n=>t.ready?`${esc(t.currency)} ${money(n)}`:'Pendiente de calcular';
  const warning=!state.online?'Sin conexión: los valores son orientativos y stock/precios se validarán al sincronizar.':
    !t.current?'Actualizando precios según las cantidades seleccionadas…':'Valores referenciales sin impuestos; Odoo calculará el importe final de la proforma.';
  const option=(state.meta?.capabilities?.quote_payment_options||[]).find(x=>Number(x.id)===Number(state.quotePaymentOptionId));
  const estimatedFee=t.ready&&option ? Math.max(0,t.negotiated)*Number(option.surcharge_percent||0)/100 : null;
  return `<div class="quote-totals-grid">
    <div class="quote-total-card"><span>Total a precio de lista</span><strong data-total-list>${fmt(t.list)}</strong></div>
    <div class="quote-total-card negotiated"><span>Total a precio negociado</span><strong data-total-negotiated>${fmt(t.negotiated)}</strong></div>
  </div>${option?`<div class="status-banner">Recargo estimado por ${esc(option.name)}: ${t.ready?`${esc(t.currency)} ${money(estimatedFee)}`:'Pendiente'} (${esc(option.surcharge_percent)}%). No incluye impuestos ni ajustes Loyalty; Odoo calculará el recargo final sobre el subtotal posterior a promociones.</div>`:''}
  <div class="small">${warning} En líneas sin precio negociado se utiliza el precio de lista.</div>`;
}
function updateQuoteTotals(){
  const el=document.querySelector('#quote-totals');
  if(el)el.innerHTML=quoteTotalsMarkup();
}
function refreshQuoteLineMarkup() {
  const box=document.querySelector('#quote-lines');
  if (box) box.innerHTML=quoteLinesMarkup();
  updateQuoteTotals();
}
function addQuoteProduct(product, quantity=1) {
  const qty=Number(quantity);
  if (!Number.isFinite(qty)||qty<=0||qty>100000) {alert('Cantidad inválida para '+product.name);return false;}
  if(!state.quoteWarehouseId){alert('Seleccione una bodega primero.');return false;}
  if(!Number.isFinite(Number(product.stock_qty))||Number(product.stock_qty)<=0||Number(product.warehouse_id)!==Number(state.quoteWarehouseId)){
    alert('El producto no tiene stock consultado en esta bodega. Actualice la búsqueda.');return false;
  }
  const existing=state.quoteLines.find(x=>x.id===product.id);
  const requested=qty+(existing?Number(existing.qty):0);
  if(requested>Number(product.stock_qty)+1e-8){alert(`Stock insuficiente de ${product.name} en la bodega: ${money(product.stock_qty)} ${product.uom||''}.`);return false;}
  if(existing){existing.qty=requested;existing.qty_priced=requested===Number(existing.qty_priced)?existing.qty_priced:null;}
  else state.quoteLines.push({...product, qty, qty_priced:qty===Number(product.qty_priced)?qty:null, negotiable_price:null});
  return true;
}
async function refreshQuoteLinePrices() {
  if (!state.online||!state.quotePartnerId||!state.quoteWarehouseId||!state.quoteLines.length) return;
  const requestId=++state.quotePriceRequest;
  const partnerId=state.quotePartnerId;
  const wh=state.quoteWarehouseId, pricelistId=state.quotePricelistId;
  const payload=state.quoteLines.map(l=>({product_id:l.id,qty:l.qty}));
  try {
    const rows=await rpc('/catastro/app/quote/prices',{partner_id:partnerId,warehouse_id:wh,pricelist_id:pricelistId,lines:payload});
    if(requestId!==state.quotePriceRequest||partnerId!==state.quotePartnerId||wh!==state.quoteWarehouseId||pricelistId!==state.quotePricelistId) return;
    rows.forEach(row=>{
      const line=state.quoteLines.find(l=>l.id===row.id && Number(l.qty)===Number(row.qty_priced));
      if(line) Object.assign(line,{price:row.price,currency:row.currency,pricelist:row.pricelist,qty_priced:row.qty_priced,stock_qty:row.stock_qty,stock_kind:row.stock_kind,stock_label:row.stock_label,warehouse_id:row.warehouse_id});
    });
    if(state.page==='quote') {
      for (const line of state.quoteLines) {
        const el=document.querySelector(`[data-quote-price-info="${line.id}"]`);
        if(el) el.outerHTML=quoteLinePriceMarkup(line);
      }
      updateQuoteTotals();
    }
  } catch(err) {console.warn('No se pudo actualizar precio y stock:',err);state.lastError=err.message||String(err);updateQuoteTotals();}
}
function scheduleQuotePrices() {
  clearTimeout(state.quotePriceTimer);
  state.quotePriceTimer=setTimeout(()=>refreshQuoteLinePrices(),400);
}
function renderQuote() {
  const partner=quotePartner();
  const cap=state.meta?.capabilities||{};
  const clients=state.partners.filter(p=>truthy(p.census_locked) && (!p.census_company_id || relationId(p.census_company_id)===Number(state.meta?.user?.company_id)));
  const related=partner&&!state.quoteRetail?ordersFor(partner.id).slice(0,10):[];
  const linkedVisits=partner?visitsFor(partner.id).filter(v=>v.state==="done"):[];
  if (!state.quoteWarehouseId && (cap.quote_warehouses||[]).length===1)
    state.quoteWarehouseId=Number(cap.quote_warehouses[0].id);
  const availabilityNote=clients.length||state.quoteRetail?"":`<div class="status-banner warn">No hay catastros protegidos de la compañía actual para cotizar. Abre un catastro, completa los datos obligatorios y pulsa «Finalizar y proteger» antes de crear una cotización.</div>`;
  const permissionNote=cap.quote_create===false?`<div class="status-banner warn">Tu usuario no tiene permiso para crear cotizaciones en Odoo. Solicita al administrador los permisos correspondientes de Ventas. El acceso a esta pantalla sigue visible para que puedas identificar la causa.</div>`:"";
  if (!partner) { state.page="home"; return renderHome(); }
  const body=`${availabilityNote}${permissionNote}<div class="quote-layout"><form id="quote-form">
    <section class="form-card"><div class="row space"><h2>1. Cliente</h2><span class="chip">Empresa: ${esc(state.meta?.user?.company_name||"")}</span></div>
      <div class="quote-current-customer"><div><span>${state.quoteRetail?"Venta de tienda":"Catastro seleccionado"}</span><strong>${esc(partnerLabel(partner))}</strong><small>${esc(partner.vat||"Sin RUC/cédula")}</small></div><button type="button" class="btn btn-outline" data-action="back-to-partner">${state.quoteRetail?'Volver a tienda':'Volver al catastro'}</button></div>
      ${!state.quoteRetail?`<div class="field"><label>Vincular con visita (opcional)</label><select name="visit_id"><option value="">Sin visita asociada</option>${linkedVisits.map(v=>`<option value="${v.id}" ${Number(state.quoteVisitId)===v.id?"selected":""}>${esc(v.name||"Visita #"+v.id)} · ${esc(dateText(v.visit_datetime||v.visit_date||v.create_date))}</option>`).join("")}</select></div>`:''}
    </section>
    <section class="quote-mode-banner"><div><strong>Proforma rápida desde PWA</strong><p>Las promociones se calculan con el motor Loyalty de Odoo. Los recargos por condiciones de pago se añaden en una línea independiente, posterior a los descuentos.</p></div><a class="btn btn-outline" href="${nativeQuotationsUrl()}" target="_blank" rel="noopener" aria-label="Abrir cotizaciones completas en Odoo">Cotización completa en Odoo</a></section>
    <section class="form-card"><h2>2. Selección rápida de productos</h2>
      ${cap.quote_can_negotiate?`<div class="field"><label>Lista de precios de Odoo</label><select id="quote-pricelist"><option value="">Lista asignada al cliente (predeterminada)</option>${(cap.quote_pricelists||[]).map(pl=>`<option value="${pl.id}" ${Number(state.quotePricelistId)===pl.id?'selected':''}>${esc(pl.name)}</option>`).join('')}</select></div>`:'<div class="small">Se utilizará la lista de precios asignada al cliente por Odoo (sin edición de precios).</div>'}
      <div class="field"><label>Bodega obligatoria · stock y validación por producto ${cap.quote_stock_supported?'':'(inventario no disponible)'}</label>
      <select id="quote-warehouse" required><option value="">Seleccione una bodega</option>${(cap.quote_warehouses||[]).map(w=>`<option value="${w.id}" ${Number(state.quoteWarehouseId)===w.id?'selected':''}>${esc(w.name)}</option>`).join('')}</select></div>
      <div class="field"><label>Buscar por nombre o código (solo stock mayor a 0)</label><input id="quote-search" value="${esc(state.quoteSearch)}" placeholder="Nombre, código SKU" autocomplete="off" ${state.quoteWarehouseId?'':'disabled'}/></div>
      <div id="quote-search-results" class="quote-results" aria-live="polite"></div>
      <button class="btn btn-outline" type="button" data-action="quote-stock-audit" ${state.quoteSearch.trim().length>=2&&state.online?'':'disabled'}>Comprobar stock de la bodega</button>
      <div id="quote-stock-audit" class="small" aria-live="polite"></div>
      <div class="quote-lines-head"><strong>Productos agregados (${state.quoteLines.length})</strong></div><div id="quote-lines">${quoteLinesMarkup()}</div>
      <div id="quote-totals" class="quote-totals" aria-live="polite">${quoteTotalsMarkup()}</div>
      <div class="small">El precio de lista es una referencia según la lista asignada al cliente, la cantidad y moneda de Odoo. El precio negociado utiliza el campo existente negotiable_price de la línea en Odoo; su personalización determina el precio final y los descuentos. No se sobrescribe el precio unitario desde la PWA. Solo se muestran productos con stock positivo en la bodega indicada. Al guardar, Odoo comprueba nuevamente producto, bodega y cantidad. La cotización no reserva stock.</div>
      ${!state.online?'<div class="status-banner warn">Sin conexión: fotos y precios pueden no estar actualizados. Odoo recalculará al sincronizar.</div>':''}
    </section>
    <dialog id="quote-image-dialog" class="quote-image-dialog"><div class="quote-zoom-bar"><strong id="quote-zoom-name">Producto</strong><div class="quote-zoom-buttons"><button class="btn btn-outline" type="button" data-action="quote-zoom-out" aria-label="Reducir fotografía">−</button><span id="quote-zoom-level">100%</span><button class="btn btn-outline" type="button" data-action="quote-zoom-in" aria-label="Ampliar fotografía">＋</button><button class="btn btn-outline" type="button" data-action="quote-close-image">Cerrar ✕</button></div></div><div class="quote-zoom-body"><img id="quote-zoom-picture" alt="Foto del producto ampliada"/></div><small>Puede ampliar la foto con los controles de zoom del navegador o del dispositivo.</small></dialog><section class="form-card"><h2>3. Condiciones de pago y promociones</h2>
      <div class="field"><label>Condición de pago</label><select id="quote-payment-option"><option value="">Sin condición adicional</option>${(cap.quote_payment_options||[]).map(opt=>`<option value="${opt.id}" ${Number(state.quotePaymentOptionId)===Number(opt.id)?'selected':''}>${esc(opt.name)}${opt.surcharge_percent?` · recargo ${esc(opt.surcharge_percent)}%`:''}</option>`).join('')}</select></div>
      <div class="field"><label>Código de promoción / cupón Loyalty</label><input id="quote-loyalty-code" value="${esc(state.quoteLoyaltyCode)}" maxlength="100" placeholder="Opcional · código autorizado en Odoo" ${cap.quote_loyalty_supported?'':'disabled'}/></div>
      ${cap.quote_loyalty_supported?'<div class="small">Después de guardar, la ficha mostrará las recompensas disponibles para aplicar. Odoo valida las reglas, vigencia, cantidades, cliente y acumulación.</div>':'<div class="status-banner warn">Las promociones requieren instalar y activar sale_loyalty en Ventas.</div>'}
    </section><section class="form-card"><h2>4. Referencia</h2><div class="field"><label>Referencia del cliente (opcional)</label><input name="client_order_ref" maxlength="100" value="${esc(state.quoteClientRef)}" placeholder="Orden de compra o referencia externa"/></div>
      <div class="status-banner warn">La cotización se guardará como <b>borrador</b>. Revise los importes definitivos antes de enviarla o confirmarla.</div></section>
      <div class="sticky-actions quote-submit"><button class="btn btn-outline" type="button" data-action="back-to-partner">${state.quoteRetail?'Volver a tienda':'Volver al catastro'}</button><button class="btn btn-primary" type="submit" ${!cap.quote_create?"disabled":""}>▤ Guardar cotización${state.online?"":" offline"}</button></div>
    </form><aside class="quote-side"><section class="card"><div class="card-title">Cotizaciones del cliente</div><div class="card-sub">Historial visible según permisos de Odoo</div>
      ${related.length?related.map(o=>`<button class="quote-history" type="button" data-action="view-quote" data-id="${o.id}"><span><strong>${esc(o.name)}</strong><small>${esc(dateText(o.date_order))} · ${esc(o.state||"")}</small></span><b>${esc(relationName(o.currency_id)||"")} ${money(o.amount_total)}</b></button>`).join(""):'<div class="small" style="margin-top:10px">Seleccione un cliente para consultar sus proformas.</div>'}</section></aside></div>`;
  $app.innerHTML=shell("Cotizaciones",body,{nav:"quote"});renderQuoteResults();
}
function renderQuoteDetail() {
  const q=state.quoteDetail;
  if (!q) {state.page="quote";return renderQuote();}
  const body=`<div class="quote-layout"><section class="form-card"><div class="row space"><div><div class="eyebrow">Cotización</div><h2>${esc(q.name)}</h2><div class="card-sub">${esc(q.partner_name)} · ${esc(q.company_name)} · ${esc(dateText(q.date_order))}</div></div><span class="chip">${esc(q.state)}</span></div>
    <div class="section-title">Detalle de productos</div>${q.lines.map(l=>`<div class="quote-detail-line"><div><strong>${esc(l.product_name||l.name)}</strong><div class="small">${esc(l.qty)} ${esc(l.uom)} × ${esc(q.currency)} ${money(l.price_unit)}${l.discount?` · descuento ${esc(l.discount)}%`:""}${l.negotiable_price!==null&&l.negotiable_price!==undefined?` · negociable: ${esc(q.currency)} ${money(l.negotiable_price)}`:''}</div></div><strong>${esc(q.currency)} ${money(l.subtotal)}</strong></div>`).join("")}
    <div class="quote-total"><div><span>Subtotal</span><strong>${esc(q.currency)} ${money(q.amount_untaxed)}</strong></div><div><span>Impuestos</span><strong>${esc(q.currency)} ${money(q.amount_tax)}</strong></div><div class="grand"><span>Total</span><strong>${esc(q.currency)} ${money(q.amount_total)}</strong></div></div>
    <div class="status-banner">Condición de pago: ${esc(q.payment_option||'Estándar')} ${q.surcharge_percent?`· recargo ${esc(q.surcharge_percent)}% en línea aparte`:''}. Promociones y totales suministrados por Odoo.</div>
    ${q.state==='draft'&&q.loyalty_enabled?`<div class="loyalty-tools"><h3>Promociones y recompensas Loyalty</h3><div class="field"><label>Código promocional</label><input id="quote-detail-coupon" placeholder="Cupón o código descuento"/></div><div class="row"><button type="button" class="btn btn-outline" data-action="quote-apply-code">Aplicar código</button><button type="button" class="btn btn-outline" data-action="quote-update-rewards">Consultar recompensas</button></div>${(q.loyalty_rewards||[]).length?`<div class="quote-rewards">${q.loyalty_rewards.map(r=>`<div class="quote-reward"><strong>${esc(r.name)}</strong>${r.multi_product?`<select data-loyalty-product="${r.id}">${(r.products||[]).map(pr=>`<option value="${pr.id}">${esc(pr.name)}</option>`).join('')}</select>`:''}<button type="button" class="btn btn-secondary" data-action="quote-apply-reward" data-id="${r.id}">Aplicar recompensa</button></div>`).join('')}</div>`:'<p class="small">No hay recompensas reclamables en este momento; los descuentos automáticos se reflejan en el detalle del pedido.</p>'}</div>`:''}
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
    if (db) await idbPut(STORE_QUOTE_DETAILS,{key,value:quote}).catch(err => console.warn("Detalle sin cache offline",err));
    state.quoteDetail=quote;state.page="quote-detail";render();
  } catch(err){alert(err.message||String(err));}
}
async function searchQuoteProducts(value) {
  const term=String(value||"").trim();state.quoteSearch=value;
  if (!state.quoteWarehouseId){state.quoteResults=[];state.quoteSearching=false;renderQuoteResults();return;}
  if (term.length<2) {state.quoteResults=[];state.quoteSearching=false;renderQuoteResults();return;}
  state.quoteResults=availableQuoteProducts(term);state.quoteSearching=state.online;renderQuoteResults();
  if (!state.online || !state.quotePartnerId){state.quoteSearching=false;renderQuoteResults();return;}
  const partnerId=state.quotePartnerId, warehouseId=state.quoteWarehouseId, pricelistId=state.quotePricelistId;
  try {
    const result=await rpc("/catastro/app/quote/products",{term,partner_id:partnerId,warehouse_id:warehouseId,pricelist_id:pricelistId});
    if (!document.querySelector("#quote-search") || document.querySelector("#quote-search").value.trim()!==term ||
        partnerId!==state.quotePartnerId || warehouseId!==state.quoteWarehouseId || pricelistId!==state.quotePricelistId) return;
    const user=state.meta?.user||{};
    const tagged=result.map(p=>({...p,key:`${user.id}:${user.company_id}:${partnerId}:${warehouseId||0}:${pricelistId||0}:${p.id}`,
      user_id:user.id,company_id:user.company_id,partner_id:partnerId,warehouse_id:warehouseId||0,pricelist_id:pricelistId||0}));
    // Mostrar siempre los resultados del servidor aunque IndexedDB no acepte escrituras.
    state.quoteResults=result.filter(p=>Number(p.stock_qty)>0 && Number(p.warehouse_id)===Number(warehouseId));
    if (db) {
      try {
        for (const row of tagged) await idbPut(STORE_QUOTE_PRODUCTS,row);
        state.quoteProducts=await idbGetAll(STORE_QUOTE_PRODUCTS);
      } catch(storageErr) {
        console.warn('Catálogo en línea; caché no disponible:',storageErr);
        state.quoteProducts=[...state.quoteProducts.filter(p=>!tagged.some(t=>t.key===p.key)),...tagged];
      }
    } else {
      state.quoteProducts=[...state.quoteProducts.filter(p=>!tagged.some(t=>t.key===p.key)),...tagged];
    }
  } catch(err){state.quoteResults=availableQuoteProducts(term);state.lastError=err.message||String(err);}
  state.quoteSearching=false;renderQuoteResults();
}
async function submitQuote(form) {
  const p=quotePartner();
  if (!p||(!state.quoteRetail&&!truthy(p.census_locked))) {alert("Seleccione un catastro finalizado o el consumidor final autorizado.");return;}
  if (!state.quoteLines.length){alert("Agregue al menos un producto.");return;}
  if (!state.quoteWarehouseId){alert("Seleccione una bodega antes de guardar la cotización.");return;}
  const lines=state.quoteLines.map(x=>({product_id:Number(x.id),qty:Number(x.qty),
    negotiable_price:x.negotiable_price==null||String(x.negotiable_price).trim()===''?null:Number(x.negotiable_price)}));
  if(lines.some(x=>!Number.isInteger(x.product_id)||!Number.isFinite(x.qty)||x.qty<=0||x.qty>100000 ||
    (x.negotiable_price!==null && (!Number.isFinite(x.negotiable_price)||x.negotiable_price<0||x.negotiable_price>1000000000)))) {alert("Revise las cantidades y los precios negociados.");return;}
  for(const line of state.quoteLines){
    if(Number(line.warehouse_id)!==Number(state.quoteWarehouseId)||!Number.isFinite(Number(line.stock_qty))){
      alert(`No hay una consulta de stock válida de ${line.name} para esta bodega. Actualice precios y existencias.`);return;
    }
    if(Number(line.qty)>Number(line.stock_qty)+1e-8 || Number(line.stock_qty)<=0){
      alert(`Cantidad sin stock suficiente para ${line.name}: a mano ${money(line.stock_qty)} ${line.uom||''}.`);return;
    }
  }
  if (!state.meta?.user?.id) {alert("Sin sesión descargada. Conéctese para empezar.");return;}
  if (state.online && !quoteCanCreate()){alert("Su usuario necesita permiso para crear cotizaciones en Ventas.");return;}
  const totals=quoteTotals();
  const note=totals.ready?`Lista: ${totals.currency} ${money(totals.list)} · negociado estimado: ${totals.currency} ${money(totals.negotiated)}. `:'';
  if (!confirm(`¿Guardar cotización para ${partnerLabel(p)} con ${lines.length} producto(s) en la bodega seleccionada? ${note}Odoo volverá a validar stock y recalcular precios.`))return;
  const payload={partner_id:p.id,payment_option_id:state.quotePaymentOptionId||null,
    loyalty_code:state.quoteLoyaltyCode||'',visit_id:Number(form.querySelector('[name="visit_id"]')?.value||0),warehouse_id:state.quoteWarehouseId||null,pricelist_id:state.quotePricelistId||null,lines,
    client_order_ref:form.querySelector('[name="client_order_ref"]')?.value.trim()||""};
  const op=await queueOperation("quote",payload,`${partnerLabel(p)} · cotización de ${lines.length} productos`);
  if (!op) return;
  state.quoteLines=[];state.quoteSearch="";state.quoteResults=[];state.quoteSelections={};state.quoteVisitId=null;state.quoteClientRef="";state.quoteLoyaltyCode="";state.quotePaymentOptionId=null;
  state.page="pending";render();
  if(navigator.onLine){
    if (op.state!=="synced" && op.state!=="warning") await syncPending(false,[op.uuid]);
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
  if (!op) return;
  state.page = "pending"; render();
  if (navigator.onLine && op.state!=="synced" && op.state!=="warning") await syncPending(false, [op.uuid]);
}

function pendingQuoteWarehousePicker(op){
  if(op.type!=='quote'||['synced','warning'].includes(op.state))return '';
  if((op.user_id && Number(op.user_id)!==Number(state.meta?.user?.id))||
     (op.company_id && Number(op.company_id)!==Number(state.meta?.user?.company_id)))
    return '<div class="small">Cotización de otra sesión. Inicie sesión con el usuario y compañía de origen para editarla.</div>';
  const warehouses=state.meta?.capabilities?.quote_warehouses||[];
  if(!warehouses.length)return '<div class="small">No hay bodegas disponibles. Consulte con el administrador.</div>';
  return `<div class="quote-pending-warehouse"><label>Bodega para validar existencias
    <select data-pending-quote-warehouse="${esc(op.uuid)}"><option value="">Seleccione…</option>${warehouses.map(w=>`<option value="${w.id}" ${Number(op.payload?.warehouse_id)===Number(w.id)?'selected':''}>${esc(w.name)}</option>`).join('')}</select></label>
    <button type="button" class="btn btn-outline" data-action="fix-quote-warehouse" data-id="${esc(op.uuid)}">Guardar bodega</button>
    <div class="small">Al sincronizar, Odoo validará los productos y cantidades usando esta bodega. Puede rechazar la operación si el stock cambió.</div></div>`;
}
function renderPending() {
  const pending = [...state.pending].sort((a,b)=>String(b.created_at).localeCompare(String(a.created_at)));
  const body = `<div class="row" style="margin-bottom:12px"><button class="btn btn-primary" style="width:100%" data-action="sync">⇅ Sincronizar ahora</button></div>
    <div class="cards">${pending.map(op=>`<section class="card pending-item"><div><div class="card-title">${esc(operationLabel(op))}</div><div class="card-sub">${esc(op.label||"")}</div><div class="chips"><span class="chip ${op.state==="error"?"danger":op.state==="conflict"?"warn":op.state==="synced"?"ok":""}">${esc(op.state||"pendiente")}</span></div>${op.message?`<div class="small ${op.state==="error"?"danger-text":""}" style="margin-top:8px">${esc(op.message)}</div>`:""}${op.result_model==="res.partner" && op.result_id && ["synced","warning"].includes(op.state)?`<button class="btn btn-outline" style="margin-top:10px" data-action="open-result" data-id="${op.result_id}">Ver catastro</button>`:""}${op.result_model==="sale.order" && op.result_id && op.state==="synced"?`<button class="btn btn-outline" style="margin-top:10px" data-action="open-quote-result" data-id="${op.result_id}">Ver cotización</button>`:""}${pendingQuoteWarehousePicker(op)}<div class="pending-meta">${esc(dateText(op.created_at))}</div></div><div><button class="icon-btn" data-delete-pending="${op.uuid}" title="Eliminar del dispositivo">×</button></div></section>`).join("") || `<div class="empty"><b>Todo sincronizado</b>No hay información pendiente en este dispositivo.</div>`}</div>`;
  $app.innerHTML = shell("Pendientes", body, { nav:"pending" });
}

function renderMore() {
  const secure = window.isSecureContext;
  const saved = state.meta?.saved_at ? dateText(state.meta.saved_at) : "Nunca";
  const canInstall = Boolean(installPrompt);
  const body = `<section class="card ${secure?"":"install-card"}"><div class="card-title">${secure?"Modo offline completo":"Modo offline limitado por HTTP"}</div><div class="card-sub" style="${secure?"":"color:rgba(255,255,255,.86)"}">${secure?(state.localReady?"La app puede abrirse y capturar datos sin cobertura después de sincronizar.":"La app funciona online mientras se conecta al almacenamiento local. El guardado offline solo estará disponible cuando termine la conexión."):"Puede seguir capturando si pierde señal mientras esta pantalla permanece abierta. Para abrir la app desde cero sin Internet e instalarla como PWA, el servidor debe usar HTTPS."}</div>${canInstall?'<button class="btn" data-action="install">Instalar app</button>':""}</section>
    <section class="card"><div class="card-title">Datos del dispositivo</div><div class="card-sub">Usuario: ${esc(state.meta?.user?.name||"Sin descargar")}<br>Empresa: ${esc(state.meta?.user?.company_name||"")}<br>Última descarga: ${esc(saved)}<br>Pendientes: ${state.pending.filter(x=>x.state!=="synced").length}</div><div class="action-grid"><button class="btn btn-outline" data-action="refresh">Descargar datos</button><button class="btn btn-danger" data-action="clear-local" ${db?"":"disabled"}>Borrar caché local</button></div></section>
    <section class="card"><div class="card-title">Datos sin conexión</div><div class="card-sub">${state.localReady?"Almacenamiento local conectado. Puede preparar registros offline.":state.storageError?"No se pudo acceder al almacenamiento local. Online se guarda directamente en Odoo; para trabajar sin conexión revise los permisos del navegador y cierre otras pestañas de Catastro.":"Preparando almacenamiento local en segundo plano. Puede trabajar online mientras tanto."}</div>${!state.localReady?'<button type="button" class="btn btn-outline" data-action="retry-storage" style="margin-top:10px">Reintentar almacenamiento</button>':""}</section>
    <section class="card"><div class="card-title">Versión de la aplicación: ${esc(APP_VERSION)}</div><div class="card-sub">Si no aparece «Crear cotización» dentro de la ficha del catastro o ves una versión anterior, actualiza la interfaz. Esta acción no elimina catastros, visitas ni cotizaciones pendientes de sincronización.</div><button class="btn btn-secondary" style="width:100%;margin-top:12px" type="button" data-action="update-ui">↻ Actualizar interfaz PWA</button></section>
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
async function sendOperationOnline(op) {
  // Fallback real para equipos con IndexedDB temporalmente inaccesible.
  // Odoo registra client_uuid de forma idempotente y aplica permisos y cálculos.
  if (!navigator.onLine || !state.meta?.user) {
    showFormError("Sin almacenamiento offline disponible. Conéctese a Odoo para guardar de forma segura.");
    return null;
  }
  try {
    const session = await rpc("/catastro/app/ping");
    if (Number(session.user_id)!==Number(op.user_id) || Number(session.company_id)!==Number(op.company_id)) {
      throw new Error("La sesión cambió. No se enviaron datos con otro usuario o empresa.");
    }
    const response = await rpc("/catastro/app/sync", {operations: [
      {uuid:op.uuid,type:op.type,payload:op.payload,user_id:op.user_id,company_id:op.company_id},
    ]});
    const result = (response.results || []).find(x=>x.uuid===op.uuid);
    if (!result || !["synced","warning"].includes(result.state)) {
      throw new Error(result?.message || "Odoo no confirmó el guardado. Revise el formulario.");
    }
    Object.assign(op, result, {synced_at:new Date().toISOString()});
    // Histórico temporal de la sesión: el registro final está guardado en Odoo.
    state.pending = [op,...state.pending.filter(x=>x.uuid!==op.uuid)];
    await refreshFromServer(false);
    return op;
  } catch (error) {
    showFormError(error.message || String(error));
    return null;
  }
}
async function queueOperation(type, payload, label) {
  const op={uuid:uuid(),type,payload,label,state:"pending",message:"",created_at:new Date().toISOString(),
    user_id:state.meta?.user?.id||null,company_id:state.meta?.user?.company_id||null};
  if (db && state.localReady) {
    try {
      await idbPut(STORE_PENDING,op);
      await hydrateLocalState();
      render();
      return op;
    } catch (error) {
      state.storageError = error.message || String(error);
      console.warn("No se pudo conservar la operación en IndexedDB", error);
    }
  }
  return sendOperationOnline(op);
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
  if (!op) return;
  state.page="pending";render();
  if (navigator.onLine && op.state!=="synced" && op.state!=="warning") await syncPending(false,[op.uuid]);
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
  if (!op) return;
  state.page = "pending";
  render();
  if (navigator.onLine && op.state!=="synced" && op.state!=="warning") await syncPending(false, [op.uuid]);
}

async function syncPending(silent=false, onlyUuids=null) {
  // Una falla al actualizar la caché de lectura no debe bloquear el envío de
  // operaciones que sí están persistidas en la cola local.
  if (!db || !state.localReady) return;
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
  if (!db) {alert("El almacenamiento local no está disponible. No se puede borrar desde la aplicación.");return;}
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
    const fresh={...p,...status};
    if (db) {await idbPut(STORE_PARTNERS,fresh);await hydrateLocalState();}
    else state.partners=state.partners.map(row=>row.id===p.id?fresh:row);
    render();}
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
  if(event.target?.id==='quote-loyalty-code')state.quoteLoyaltyCode=event.target.value;
  if (event.target?.id === "quote-search") {
    const value=event.target.value;state.quoteSearch=value;
    const auditButton=document.querySelector('[data-action="quote-stock-audit"]');
    if(auditButton)auditButton.disabled=value.trim().length<2||!state.online;
    clearTimeout(state.quoteLookupTimer);state.quoteLookupTimer=setTimeout(()=>searchQuoteProducts(value),300);
  }
  if (event.target?.matches('#quote-form [name="client_order_ref"]')) {
    state.quoteClientRef=event.target.value;
  }
  if (event.target?.matches("[data-quote-qty]")) {
    const line=state.quoteLines.find(x=>x.id===Number(event.target.dataset.quoteQty));
    if(line){line.qty=event.target.value;updateQuoteTotals();}
  }
  if (event.target?.matches('[data-quote-negotiable]')) {
    const line=state.quoteLines.find(x=>x.id===Number(event.target.dataset.quoteNegotiable));
    if(line){line.negotiable_price=event.target.value;updateQuoteTotals();}
  }
  if (event.target?.matches('[data-quote-search-qty]')) {
    const id=Number(event.target.dataset.quoteSearchQty);
    const chosen=state.quoteSelections[id]; if(chosen)chosen.qty=event.target.value;
  }
  if (event.target?.id === "partner-search") { state.search = event.target.value; renderHome(); const input=document.querySelector("#partner-search"); if(input){input.focus(); input.setSelectionRange(state.search.length,state.search.length);} }
});

$app.addEventListener("change", (event) => {
  if (event.target?.matches('#quote-form [name="partner_id"]')) {
    state.quotePartnerId=Number(event.target.value)||null;
    state.quoteVisitId=null;
    state.quoteLines=[];state.quoteResults=[];state.quoteSelections={};state.quoteSearch="";renderQuote();
  }
  if(event.target?.id==='quote-payment-option') {
    state.quotePaymentOptionId=Number(event.target.value)||null;updateQuoteTotals();
  }
  if (event.target?.matches('#quote-form [name="visit_id"]')) {
    state.quoteVisitId=Number(event.target.value)||null;
  }
  if (event.target?.matches('[data-quote-select]')) {
    const id=Number(event.target.dataset.quoteSelect);
    if(event.target.checked){
      const product=state.quoteResults.find(x=>x.id===id);
      if(product)state.quoteSelections[id]={product,qty:document.querySelector(`[data-quote-search-qty="${id}"]`)?.value||1};
    } else delete state.quoteSelections[id];
    renderQuoteResults();
  }
  if (event.target?.matches('[data-quote-qty]')) scheduleQuotePrices();
  if (event.target?.id==='quote-warehouse'||event.target?.id==='quote-pricelist') {
    if(event.target.id==='quote-warehouse')state.quoteWarehouseId=Number(event.target.value)||null;
    else state.quotePricelistId=Number(event.target.value)||null;
    state.quoteResults=[];
    state.quoteLines.forEach(line=>{line.stock_qty=null;line.price=null;line.qty_priced=null;line.stock_label='';line.warehouse_id=null;});
    state.quoteSelections={};
    renderQuote();
    if(state.quoteSearch.trim().length>=2)void searchQuoteProducts(state.quoteSearch);
    scheduleQuotePrices();
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
  if (action === "quote-retail") {
    const retail=state.meta?.capabilities?.quote_retail_partner;
    if(!retail || !state.meta?.capabilities?.quote_retail_enabled){alert('El administrador debe configurar Consumidor Final y asignar el perfil Tienda.');return;}
    state.quoteRetail=true;state.quotePartnerId=Number(retail.id);state.selectedPartnerId=null;
    state.quoteVisitId=null;state.quoteClientRef='';state.quoteLines=[];state.quoteResults=[];state.quoteSelections={};
    state.quoteWarehouseId=null;state.quotePricelistId=null;state.quotePaymentOptionId=null;state.quoteLoyaltyCode='';
    state.quoteSearch='';state.quoteDetail=null;state.page='quote';render();return;
  }
  if (action === "quote-partner") {state.quoteRetail=false;const id=Number(event.target.closest("[data-id]")?.dataset.id);const partner=state.partners.find(x=>x.id===id);if (!truthy(partner?.census_locked)){alert("Primero finalice y proteja el catastro.");return;}state.selectedPartnerId=id;state.quotePartnerId=id;state.quoteVisitId=null;state.quoteClientRef="";state.quoteLines=[];state.quoteResults=[];state.quoteSelections={};state.quoteWarehouseId=null;state.quotePricelistId=null;state.quoteSearch="";state.quoteDetail=null;state.page="quote";render();return;}
  if (action === "back-to-partner") {if(state.quoteRetail){state.page="home";render();return;}state.selectedPartnerId=Number(state.quotePartnerId)||state.selectedPartnerId;state.page="detail";render();return;}
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
  if (action === 'quote-stock-audit') {
    const box=document.querySelector('#quote-stock-audit');
    if(!box)return;
    box.textContent='Comparando stock físico de la bodega con el total de la compañía…';
    try {
      const rows=await rpc('/catastro/app/quote/stock-audit',{partner_id:state.quotePartnerId,warehouse_id:state.quoteWarehouseId,term:state.quoteSearch});
      box.innerHTML=rows.length?rows.map(row=>`<div class="stock-diagnostic"><strong>${esc(row.name)}</strong><span>Bodega: ${money(row.stock_warehouse)} ${esc(row.uom)} · Total compañía: ${money(row.stock_company)} ${esc(row.uom)}</span><small>Ubicación raíz: ${esc(row.root_location)}</small></div>`).join(''):'No hay productos vendibles con esa búsqueda.';
    }catch(e){box.textContent=e.message||String(e);}return;
  }
  if (action === 'quote-update-rewards' && state.quoteDetail?.id) {
    try {state.quoteDetail=await rpc('/catastro/app/quote/loyalty/rewards',{quote_id:state.quoteDetail.id});renderQuoteDetail();}
    catch(e){alert(e.message||String(e));}return;
  }
  if (action === 'quote-apply-code' && state.quoteDetail?.id) {
    const code=document.querySelector('#quote-detail-coupon')?.value?.trim();if(!code){alert('Ingrese un código.');return;}
    try {state.quoteDetail=await rpc('/catastro/app/quote/loyalty/code',{quote_id:state.quoteDetail.id,code});renderQuoteDetail();}
    catch(e){alert(e.message||String(e));}return;
  }
  if (action === 'quote-apply-reward' && state.quoteDetail?.id) {
    const reward_id=Number(event.target.closest('[data-id]')?.dataset.id);
    const product_id=Number(document.querySelector(`[data-loyalty-product="${reward_id}"]`)?.value||0);
    if(!confirm('¿Aplicar esta recompensa usando las reglas de Loyalty de Odoo?'))return;
    try {state.quoteDetail=await rpc('/catastro/app/quote/loyalty/apply',{quote_id:state.quoteDetail.id,reward_id,product_id});renderQuoteDetail();}
    catch(e){alert(e.message||String(e));}return;
  }
  if (action === "quote-add-product") {
    const id=Number(event.target.closest("[data-id]")?.dataset.id);
    const product=state.quoteResults.find(x=>x.id===id);
    if(!product)return;
    const qty=document.querySelector(`[data-quote-search-qty="${id}"]`)?.value||1;
    if(addQuoteProduct(product,qty)) {delete state.quoteSelections[id];renderQuote();scheduleQuotePrices();}
    return;
  }
  if (action === "quote-add-selected") {
    let done=0;
    for(const selected of Object.values(state.quoteSelections)) if(addQuoteProduct(selected.product,selected.qty)) done++;
    if(done){state.quoteSelections={};state.quoteSearch='';state.quoteResults=[];renderQuote();scheduleQuotePrices();}
    return;
  }
  if (action === "quote-image") {
    const id=Number(event.target.closest('[data-id]')?.dataset.id);
    const product=[...state.quoteResults,...state.quoteLines].find(x=>x.id===id);
    if(!product?.has_image)return;
    const dialog=document.querySelector('#quote-image-dialog');
    const img=document.querySelector('#quote-zoom-picture');
    const name=document.querySelector('#quote-zoom-name');
    if(!dialog||!img)return;
    img.src=product.zoom_url; img.alt=product.name; if(name)name.textContent=product.name;
    state.quoteImageZoom=1;img.style.width='auto';img.style.maxWidth='100%';img.style.maxHeight='70vh';
    const level=document.querySelector('#quote-zoom-level');if(level)level.textContent='100%';
    dialog.showModal();return;
  }
  if(action==='quote-zoom-in'||action==='quote-zoom-out'){
    state.quoteImageZoom=Math.max(1,Math.min(3,state.quoteImageZoom+(action==='quote-zoom-in'?.5:-.5)));
    const img=document.querySelector('#quote-zoom-picture');
    if(img){ img.style.maxWidth='none';img.style.maxHeight='none';img.style.width=`${state.quoteImageZoom*100}%`; }
    const level=document.querySelector('#quote-zoom-level');if(level)level.textContent=`${Math.round(state.quoteImageZoom*100)}%`;
    return;
  }
  if(action==='quote-close-image'){document.querySelector('#quote-image-dialog')?.close();return;}
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
    if (!op) return;
    state.page="pending";render();if(navigator.onLine && op.state!=="synced" && op.state!=="warning") await syncPending(false,[op.uuid]);return;
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
  if (action === "retry-storage") {void restoreLocalStorage();render();return;}
  if (action === "refresh") { await syncPending(true); await refreshFromServer(true); return; }
  if (action === "new-catastro") { state.page="new"; render(); return; }
  if (action === "edit-partner") {if(!truthy(selectedPartner()?.census_can_edit_master)){alert("El catastro está protegido; solicite habilitación.");return;} state.page="edit"; render(); return; }
  if (action === "cancel-edit") { state.page="detail"; render(); return; }
  if (action === "fix-quote-warehouse") {
    const uuid=event.target.closest('[data-id]')?.dataset.id;
    const op=state.pending.find(x=>x.uuid===uuid && x.type==='quote' && !['synced','warning'].includes(x.state));
    const id=Number(document.querySelector(`[data-pending-quote-warehouse="${uuid}"]`)?.value||0);
    const wh=(state.meta?.capabilities?.quote_warehouses||[]).find(w=>w.id===id);
    if(!op||!wh){alert('Seleccione una bodega válida.');return;}
    if((op.user_id && Number(op.user_id)!==Number(state.meta?.user?.id))||
       (op.company_id && Number(op.company_id)!==Number(state.meta?.user?.company_id))){
      alert('Esta operación pertenece a otra sesión y no se puede modificar.');return;
    }
    if(!confirm(`¿Asignar la bodega ${wh.name} a esta cotización pendiente? Odoo verificará el stock de cada producto cuando sincronice.`))return;
    op.payload={...op.payload,warehouse_id:id};op.state='pending';op.message='Bodega seleccionada; pendiente de validar en Odoo.';
    if(db){await idbPut(STORE_PENDING,op);await hydrateLocalState();}
    render();return;
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

$app.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (event.target.id === "catastro-form") await submitCatastro(event.target,event.submitter?.value==="finalize");
  if (event.target.id === "catastro-edit-form") await submitCatastroUpdate(event.target);
  if (event.target.id === "visit-form") await submitVisit(event.target,true);
  if (event.target.id === "quote-form") await submitQuote(event.target);
  if (event.target.id === "unlock-form") await submitUnlockRequest(event.target);
});

let storageOpenPromise = null;
async function restoreLocalStorage() {
  if (storageOpenPromise || state.localReady) return storageOpenPromise;
  storageOpenPromise = (async () => {
    try {
      const opened = await openDb();
      db = opened;
      await hydrateLocalState();
      state.localReady = true;
      state.storageError = "";
      const snapshot = state.serverSnapshot;
      if (snapshot) {
        // No sustituir un catastro remoto nuevo por una copia vieja al abrir
        // tarde el almacenamiento. Verificar pendientes de otra sesión primero.
        const differentSession=state.meta?.user &&
          (Number(state.meta.user.id)!==Number(snapshot.user.id) ||
           Number(state.meta.user.company_id)!==Number(snapshot.user.company_id));
        const hasUnsynced=state.pending.some(x=>!["synced","warning","conflict"].includes(x.state));
        if (differentSession && hasUnsynced) {
          state.sessionBlocked = true;
          state.lastError = "Hay datos offline de otro usuario o compañía; no se sincronizaron.";
        } else {
          try {
            await persistBootstrap(snapshot);
            await hydrateLocalState();
          } catch (error) {
            // Seguir online aun si la caché no acepta escrituras grandes.
            state.storageError = error.message || String(error);
            applyBootstrapInMemory(snapshot);
          }
        }
      }
      render();
      if (navigator.onLine && !state.sessionBlocked) void syncPending(true);
    } catch (error) {
      console.warn("Catastro: almacenamiento local temporalmente inaccesible", error);
      db = null;
      state.localReady = false;
      state.storageError = error.message || String(error);
      render();
    } finally {
      storageOpenPromise = null;
    }
  })();
  return storageOpenPromise;
}
async function init() {
  // Render inmediato, sin temporizadores ni migraciones que frenen la PWA.
  render();
  window.catastroBootReady?.();
  if (window.isSecureContext && "serviceWorker" in navigator) {
    navigator.serviceWorker.register("/catastro/sw.js", { scope: "/catastro/" })
      .catch(err => console.warn("Service worker no disponible", err));
  }
  // El acceso al dispositivo es opcional para la navegación online, no para
  // garantizar operaciones offline. No esperar IndexedDB en el arranque.
  void restoreLocalStorage();
  if (navigator.onLine) {
    await refreshFromServer(false);
  }
  state.starting = false;
  render();
}

init().catch((err) => {
  console.error("Error iniciando Catastro PWA", err);
  if (window.catastroBootError) window.catastroBootError(err.message || String(err));
  else $app.innerHTML = `<div class="boot-screen"><div class="boot-logo">!</div><strong>No se pudo iniciar la app</strong><span>${esc(err.message || err)}</span><a class="btn btn-primary" href="/web">Volver a Odoo</a></div>`;
});
