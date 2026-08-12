/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.MultistepForm.include({

    init() {
        this._super(...arguments);
        this.uploadedFiles = {};
    },

    start() {
        const result = this._super(...arguments);
        this._initializeDocumentFiles();
        return result;
    },

    events: {

        'change #hr-job-recruitment-form input[type="file"]':
            '_onCustomFileSelected',

    },


    /**
     * Inicializa los archivos de los inputs.
     */
    _initializeDocumentFiles() {

        const self = this;

        this.$('#hr-job-recruitment-form input[type="file"]')
            .each(function () {

                const inputId = this.id;

                if (inputId && !self.uploadedFiles[inputId]) {
                    self.uploadedFiles[inputId] = [];
                }
            });
    },


    /**
     * Evento cuando se selecciona un archivo.
     */
    _onCustomFileSelected(ev) {

        const input = ev.currentTarget;

        if (!input) {
            return;
        }

        const inputId = input.id;

        if (!inputId) {
            return;
        }

        if (!this.uploadedFiles[inputId]) {
            this.uploadedFiles[inputId] = [];
        }

        const newFiles = Array.from(input.files || []);

        if (!newFiles.length) {
            return;
        }

        const isImage = inputId === 'fotografia';

        const invalidFiles = newFiles.filter(file => {

            if (isImage) {
                return !file.type.startsWith('image/');
            }

            return file.type !== 'application/pdf' &&
                !file.name.toLowerCase().endsWith('.pdf');
        });

        const $container =
            this.$(`#file-selected-${inputId}`);

        if (invalidFiles.length) {

            input.value = '';

            this.uploadedFiles[inputId] = [];

            $container.html(`
                <div class="text-danger custom-message fs-6">
                    ${
                        isImage
                            ? 'Solo se permiten imágenes.'
                            : 'Solo se permiten archivos PDF.'
                    }
                </div>
            `);

            $(input).addClass('is-invalid');

            return;
        }

        this.uploadedFiles[inputId] =
            this.uploadedFiles[inputId].concat(newFiles);

        // Eliminar duplicados
        this.uploadedFiles[inputId] =
            this.uploadedFiles[inputId].filter(
                (file, index, self) =>
                    index === self.findIndex(
                        f =>
                            f.name === file.name &&
                            f.size === file.size &&
                            f.lastModified === file.lastModified
                    )
            );

        this._refreshCustomFileInput(input);

        this._renderCustomFileList(
            $container[0],
            input
        );

        $(input).removeClass('is-invalid');
    },


    /**
     * Reconstruye input.files usando DataTransfer.
     */
    _refreshCustomFileInput(input) {

        const inputId = input.id;

        const files =
            this.uploadedFiles[inputId] || [];

        const dataTransfer = new DataTransfer();

        files.forEach(file => {
            dataTransfer.items.add(file);
        });

        input.files = dataTransfer.files;
    },


    /**
     * Renderiza los archivos seleccionados.
     */
    _renderCustomFileList(container, input) {

        if (!container) {
            return;
        }

        const inputId = input.id;

        const files =
            this.uploadedFiles[inputId] || [];

        container.innerHTML = '';

        if (!files.length) {
            return;
        }

        files.forEach((file, index) => {

            const fileItem =
                document.createElement('div');

            fileItem.className =
                'd-flex align-items-center ' +
                'justify-content-between ' +
                'border rounded-pill px-3 py-2 mb-2';

            fileItem.innerHTML = `
                <span class="text-success">
                    ${file.name} ✓
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
            .forEach(button => {

                button.addEventListener('click', ev => {

                    const index = parseInt(
                        ev.currentTarget.dataset.index,
                        10
                    );

                    this.uploadedFiles[inputId]
                        .splice(index, 1);

                    this._refreshCustomFileInput(input);

                    this._renderCustomFileList(
                        container,
                        input
                    );

                    // Si es obligatorio, volver a validar.
                    if (this._isRequiredCustomDocument(inputId)) {
                        this._validateCustomDocument(input);
                    }
                });
            });
    },


    // ---------------------------------------------------------
    // DOCUMENTOS OBLIGATORIOS
    // ---------------------------------------------------------

    /**
     * Define qué documentos son opcionales.
     *
     * Todo lo que NO esté aquí será obligatorio.
     */
    _isRequiredCustomDocument(inputId) {

        const optionalDocuments = [
            'acta-matrimonio',
            'hijos-menores',
            'cursos-realizados',
            'formulario-107',
        ];

        return !optionalDocuments.includes(inputId);
    },


    /**
     * Valida un documento individual.
     */
    _validateCustomDocument(input) {

        if (!input) {
            return true;
        }

        const inputId = input.id;

        const files =
            this.uploadedFiles[inputId] || [];

        const $input = $(input);

        const $container =
            this.$(`#file-selected-${inputId}`);

        const required =
            this._isRequiredCustomDocument(inputId);

        // -----------------------------------------------------
        // OPCIONAL SIN ARCHIVO
        // -----------------------------------------------------

        if (!required && !files.length) {

            $input.removeClass('is-invalid');

            return true;
        }

        // -----------------------------------------------------
        // OBLIGATORIO SIN ARCHIVO
        // -----------------------------------------------------

        if (required && !files.length) {

            $input.addClass('is-invalid');

            $container.html(`
                <div class="text-danger custom-message fs-6">
                    Campo obligatorio. Debe seleccionar un archivo.
                </div>
            `);

            return false;
        }

        // -----------------------------------------------------
        // VALIDAR TIPO
        // -----------------------------------------------------

        const isImage =
            inputId === 'fotografia';

        const invalidFiles =
            files.filter(file => {

                if (isImage) {
                    return !file.type.startsWith('image/');
                }

                return file.type !== 'application/pdf' &&
                    !file.name.toLowerCase().endsWith('.pdf');
            });

        if (invalidFiles.length) {

            $input.addClass('is-invalid');

            $container.html(`
                <div class="text-danger custom-message fs-6">
                    ${
                        isImage
                            ? 'Solo se permiten imágenes.'
                            : 'Solo se permiten archivos PDF.'
                    }
                </div>
            `);

            return false;
        }

        $input.removeClass('is-invalid');

        return true;
    },


    /**
     * Valida todos los documentos de la vista.
     */
    _validateCustomDocuments() {

        let isValid = true;

        const $inputs =
            this.$('#hr-job-recruitment-form input[type="file"]');

        $inputs.each((index, input) => {

            const valid =
                this._validateCustomDocument(input);

            if (!valid) {
                isValid = false;
            }
        });

        return isValid;
    },


    // ---------------------------------------------------------
    // CURRICULUM
    // ---------------------------------------------------------

    /**
     * Sobrescribimos la validación del curriculum
     * para utilizar la estructura nueva.
     */
    _validateCurriculum() {

        const $input =
            this.$('#curriculum-vitae');

        const $container =
            this.$('#file-selected-message');

        const files =
            this.uploadedFiles['curriculum-vitae'] || [];

        if (!files.length) {

            $input.addClass('is-invalid');

            $container.html(`
                <div class="text-danger custom-message fs-6">
                    Campo obligatorio.
                    Debe seleccionar al menos un archivo PDF.
                </div>
            `);

            return false;
        }

        const invalidFiles =
            files.filter(file => {

                return file.type !== 'application/pdf' &&
                    !file.name.toLowerCase().endsWith('.pdf');
            });

        if (invalidFiles.length) {

            $input.addClass('is-invalid');

            $container.html(`
                <div class="text-danger custom-message fs-6">
                    Solo se permiten archivos PDF.
                </div>
            `);

            return false;
        }

        $input.removeClass('is-invalid');

        return true;
    },


    // ---------------------------------------------------------
    // STEP 1
    // ---------------------------------------------------------

    /**
     * Extendemos la validación existente del módulo original.
     *
     * Primero ejecutamos la validación original.
     * Después agregamos nuestros documentos.
     */
    _validateCurrentStep1() {

        const originalValid =
            this._super(...arguments);

        const documentsValid =
            this._validateCustomDocuments();

        if (!documentsValid) {
            this._scrollToFirstError();
        }

        return originalValid && documentsValid;
    },

});