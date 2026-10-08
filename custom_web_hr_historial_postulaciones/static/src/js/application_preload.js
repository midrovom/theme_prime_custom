/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

const DATA_TTL_MS = 5 * 60 * 1000;
const DATA_PREFIX = "portalApplicantPreload:";
const CATALOG_KEY = "portalFormCatalogs:v1";

function now() {
    return Date.now();
}

function readSession(key, ttl = DATA_TTL_MS) {
    try {
        const raw = sessionStorage.getItem(key);
        if (!raw) return null;
        const entry = JSON.parse(raw);
        if (!entry || !entry.ts || now() - entry.ts > ttl) {
            sessionStorage.removeItem(key);
            return null;
        }
        return entry.data || null;
    } catch (error) {
        return null;
    }
}

function writeSession(key, data) {
    try {
        sessionStorage.setItem(key, JSON.stringify({ ts: now(), data }));
    } catch (error) {
        // Ignore quota/private-mode errors; the in-memory promise still helps.
    }
}

async function fetchApplicantData(applicantId) {
    const key = `${DATA_PREFIX}${applicantId}`;
    const cached = readSession(key);
    if (cached) return cached;

    const response = await fetch(`/my/application/${applicantId}/data`, {
        headers: { "Accept": "application/json" },
        credentials: "same-origin",
        cache: "no-store",
    });
    const data = await response.json();
    if (!response.ok || data.ok === false) {
        throw new Error(data?.error || `HTTP ${response.status}`);
    }
    writeSession(key, data);
    return data;
}

async function fetchCatalogs() {
    const cached = readSession(CATALOG_KEY, 30 * 60 * 1000);
    if (cached) return cached;

    const response = await fetch('/my/application/form-catalogs', {
        headers: { "Accept": "application/json" },
        credentials: "same-origin",
        cache: "no-store",
    });
    const data = await response.json();
    if (!response.ok || data.ok === false) {
        throw new Error(data?.error || `HTTP ${response.status}`);
    }
    writeSession(CATALOG_KEY, data);
    return data;
}

// In-memory promises survive while the page is initializing.
window.__portalApplicantPreloadPromises = window.__portalApplicantPreloadPromises || new Map();
window.__portalCatalogPromise = window.__portalCatalogPromise || null;

function preloadApplicant(applicantId) {
    if (!applicantId) return Promise.resolve(null);
    if (!window.__portalApplicantPreloadPromises.has(String(applicantId))) {
        window.__portalApplicantPreloadPromises.set(
            String(applicantId),
            fetchApplicantData(applicantId).catch(error => {
                console.warn("No se pudo precargar la postulación", applicantId, error);
                return null;
            })
        );
    }
    return window.__portalApplicantPreloadPromises.get(String(applicantId));
}

function preloadCatalogs() {
    if (!window.__portalCatalogPromise) {
        window.__portalCatalogPromise = fetchCatalogs().catch(error => {
            console.warn("No se pudieron precargar los catálogos del formulario", error);
            return null;
        });
    }
    return window.__portalCatalogPromise;
}

// Warm both caches as soon as the history page is visible.
publicWidget.registry.PortalApplicantPreload = publicWidget.Widget.extend({
    selector: '.portal-table-card',

    start() {
        this.$('a[href^="/my/application/"][href$="/edit"]').each(function () {
            const match = this.getAttribute('href')?.match(/\/my\/application\/(\d+)\/edit/);
            if (match) preloadApplicant(match[1]);
        });
        preloadCatalogs();
        return this._super(...arguments);
    },
});

// Start catalog prefetch immediately on edit pages, before the native widget
// creates the first education block.
const params = new URLSearchParams(window.location.search);
if (/^\d+$/.test(params.get('edit_applicant') || '')) {
    preloadCatalogs();
}

// The native module keeps these catalogs inside private closure variables.
// We cannot mutate those variables directly, so we provide the same API from
// our preloaded one-request cache whenever the native code asks for them.
if (!window.__portalFetchPatched) {
    const originalFetch = window.fetch.bind(window);
    window.fetch = async function (input, init) {
        const url = typeof input === 'string' ? input : input?.url || '';
        const absolute = new URL(url, window.location.origin);
        const path = absolute.pathname;
        const matchState = path.match(/^\/api\/states\/(\d+)$/);

        if (/^\d+$/.test(new URLSearchParams(window.location.search).get('edit_applicant') || '')) {
            const catalogs = await preloadCatalogs();
            if (catalogs) {
                if (path === '/api/countries') {
                    return new Response(JSON.stringify(catalogs.countries || []), {
                        status: 200,
                        headers: { 'Content-Type': 'application/json' },
                    });
                }
                if (path === '/api/study_levels') {
                    return new Response(JSON.stringify(catalogs.study_levels || []), {
                        status: 200,
                        headers: { 'Content-Type': 'application/json' },
                    });
                }
                if (matchState) {
                    return new Response(JSON.stringify((catalogs.states_by_country || {})[matchState[1]] || []), {
                        status: 200,
                        headers: { 'Content-Type': 'application/json' },
                    });
                }
            }
        }

        return originalFetch(input, init);
    };
    window.__portalFetchPatched = true;
}

window.__portalPreloadApplicant = preloadApplicant;
window.__portalPreloadCatalogs = preloadCatalogs;
