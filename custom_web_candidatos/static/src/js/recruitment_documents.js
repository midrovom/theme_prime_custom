/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import { _t } from "@web/core/l10n/translation";

publicWidget.registry.MultistepForm = publicWidget.Widget.extend({

    selector: '#hr_job_recruitment_form',

    events: {
        // Curriculum
        'change #curriculum-vitae': '_onCurriculumSelected',

        // Documentos adicionales
        'change #fotografia': '_onFileSelected',
        'change #cedula-votacion': '_onFileSelected',
        'change #historia-laboral-iess': '_onFileSelected',
        'change #estudios-senecyt': '_onFileSelected',
        'change #recomendaciones': '_onFileSelected',
        'change #certificados-trabajo': '_onFileSelected',
        'change #planilla-servicios': '_onFileSelected',
        'change #croquis-domicilio': '_onFileSelected',
        'change #cuenta-banco-internacional': '_onFileSelected',
        'change #certificado-salud': '_onFileSelected',
        'change #acta-matrimonio': '_onFileSelected',
        'change #hijos-menores': '_onFileSelected',
        'change #cursos-realizados': '_onFileSelected',
        'change #formulario-107': '_onFileSelected',
    },

    //---------------------------------------------------------------------- 
    // Init
    //----------------------------------------------------------------------

    init() {
        this._super(...arguments);

        // Archivos del curriculum
        this.uploadedCurriculumFiles = [];

        // Archivos de los demás documentos
        this.uploadedFiles = {};
    },

    //---------------------------------------------------------------------- 
    // Private
    //----------------------------------------------------------------------

    /**
     * Inicializa el arreglo de archivos de un campo.
     */
    _getUploadedFiles(inputId) {

        if (!this.uploadedFiles[inputId]) {
            this.uploadedFiles[inputId] = [];
        }

        return this.uploadedFiles[inputId];
    },

    //---------------------------------------------------------------------- 
    // Curriculum
    //----------------------------------------------------------------------

    /**
     * Maneja la selección de archivos del Curriculum Vitae.
     *
     * Permite seleccionar varios PDF y conservar los archivos
     * previamente seleccionados.
     */
    _onCurriculumSelected(ev) {

        const input = ev.currentTarget;
        const newFiles = Array.from(input.files || []);
        const container = document.getElementById(
            "file-selected-message"
        );

        if (!container) {
            return;
        }

        // Si no se seleccionó nada
        if (!newFiles.length) {
            return;
        }

        // Validar PDF
        const invalidFiles = newFiles.filter(file => {
            return file.type !== "application/pdf" &&
                !file.name.toLowerCase().endsWith(".pdf");
        });

        if (invalidFiles.length > 0) {

            container.innerHTML = `
                <div class="text-danger custom-message fs-6">
                    Solo se permiten archivos PDF.
                </div>
            `;

            input.value = "";
            return;
        }

        // Mantener los archivos anteriores
        this.uploadedCurriculumFiles =
            this.uploadedCurriculumFiles.concat(newFiles);

        // Evitar duplicados por nombre
        this.uploadedCurriculumFiles =
            this.uploadedCurriculumFiles.filter(
                (file, index, self) =>
                    index === self.findIndex(
                        f => f.name === file.name
                    )
            );

        // Reconstruir input
        this._refreshCurriculumInput(input);

        // Mostrar archivos
        this._renderCurriculumList(container, input);

        // Quitar error si ya existe un archivo
        this._validateCurriculum();
    },

    /**
     * Reconstruye el input del Curriculum manteniendo
     * todos los archivos seleccionados.
     */
    _refreshCurriculumInput(input) {

        const dataTransfer = new DataTransfer();

        this.uploadedCurriculumFiles.forEach(file => {
            dataTransfer.items.add(file);
        });

        input.files = dataTransfer.files;
    },

    /**
     * Renderiza la lista de archivos del Curriculum.
     */
    _renderCurriculumList(container, input) {

        container.innerHTML = "";

        if (!this.uploadedCurriculumFiles.length) {

            container.innerHTML = `
                <div class="text-danger custom-message fs-6">
                    No se seleccionó ningún archivo.
                </div>
            `;

            return;
        }

        this.uploadedCurriculumFiles.forEach((file, index) => {

            const fileItem = document.createElement("div");

            fileItem.className =
                "d-flex align-items-center justify-content-between " +
                "border rounded-pill px-3 py-2 mb-2";

            fileItem.innerHTML = `
                <span class="text-success">
                    ${file.name}
                </span>

                <button
                    type="button"
                    class="btn btn-sm btn-danger remove-curriculum-file"
                    data-index="${index}">
                    ×
                </button>
            `;

            container.appendChild(fileItem);
        });

        container
            .querySelectorAll(".remove-curriculum-file")
            .forEach(button => {

                button.addEventListener("click", (e) => {

                    const index = parseInt(
                        e.currentTarget.dataset.index
                    );

                    this.uploadedCurriculumFiles.splice(index, 1);

                    this._refreshCurriculumInput(input);

                    this._renderCurriculumList(
                        container,
                        input
                    );

                    this._validateCurriculum();
                });
            });
    },

    /**
     * Valida que exista al menos un Curriculum Vitae.
     */
    _validateCurriculum() {

        const $input = this.$('#curriculum-vitae');
        const $container = this.$('#file-selected-message');

        const hasFiles =
            this.uploadedCurriculumFiles &&
            this.uploadedCurriculumFiles.length > 0;

        // No existe ningún archivo
        if (!hasFiles) {

            $input.addClass('is-invalid');

            $container.html(`
                <div class="text-danger custom-message fs-6">
                    Campo obligatorio. Debe seleccionar al menos un archivo PDF.
                </div>
            `);

            return false;
        }

        // Validar que todos sean PDF
        const invalidFiles =
            this.uploadedCurriculumFiles.filter(file => {

                return file.type !== "application/pdf" &&
                    !file.name.toLowerCase().endsWith(".pdf");

            });

        if (invalidFiles.length > 0) {

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

    //---------------------------------------------------------------------- 
    // Documentos adicionales
    //----------------------------------------------------------------------

    /**
     * Maneja los archivos de los documentos adicionales.
     *
     * Cada input mantiene sus propios archivos.
     */
    _onFileSelected(ev) {

        const input = ev.currentTarget;
        const inputId = input.id;

        const newFiles = Array.from(input.files || []);

        const container = document.getElementById(
            `file-selected-${inputId}`
        );

        if (!container) {
            return;
        }

        if (!newFiles.length) {
            return;
        }

        // Fotografía permite imágenes
        const invalidFiles = newFiles.filter(file => {

            if (inputId === "fotografia") {
                return !file.type.startsWith("image/");
            }

            return file.type !== "application/pdf" &&
                !file.name.toLowerCase().endsWith(".pdf");
        });

        if (invalidFiles.length > 0) {

            container.innerHTML = `
                <div class="text-danger custom-message fs-6">
                    Solo se permiten archivos ${
                        inputId === "fotografia"
                            ? "de imagen"
                            : "PDF"
                    }.
                </div>
            `;

            input.value = "";
            return;
        }

        // Obtener archivos específicos de este campo
        const files = this._getUploadedFiles(inputId);

        // Agregar nuevos archivos
        this.uploadedFiles[inputId] =
            files.concat(newFiles);

        // Evitar duplicados
        this.uploadedFiles[inputId] =
            this.uploadedFiles[inputId].filter(
                (file, index, self) =>
                    index === self.findIndex(
                        f => f.name === file.name
                    )
            );

        // Reconstruir input
        this._refreshFileInput(input);

        // Renderizar
        this._renderFileList(
            container,
            input
        );

        // Validar este documento
        this._validateDocumentField(inputId);
    },

    /**
     * Reconstruye el input manteniendo todos los archivos
     * seleccionados para ese campo.
     */
    _refreshFileInput(input) {

        const files = this._getUploadedFiles(input.id);

        const dataTransfer = new DataTransfer();

        files.forEach(file => {
            dataTransfer.items.add(file);
        });

        input.files = dataTransfer.files;
    },

    /**
     * Renderiza los archivos de un documento.
     */
    _renderFileList(container, input) {

        container.innerHTML = "";

        const files = this._getUploadedFiles(input.id);

        if (!files.length) {

            container.innerHTML = `
                <div class="text-danger custom-message fs-6">
                    No se seleccionó ningún archivo.
                </div>
            `;

            return;
        }

        files.forEach((file, index) => {

            const fileItem = document.createElement("div");

            fileItem.className =
                "d-flex align-items-center justify-content-between " +
                "border rounded-pill px-3 py-2 mb-2";

            fileItem.innerHTML = `
                <span class="text-success">
                    ${file.name}
                </span>

                <button
                    type="button"
                    class="btn btn-sm btn-danger remove-file"
                    data-index="${index}">
                    ×
                </button>
            `;

            container.appendChild(fileItem);
        });

        // Eventos eliminar
        container
            .querySelectorAll(".remove-file")
            .forEach(button => {

                button.addEventListener("click", (e) => {

                    const index = parseInt(
                        e.currentTarget.dataset.index
                    );

                    const files =
                        this._getUploadedFiles(input.id);

                    files.splice(index, 1);

                    this._refreshFileInput(input);

                    this._renderFileList(
                        container,
                        input
                    );

                    this._validateDocumentField(
                        input.id
                    );
                });
            });
    },

    /**
     * Valida un documento específico.
     */
    _validateDocumentField(inputId) {

        const $input = this.$(`#${inputId}`);

        const container =
            document.getElementById(
                `file-selected-${inputId}`
            );

        const files =
            this._getUploadedFiles(inputId);

        if (!files.length) {

            $input.addClass('is-invalid');

            if (container) {
                container.innerHTML = `
                    <div class="text-danger custom-message fs-6">
                        Campo obligatorio. Debe seleccionar un archivo.
                    </div>
                `;
            }

            return false;
        }

        $input.removeClass('is-invalid');

        return true;
    },

    /**
     * Valida todos los documentos que sean obligatorios.
     *
     * Agrega aquí los IDs que realmente sean requeridos.
     */
    _validateRequiredDocuments() {

        const requiredDocuments = [
            'fotografia',
            'cedula-votacion',
            'historia-laboral-iess',
            'estudios-senecyt',
            'recomendaciones',
            'certificados-trabajo',
            'planilla-servicios',
            'croquis-domicilio',
            'cuenta-banco-internacional',
            'certificado-salud',
            'acta-matrimonio',
            'hijos-menores',
            'cursos-realizados',
            'formulario-107',
        ];

        let isValid = true;

        requiredDocuments.forEach(inputId => {

            const valid =
                this._validateDocumentField(inputId);

            if (!valid) {
                isValid = false;
            }
        });

        if (!isValid) {
            this._scrollToFirstError();
        }

        return isValid;
    },

    /**
     * Valida todos los documentos.
     *
     * Curriculum + documentos adicionales.
     */
    _validateAllDocuments() {

        const curriculumValid =
            this._validateCurriculum();

        const documentsValid =
            this._validateRequiredDocuments();

        return curriculumValid && documentsValid;
    },

    /**
     * Llevar al primer campo con error.
     */
    _scrollToFirstError() {

        const $firstError =
            this.$('.is-invalid').first();

        if ($firstError.length) {

            $('html, body').animate({
                scrollTop:
                    $firstError.offset().top - 100
            }, 500);
        }
    },
});