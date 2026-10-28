/* Transcash PWA: public navigation is /logistica without changing model names,
 * legacy /transcash routes, API endpoints or static asset module paths.
 * No privileged operation is exposed by this script: all server-side checks remain.
 */
(function () {
    'use strict';
    var oldRoot = '/transcash';
    var newRoot = '/logistica';
    function oldPath(path) { return path === oldRoot || path.indexOf(oldRoot + '/') === 0; }
    function pwaPath(path) {
        return path === newRoot || path.indexOf(newRoot + '/') === 0 || oldPath(path);
    }
    function pathChange(value) {
        if (!value || value[0] === '#') return value;
        try {
            var url = new URL(value, location.href);
            if (url.origin !== location.origin || !oldPath(url.pathname)) return value;
            url.pathname = newRoot + url.pathname.slice(oldRoot.length);
            // Retain relative URL style where possible; do not alter other hosts.
            return value[0] === '/' ? url.pathname + url.search + url.hash : url.href;
        } catch (_) { return value; }
    }
    function updateAttribute(element, attribute) {
        var current = element.getAttribute(attribute);
        if (!current) return;
        var next = pathChange(current);
        if (next !== current) element.setAttribute(attribute, next);
    }
    function updateElement(element) {
        if (!element || element.nodeType !== 1) return;
        if (element.hasAttribute('href')) updateAttribute(element, 'href');
        if (element.hasAttribute('action')) updateAttribute(element, 'action');
        if (element.hasAttribute('formaction')) updateAttribute(element, 'formaction');
    }
    function updateTree(root) {
        updateElement(root);
        if (root.querySelectorAll) {
            root.querySelectorAll('[href],[action],[formaction]').forEach(updateElement);
        }
    }
    // A previously saved /transcash bookmark will display /logistica after load,
    // while the old endpoint still works for installed links or disabled scripts.
    if (oldPath(location.pathname)) {
        history.replaceState(history.state, '',
            newRoot + location.pathname.slice(oldRoot.length) + location.search + location.hash);
    }
    function init() {
        if (!pwaPath(location.pathname)) return;
        updateTree(document.documentElement);
        if (window.MutationObserver) {
            var observer = new MutationObserver(function (records) {
                records.forEach(function (record) {
                    if (record.type === 'attributes') updateElement(record.target);
                    else record.addedNodes.forEach(updateTree);
                });
            });
            observer.observe(document.documentElement, {
                subtree: true, childList: true, attributes: true,
                attributeFilter: ['href', 'action', 'formaction']
            });
        }
        if ('serviceWorker' in navigator && window.isSecureContext) {
            navigator.serviceWorker.register('/logistica/sw.js', { scope: '/logistica/' })
                .catch(function (error) { console.warn('PWA /logistica:', error); });
        }
    }
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();

    // Defend against links/forms added dynamically immediately before the action.
    document.addEventListener('click', function (event) {
        var el = event.target.closest && event.target.closest('a[href],button[formaction]');
        if (el) updateElement(el);
    }, true);
    document.addEventListener('submit', function (event) {
        if (event.target && event.target.tagName === 'FORM') updateElement(event.target);
    }, true);
}());
