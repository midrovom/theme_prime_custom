/* Transcash PWA v2.8: mejora progresiva de selects nativos, sin dependencias externas.
 * Las opciones proceden del backend autorizado; se conserva select.name/value y los eventos change.
 */
(function () {
    'use strict';
    var LIMIT = 90;
    var counter = 0;

    function normalize(value) {
        return String(value || '').normalize('NFD')
            .replace(/[\u0300-\u036f]/g, '').toLowerCase().trim();
    }

    function attach(select) {
        if (select.dataset.tcSearchReady === '1' || select.multiple || select.disabled) return;
        var options = Array.prototype.map.call(select.options, function (opt) {
            return {
                value: opt.value,
                label: opt.textContent.trim(),
                text: normalize((opt.dataset.tcSearch || '') + ' ' + opt.textContent),
                disabled: opt.disabled
            };
        });
        if (options.length < 2) return;

        var id = 'tc-pwa-combo-' + (++counter);
        var wrap = document.createElement('div');
        wrap.className = 'tc-search-select tc-search-select--ready';
        var input = document.createElement('input');
        input.type = 'search';
        input.id = id + '-input';
        input.className = 'tc-search-select__input';
        input.autocomplete = 'off';
        input.spellcheck = false;
        input.setAttribute('role', 'combobox');
        input.setAttribute('aria-autocomplete', 'list');
        input.setAttribute('aria-haspopup', 'listbox');
        input.setAttribute('aria-controls', id + '-list');
        input.setAttribute('aria-expanded', 'false');
        input.setAttribute('aria-required', select.required ? 'true' : 'false');
        input.setAttribute('placeholder', 'Escribir para buscar o seleccionar…');

        var toggle = document.createElement('button');
        toggle.type = 'button';
        toggle.className = 'tc-search-select__toggle';
        toggle.setAttribute('aria-label', 'Mostrar opciones');
        toggle.textContent = '▾';
        var panel = document.createElement('div');
        panel.className = 'tc-search-select__panel';
        panel.id = id + '-list';
        panel.setAttribute('role', 'listbox');
        panel.hidden = true;
        var caption = document.createElement('div');
        caption.className = 'tc-search-select__caption';
        caption.setAttribute('aria-live', 'polite');
        var results = document.createElement('div');
        results.className = 'tc-search-select__results';
        panel.appendChild(caption);
        panel.appendChild(results);

        select.parentNode.insertBefore(wrap, select);
        wrap.appendChild(select);
        wrap.appendChild(input);
        wrap.appendChild(toggle);
        wrap.appendChild(panel);
        select.classList.add('tc-search-select__native');
        select.setAttribute('tabindex', '-1');
        select.dataset.tcSearchReady = '1';
        var formLabel = document.querySelector('label[for="' + select.id + '"]');
        if (formLabel) formLabel.setAttribute('for', input.id);

        var chosen = options.find(function (opt) { return opt.value === select.value; });
        var emptyOpt = options.find(function (opt) { return !opt.value; });
        input.value = chosen && chosen.value ? chosen.label : '';
        if (emptyOpt && emptyOpt.label) input.placeholder = emptyOpt.label + ' · buscar…';
        var visible = [], active = -1, isOpen = false;

        function setOpened(value) {
            isOpen = value;
            panel.hidden = !value;
            wrap.classList.toggle('tc-search-select--open', value);
            input.setAttribute('aria-expanded', value ? 'true' : 'false');
            if (!value) input.removeAttribute('aria-activedescendant');
        }
        function markActive() {
            var buttons = results.querySelectorAll('[role="option"]');
            buttons.forEach(function (button, index) {
                var enabled = index === active;
                button.classList.toggle('tc-search-select__item--active', enabled);
                button.setAttribute('aria-selected', enabled ? 'true' : 'false');
                if (enabled) {
                    input.setAttribute('aria-activedescendant', button.id);
                    button.scrollIntoView({block: 'nearest'});
                }
            });
        }
        function draw(query) {
            var tokens = normalize(query).split(/\s+/).filter(Boolean);
            visible = options.filter(function (opt) {
                return !!opt.value && !opt.disabled && tokens.every(function (token) {
                    return opt.text.indexOf(token) !== -1 || opt.text.replace(/[^a-z0-9]/g, '').indexOf(token.replace(/[^a-z0-9]/g, '')) !== -1;
                });
            });
            active = -1;
            results.replaceChildren();
            caption.textContent = !visible.length ? 'No se encontraron coincidencias' :
                visible.length + ' resultado(s)' + (visible.length > LIMIT ? ' · refine la búsqueda' : '');
            visible.slice(0, LIMIT).forEach(function (opt, index) {
                var item = document.createElement('button');
                item.type = 'button';
                item.className = 'tc-search-select__item';
                item.id = id + '-opt-' + index;
                item.setAttribute('role', 'option');
                item.setAttribute('aria-selected', 'false');
                item.textContent = opt.label;
                // mousedown precede a blur; no ocultar el resultado antes de elegirlo.
                item.addEventListener('pointerdown', function (event) { event.preventDefault(); });
                item.addEventListener('click', function () { choose(opt); });
                results.appendChild(item);
            });
            setOpened(true);
        }
        function choose(opt) {
            select.value = opt.value;
            input.value = opt.label;
            input.removeAttribute('aria-invalid');
            wrap.classList.remove('tc-search-select--error');
            setOpened(false);
            // Reutiliza onchange nativo: el grupo de rutas recarga su formulario automáticamente.
            select.dispatchEvent(new Event('change', {bubbles: true}));
        }
        function close() {
            setOpened(false);
            // No permitir que quede un texto escrito distinto del ID que se enviará.
            var current = options.find(function (opt) { return opt.value === select.value; });
            input.value = current && current.value ? current.label : '';
        }
        input.addEventListener('focus', function () {
            draw('');
            input.select();
        });
        input.addEventListener('input', function () {
            var selected = options.find(function (opt) { return opt.value === select.value; });
            if (!selected || input.value !== selected.label) {
                select.value = '';
            }
            draw(input.value);
        });
        input.addEventListener('keydown', function (event) {
            if (event.key === 'Escape') {
                event.preventDefault();
                close();
            } else if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
                event.preventDefault();
                if (!isOpen) draw('');
                var count = Math.min(visible.length, LIMIT);
                if (!count) return;
                active = event.key === 'ArrowDown' ?
                    (active + 1) % count : (active <= 0 ? count - 1 : active - 1);
                markActive();
            } else if (event.key === 'Enter' && isOpen) {
                event.preventDefault();
                if (active >= 0 && visible[active]) choose(visible[active]);
                else if (visible.length === 1) choose(visible[0]);
            } else if (event.key === 'Tab') {
                close();
            }
        });
        toggle.addEventListener('click', function () {
            if (isOpen) close();
            else { input.focus(); draw(''); }
        });
        select.addEventListener('change', function () {
            var current = options.find(function (opt) { return opt.value === select.value; });
            input.value = current && current.value ? current.label : '';
        });
        select.addEventListener('invalid', function (event) {
            event.preventDefault();
            wrap.classList.add('tc-search-select--error');
            input.setAttribute('aria-invalid', 'true');
            input.focus();
        });
        document.addEventListener('pointerdown', function (event) {
            if (isOpen && !wrap.contains(event.target)) close();
        });
        // Sin selección no se inventan valores: el required del <select> sigue activo.
    }
    function init() {
        var main = document.querySelector('main.tc-ops');
        if (!main) return;
        main.querySelectorAll('.tc-ops-form select:not([multiple])').forEach(attach);
    }
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else init();
}());
