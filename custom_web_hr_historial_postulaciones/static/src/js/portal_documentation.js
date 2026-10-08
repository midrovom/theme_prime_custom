/** @odoo-module **/

function escapeHtml(value) {
    const div = document.createElement('div');
    div.textContent = value || '';
    return div.innerHTML;
}

function formatBytes(bytes) {
    if (!bytes) {
        return '0 B';
    }
    const units = ['B', 'KB', 'MB', 'GB'];
    const i = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
    const value = bytes / Math.pow(1024, i);
    return `${value.toFixed(i ? 1 : 0)} ${units[i]}`;
}

function initFileInputs() {
    document.querySelectorAll('input[type="file"][data-file-list-target]').forEach((input) => {
        if (input.dataset.initialized === '1') {
            return;
        }
        input.dataset.initialized = '1';
        input._selectedFiles = [];

        const card = input.closest('.document-upload-card');
        const listSelector = input.dataset.fileListTarget;
        const list = listSelector ? document.querySelector(listSelector) : null;
        const counter = card ? card.querySelector('[data-file-count]') : null;
        const minimum = Number(input.dataset.minimumCount || 0);

        const syncInput = () => {
            try {
                const dt = new DataTransfer();
                input._selectedFiles.forEach((file) => dt.items.add(file));
                input.files = dt.files;
            } catch (error) {
                console.debug('No fue posible sincronizar FileList:', error);
            }
        };

        const render = () => {
            if (list) {
                list.replaceChildren();
                input._selectedFiles.forEach((file, index) => {
                    const row = document.createElement('div');
                    row.className = 'd-flex align-items-center justify-content-between gap-2 border rounded-3 px-3 py-2 mb-2';

                    const info = document.createElement('div');
                    info.className = 'text-truncate';
                    info.innerHTML = `<strong>${index + 1}.</strong> ${escapeHtml(file.name)} <span class="text-muted">(${formatBytes(file.size)})</span>`;

                    const remove = document.createElement('button');
                    remove.type = 'button';
                    remove.className = 'btn btn-sm btn-outline-danger flex-shrink-0';
                    remove.textContent = 'Quitar';
                    remove.addEventListener('click', () => {
                        input._selectedFiles.splice(index, 1);
                        syncInput();
                        render();
                    });

                    row.appendChild(info);
                    row.appendChild(remove);
                    list.appendChild(row);
                });
            }

            const existing = Number(input.dataset.existingCount || 0);
            const selected = input._selectedFiles.length;
            const total = existing + selected;
            if (counter) {
                counter.textContent = `${total}`;
                counter.classList.toggle('text-success', minimum === 0 || total >= minimum);
                counter.classList.toggle('text-danger', minimum > 0 && total < minimum);
            }
        };

        input.addEventListener('change', () => {
            const freshFiles = Array.from(input.files || []);
            input._selectedFiles = input._selectedFiles.concat(freshFiles);
            syncInput();
            render();
        });

        render();
    });
}

document.addEventListener('DOMContentLoaded', initFileInputs);
