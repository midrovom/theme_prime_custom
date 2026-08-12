/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.MultistepForm.extend({

    events: {
        'change #fotografia': '_onCustomFileSelected',
        'change #cedula-votacion': '_onCustomFileSelected',
        'change #historia-laboral-iess': '_onCustomFileSelected',
        'change #acta-matrimonio': '_onCustomFileSelected',
        'change #hijos-menores': '_onCustomFileSelected',
        'change #estudios-senecyt': '_onCustomFileSelected',
        'change #cursos-realizados': '_onCustomFileSelected',
        'change #recomendaciones': '_onCustomFileSelected',
        'change #certificados-trabajo': '_onCustomFileSelected',
        'change #planilla-servicios': '_onCustomFileSelected',
        'change #croquis-domicilio': '_onCustomFileSelected',
        'change #formulario-107': '_onCustomFileSelected',
        'change #cuenta-banco-internacional': '_onCustomFileSelected',
        'change #certificado-salud': '_onCustomFileSelected',
    },

    init() {
        this._super(...arguments);

        this.customUploadedFiles = {};
    },

    // ============================================================
    // ARCHIVOS
    // ============================================================

    _onCustomFileSelected(ev) {

        const input = ev.currentTarget;
        const inputId = input.id;

        const container = document.getElementById(
            `file-selected-${inputId}`
        );

        if (!input || !container) {
            return;
        }

        const files = Array.from(input.files || []);

        if (!files.length) {
            return;
        }

        const isPhotography = inputId === 'fotografia';

        const invalidFiles = files.filter((file) => {

            if (isPhotography) {
                return !file.type.startsWith('image/');
            }

            return (
                file.type !== 'application/pdf' &&
                !file.name.toLowerCase().endsWith('.pdf')
            );
        });

        // --------------------------------------------------------
        // ARCHIVO INVÁLIDO
        // --------------------------------------------------------

        if (invalidFiles.length) {

            const message = isPhotography
                ? 'Solo se permiten archivos de imagen.'
                : 'Solo se permiten archivos PDF.';

            container.innerHTML = `
                <div class="text-danger custom-message fs-6">
                    ${message}
                </div>
            `;

            input.classList.add('is-invalid');
            input.value = '';

            this.customUploadedFiles[inputId] = [];

            return;
        }

        // --------------------------------------------------------
        // ARCHIVO VÁLIDO
        // --------------------------------------------------------

        input.classList.remove('is-invalid');

        if (!this.customUploadedFiles[inputId]) {
            this.customUploadedFiles[inputId] = [];
        }

        this.customUploadedFiles[inputId] =
            this.customUploadedFiles[inputId].concat(files);

        // Eliminar duplicados
        this.customUploadedFiles[inputId] =
            this.customUploadedFiles[inputId].filter(
                (file, index, self) =>
                    index === self.findIndex(
                        (f) =>
                            f.name === file.name &&
                            f.size === file.size
                    )
            );

        this._refreshCustomFileInput(input);

        this._renderCustomFileList(
            container,
            input
        );
    },

    _refreshCustomFileInput(input) {

        const files =
            this.customUploadedFiles[input.id] || [];

        const dataTransfer = new DataTransfer();

        files.forEach((file) => {
            dataTransfer.items.add(file);
        });

        input.files = dataTransfer.files;
    },

    _renderCustomFileList(container, input) {

        container.innerHTML = '';

        const files =
            this.customUploadedFiles[input.id] || [];

        if (!files.length) {
            return;
        }

        files.forEach((file, index) => {

            const fileItem =
                document.createElement('div');

            fileItem.className =
                'd-flex align-items-center ' +
                'justify-content-between ' +
                'border rounded-pill ' +
                'px-3 py-2 mb-2';

            fileItem.innerHTML = `
                <span class="text-success">
                    ${file.name}
                </span>

                <button
                    type="button"
                    class="btn btn-sm btn-danger remove-custom-file"
                    data-index="${index}">
                    ×
                </button>
            `;

            container.appendChild(fileItem);
        });

        container
            .querySelectorAll('.remove-custom-file')
            .forEach((button) => {

                button.addEventListener('click', (ev) => {

                    const index = parseInt(
                        ev.currentTarget.dataset.index,
                        10
                    );

                    const inputId = input.id;

                    this.customUploadedFiles[inputId]
                        .splice(index, 1);

                    this._refreshCustomFileInput(input);

                    this._renderCustomFileList(
                        container,
                        input
                    );
                });
            });
    },

    // ============================================================
    // VALIDACIÓN STEP 1
    // ============================================================

    _validateCurrentStep1() {

        // Primero ejecutamos TODA la validación
        // que ya existe en el widget original.
        const originalValid = this._super(...arguments);

        // Después validamos nuestros documentos.
        const customDocumentsValid =
            this._validateCustomDocuments();

        if (!originalValid || !customDocumentsValid) {

            this._scrollToFirstError();

            return false;
        }

        return true;
    },

    // ============================================================
    // VALIDAR DOCUMENTOS PERSONALIZADOS
    // ============================================================

    _validateCustomDocuments() {

        let isValid = true;

        const documents = [
            {
                id: 'fotografia',
                required: true,
                type: 'image',
            },
            {
                id: 'cedula-votacion',
                required: true,
                type: 'pdf',
            },
            {
                id: 'historia-laboral-iess',
                required: true,
                type: 'pdf',
            },
            {
                id: 'acta-matrimonio',
                required: true,
                type: 'pdf',
            },
            {
                id: 'hijos-menores',
                required: true,
                type: 'pdf',
            },
            {
                id: 'estudios-senecyt',
                required: true,
                type: 'pdf',
            },
            {
                id: 'cursos-realizados',
                required: true,
                type: 'pdf',
            },
            {
                id: 'recomendaciones',
                required: true,
                type: 'pdf',
            },
            {
                id: 'certificados-trabajo',
                required: true,
                type: 'pdf',
            },
            {
                id: 'planilla-servicios',
                required: true,
                type: 'pdf',
            },
            {
                id: 'croquis-domicilio',
                required: true,
                type: 'pdf',
            },
            {
                id: 'formulario-107',
                required: true,
                type: 'pdf',
            },
            {
                id: 'cuenta-banco-internacional',
                required: true,
                type: 'pdf',
            },
            {
                id: 'certificado-salud',
                required: true,
                type: 'pdf',
            },
        ];

        documents.forEach((document) => {

            const $input = this.$(`#${document.id}`);

            if (!$input.length) {
                return;
            }

            const files =
                this.customUploadedFiles[document.id] || [];

            // ----------------------------------------------------
            // OBLIGATORIO
            // ----------------------------------------------------

            if (document.required && !files.length) {

                $input.addClass('is-invalid');

                const container =
                    this.$(`#file-selected-${document.id}`);

                container.html(`
                    <div class="text-danger custom-message fs-6">
                        Campo obligatorio.
                    </div>
                `);

                isValid = false;

                return;
            }

            // ----------------------------------------------------
            // VALIDAR TIPO
            // ----------------------------------------------------

            const invalidFile = files.some((file) => {

                if (document.type === 'image') {
                    return !file.type.startsWith('image/');
                }

                return (
                    file.type !== 'application/pdf' &&
                    !file.name.toLowerCase().endsWith('.pdf')
                );
            });

            if (invalidFile) {

                $input.addClass('is-invalid');

                const container =
                    this.$(`#file-selected-${document.id}`);

                container.html(`
                    <div class="text-danger custom-message fs-6">
                        ${
                            document.type === 'image'
                                ? 'Solo se permiten imágenes.'
                                : 'Solo se permiten archivos PDF.'
                        }
                    </div>
                `);

                isValid = false;

                return;
            }

            $input.removeClass('is-invalid');
        });

        return isValid;
    },

});