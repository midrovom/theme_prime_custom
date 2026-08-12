/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.MultistepForm.include({

    start: function () {

        const result = this._super.apply(this, arguments);
        Promise.resolve(result).then(() => {
            this._initCustomCandidateFields();
        });

        return result;
    },

    _initCustomCandidateFields: function () {

        if (this._customCandidateFieldsInitialized) {
            return;
        }

        this._customCandidateFieldsInitialized = true;
        this._customPdfFields = [
            {
                selector: '#cedula-votacion',
                name: 'cedulaVotacion',
                message: 'Debe adjuntar la cédula y certificado de votación.'
            },
            {
                selector: '#historia-laboral-iess',
                name: 'historiaLaboralIess',
                message: 'Debe adjuntar la historia laboral del IESS.'
            },
            {
                selector: '#acta-matrimonio',
                name: 'actaMatrimonio',
                message: 'Debe adjuntar el acta de matrimonio.'
            },
            {
                selector: '#hijos-menores',
                name: 'hijosMenores',
                message: 'Debe adjuntar los documentos de hijos.'
            },
            {
                selector: '#estudios-senecyt',
                name: 'estudiosSenecyt',
                message: 'Debe adjuntar el certificado o título.'
            },
            {
                selector: '#cursos-realizados',
                name: 'cursosRealizados',
                message: 'Debe adjuntar los certificados de cursos.'
            },
            {
                selector: '#recomendaciones',
                name: 'recomendaciones',
                message: 'Debe adjuntar las recomendaciones.'
            },
            {
                selector: '#certificados-trabajo',
                name: 'certificadosTrabajo',
                message: 'Debe adjuntar los certificados de trabajo.'
            },
            {
                selector: '#planilla-servicios',
                name: 'planillaServicios',
                message: 'Debe adjuntar la planilla de servicios básicos.'
            },
            {
                selector: '#croquis-domicilio',
                name: 'croquisDomicilio',
                message: 'Debe adjuntar el croquis del domicilio.'
            },
            {
                selector: '#formulario-107',
                name: 'formulario107',
                message: 'Debe adjuntar el formulario 107.'
            },
            {
                selector: '#cuenta-banco-internacional',
                name: 'cuentaBancoInternacional',
                message: 'Debe adjuntar la cuenta bancaria.'
            },
            {
                selector: '#certificado-salud',
                name: 'certificadoSalud',
                message: 'Debe adjuntar el certificado de salud.'
            },
        ];

        /*
         * ========================================================
         * FOTOGRAFÍA
         * ========================================================
         */

        this._customImageFields = [
            {
                selector: '#fotografia',
                name: 'fotografia',
                message: 'Debe adjuntar una fotografía.'
            },
        ];

        /*
         * ========================================================
         * INICIALIZAR PDF
         * ========================================================
         */

        this._customPdfFields.forEach((field) => {
            this._initCustomFileField(field);
        });

        /*
         * ========================================================
         * INICIALIZAR IMÁGENES
         * ========================================================
         */

        this._customImageFields.forEach((field) => {
            this._initCustomImageField(field);
        });
    },


    // ============================================================
    // INICIALIZAR PDF
    // ============================================================

    _initCustomFileField: function (field) {

        const $input = this.$(field.selector);

        if (!$input.length) {
            return;
        }

        $input.each((index, input) => {

            if ($(input).data("custom-file-initialized")) {
                return;
            }

            $(input).data(
                "custom-file-initialized",
                true
            );

            /*
             * Cada input tiene su propio array.
             *
             * Esto permite que cada documento pueda tener
             * varios archivos si posteriormente agregas
             * multiple.
             */
            input._customUploadedFiles = [];

            $(input).on(
                "change.customCandidateFile",
                (ev) => {
                    this._onCustomFileSelected(
                        ev,
                        field
                    );
                }
            );
        });
    },


    // ============================================================
    // SELECCIONAR PDF
    // ============================================================

    _onCustomFileSelected: function (ev, field) {

        const input = ev.currentTarget;
        const $input = $(input);

        const newFiles = Array.from(
            input.files || []
        );

        /*
         * No hay archivo.
         */
        if (!newFiles.length) {

            input._customUploadedFiles = [];

            this._renderCustomFileList(input, field);

            return;
        }

        /*
         * Validar PDF.
         */
        const invalidFiles = newFiles.filter((file) => {

            return file.type !== "application/pdf" &&
                !file.name.toLowerCase().endsWith(".pdf");
        });

        if (invalidFiles.length) {

            input.value = "";
            input._customUploadedFiles = [];

            $input.addClass("is-invalid");

            this._renderCustomFileError(
                input,
                field,
                "Solo se permiten archivos PDF."
            );

            return;
        }

        /*
         * Guardar archivos.
         */
        input._customUploadedFiles = newFiles;

        /*
         * Reconstruir input.files.
         */
        this._refreshCustomFileInput(input);

        /*
         * Mostrar archivos.
         */
        this._renderCustomFileList(
            input,
            field
        );

        /*
         * Validar.
         */
        this._validateCustomFileField(
            input,
            field
        );
    },


    // ============================================================
    // RECONSTRUIR INPUT FILE
    // ============================================================

    _refreshCustomFileInput: function (input) {

        const dataTransfer = new DataTransfer();

        const files =
            input._customUploadedFiles || [];

        files.forEach((file) => {
            dataTransfer.items.add(file);
        });

        input.files = dataTransfer.files;
    },


    // ============================================================
    // CONTENEDOR VISUAL
    // ============================================================

    _getCustomFileContainer: function (input) {

        const $input = $(input);

        /*
         * En tu XML tienes:
         *
         * <div class="row">
         *     ...
         *     <input>
         *     <label>
         *     <div id="file-selected-xxx">
         *
         * Por eso buscamos primero por el id
         * file-selected-...
         */

        const id = input.id;

        if (id) {

            const $container = this.$(
                `#file-selected-${id}`
            );

            if ($container.length) {
                return $container;
            }
        }

        /*
         * Fallback.
         */
        let $container = $input
            .closest(".row")
            .find(".custom-message");

        if (!$container.length) {
            $container = $input.parent();
        }

        return $container;
    },


    // ============================================================
    // MOSTRAR ARCHIVOS
    // ============================================================

    _renderCustomFileList: function (
        input,
        field
    ) {

        const $container =
            this._getCustomFileContainer(input);

        $container.empty();

        const files =
            input._customUploadedFiles || [];

        if (!files.length) {

            return;
        }

        files.forEach((file, index) => {

            const $file = $(`
                <div class="
                    d-flex
                    align-items-center
                    justify-content-between
                    border
                    rounded-pill
                    px-3
                    py-2
                    mb-2
                ">
                    <span class="text-success">
                        ${_.escape(file.name)}
                    </span>

                    <button
                        type="button"
                        class="btn btn-sm btn-danger o_custom_remove_file"
                        data-index="${index}">
                        ×
                    </button>
                </div>
            `);

            $file
                .find(".o_custom_remove_file")
                .on(
                    "click.customCandidateFile",
                    (ev) => {

                        ev.preventDefault();
                        ev.stopPropagation();

                        const index = parseInt(
                            $(ev.currentTarget)
                                .data("index"),
                            10
                        );

                        this._removeCustomFile(
                            input,
                            field,
                            index
                        );
                    }
                );

            $container.append($file);
        });
    },


    // ============================================================
    // ERROR DE ARCHIVO
    // ============================================================

    _renderCustomFileError: function (
        input,
        field,
        message
    ) {

        const $container =
            this._getCustomFileContainer(input);

        $container.html(`
            <div class="text-danger custom-message fs-6">
                ${_.escape(message)}
            </div>
        `);
    },


    // ============================================================
    // ELIMINAR PDF
    // ============================================================

    _removeCustomFile: function (
        input,
        field,
        index
    ) {

        if (!input._customUploadedFiles) {
            input._customUploadedFiles = [];
        }

        input._customUploadedFiles.splice(
            index,
            1
        );

        this._refreshCustomFileInput(
            input
        );

        this._renderCustomFileList(
            input,
            field
        );

        this._validateCustomFileField(
            input,
            field
        );
    },


    // ============================================================
    // VALIDAR PDF INDIVIDUAL
    // ============================================================

    _validateCustomFileField: function (
        input,
        field
    ) {

        const $input = $(input);

        const files =
            input._customUploadedFiles || [];

        /*
         * Obligatorio.
         */
        if (!files.length) {

            $input.addClass("is-invalid");

            this._renderCustomFileError(
                input,
                field,
                field.message
            );

            return false;
        }

        /*
         * Validar PDF.
         */
        const invalidFiles = files.filter(
            (file) => {

                return file.type !== "application/pdf" &&
                    !file.name
                        .toLowerCase()
                        .endsWith(".pdf");
            }
        );

        if (invalidFiles.length) {

            $input.addClass("is-invalid");

            this._renderCustomFileError(
                input,
                field,
                "Solo se permiten archivos PDF."
            );

            return false;
        }

        $input.removeClass("is-invalid");

        return true;
    },


    // ============================================================
    // VALIDAR TODOS LOS PDF
    // ============================================================

    _validateCustomPdfFields: function () {

        let isValid = true;

        this._customPdfFields.forEach(
            (field) => {

                const $input =
                    this.$(field.selector);

                if (!$input.length) {
                    return;
                }

                $input.each(
                    (index, input) => {

                        const valid =
                            this._validateCustomFileField(
                                input,
                                field
                            );

                        if (!valid) {
                            isValid = false;
                        }
                    }
                );
            }
        );

        return isValid;
    },


    // ============================================================
    // INICIALIZAR FOTOGRAFÍA
    // ============================================================

    _initCustomImageField: function (field) {

        const $input = this.$(
            field.selector
        );

        if (!$input.length) {
            return;
        }

        $input.each((index, input) => {

            if ($(input).data(
                "custom-image-initialized"
            )) {
                return;
            }

            $(input).data(
                "custom-image-initialized",
                true
            );

            $(input).on(
                "change.customCandidateImage",
                (ev) => {

                    this._onCustomImageSelected(
                        ev,
                        field
                    );
                }
            );
        });
    },


    // ============================================================
    // SELECCIONAR FOTOGRAFÍA
    // ============================================================

    _onCustomImageSelected: function (
        ev,
        field
    ) {

        const input = ev.currentTarget;
        const $input = $(input);

        const file =
            input.files && input.files.length
                ? input.files[0]
                : null;

        if (!file) {

            $input.addClass(
                "is-invalid"
            );

            this._renderCustomFileError(
                input,
                field,
                field.message
            );

            return;
        }

        /*
         * Validar imagen.
         */
        if (!file.type.startsWith("image/")) {

            input.value = "";

            $input.addClass(
                "is-invalid"
            );

            this._renderCustomFileError(
                input,
                field,
                "Solo se permiten imágenes."
            );

            return;
        }

        $input.removeClass(
            "is-invalid"
        );

        const $container =
            this._getCustomFileContainer(
                input
            );

        $container.html(`
            <div class="
                d-flex
                align-items-center
                justify-content-between
                border
                rounded-pill
                px-3
                py-2
            ">
                <span class="text-success">
                    ${_.escape(file.name)}
                </span>

                <button
                    type="button"
                    class="btn btn-sm btn-danger o_custom_remove_image">
                    ×
                </button>
            </div>
        `);

        $container
            .find(".o_custom_remove_image")
            .on(
                "click.customCandidateImage",
                (event) => {

                    event.preventDefault();

                    input.value = "";

                    $input.addClass(
                        "is-invalid"
                    );

                    $container.empty();

                    this._renderCustomFileError(
                        input,
                        field,
                        field.message
                    );
                }
            );
    },


    // ============================================================
    // VALIDAR FOTOGRAFÍA
    // ============================================================

    _validateCustomImageFields: function () {

        let isValid = true;

        this._customImageFields.forEach(
            (field) => {

                const $input =
                    this.$(field.selector);

                if (!$input.length) {
                    return;
                }

                $input.each(
                    (index, input) => {

                        const files =
                            input.files || [];

                        if (!files.length) {

                            $(input)
                                .addClass(
                                    "is-invalid"
                                );

                            this._renderCustomFileError(
                                input,
                                field,
                                field.message
                            );

                            isValid = false;

                            return;
                        }

                        const file =
                            files[0];

                        if (
                            !file.type.startsWith(
                                "image/"
                            )
                        ) {

                            $(input)
                                .addClass(
                                    "is-invalid"
                                );

                            isValid = false;

                            return;
                        }

                        $(input)
                            .removeClass(
                                "is-invalid"
                            );
                    }
                );
            }
        );

        return isValid;
    },


    // ============================================================
    // VALIDACIÓN STEP 1
    // ============================================================

    _validateCurrentStep1: function () {

        /*
         * Ejecutamos TODA la validación original.
         *
         * Aquí ya se valida:
         *
         * - fotografía de perfil
         * - nombres
         * - edad
         * - dirección
         * - país
         * - provincia
         * - teléfono
         * - email
         * - cédula
         * - nacionalidad
         * - curriculum-vitae
         * - estado civil
         * etc.
         */
        const originalValid =
            this._super.apply(
                this,
                arguments
            );

        /*
         * Nuestros PDF.
         */
        const pdfValid =
            this._validateCustomPdfFields();

        /*
         * Nuestra fotografía.
         */
        const imageValid =
            this._validateCustomImageFields();

        /*
         * Si cualquier validación falla,
         * permanecemos en Step 1.
         */
        if (
            !originalValid ||
            !pdfValid ||
            !imageValid
        ) {

            this._scrollToFirstError();

            return false;
        }

        return true;
    },


    // ============================================================
    // SCROLL
    // ============================================================

    _scrollToFirstError: function () {

        const $firstError =
            this.$(".is-invalid").first();

        if ($firstError.length) {

            $("html, body").animate({
                scrollTop:
                    $firstError.offset().top - 100
            }, 500);
        }
    },

});