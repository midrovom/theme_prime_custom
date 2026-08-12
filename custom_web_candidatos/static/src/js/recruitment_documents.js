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

    /**
     * Inicialización de funcionalidades personalizadas.
     */
    _initCustomCandidateFields: function () {
        const self = this;

        // Evitamos inicializarlo dos veces.
        if (this._customCandidateFieldsInitialized) {
            return;
        }

        this._customCandidateFieldsInitialized = true;

        /*
         * ---------------------------------------------------------
         * 1. CAMPOS DE ARCHIVO
         * ---------------------------------------------------------
         *
         * Agrega aquí los nombres/IDs de los campos que deben
         * comportarse como el curriculum:
         *
         * - seleccionar archivo
         * - mostrar archivo seleccionado
         * - permitir eliminarlo
         */
        const fileSelectors = [
            'input[type="file"][name="documento_identidad"]',
            'input[type="file"][name="certificado"]',
            'input[type="file"][name="titulo"]',
        ];

        fileSelectors.forEach(function (selector) {
            self._initCustomFileField(selector);
        });

        /*
         * ---------------------------------------------------------
         * 2. CAMPOS OBLIGATORIOS
         * ---------------------------------------------------------
         *
         * Estos campos serán obligatorios.
         *
         * Puedes utilizar name:
         *
         * input[name="..."]
         * select[name="..."]
         * textarea[name="..."]
         */
        const requiredSelectors = [
            '[name="documento_identidad"]',
            '[name="certificado"]',
            '[name="titulo"]',
        ];

        requiredSelectors.forEach(function (selector) {
            self._setCustomRequired(selector);
        });
    },

    /**
     * Hace que un campo sea obligatorio sin modificar el
     * funcionamiento original del formulario.
     */
    _setCustomRequired: function (selector) {
        const $fields = this.$(selector);

        if (!$fields.length) {
            return;
        }

        $fields.each(function () {
            const $field = $(this);

            // HTML5
            $field.attr("required", "required");

            /*
             * Odoo utiliza muchas veces .o_required_modifier
             * para indicar visualmente que un campo es obligatorio.
             */
            $field.addClass("o_required_modifier");

            /*
             * Añadimos el indicador visual solamente si no existe.
             */
            const $container = $field.closest(
                ".form-group, .mb-3, .o_field_widget"
            );

            if ($container.length && !$container.find(".o_custom_required_star").length) {
                const $label = $container.find("label").first();

                if ($label.length && !$label.find(".o_custom_required_star").length) {
                    $label.append(
                        ' <span class="o_custom_required_star text-danger">*</span>'
                    );
                }
            }
        });
    },

    /**
     * Añade el comportamiento de eliminación a un input file.
     *
     * No sustituye el comportamiento original del input.
     */
    _initCustomFileField: function (selector) {
        const self = this;

        this.$(selector).each(function () {
            const input = this;

            /*
             * No inicializamos dos veces el mismo input.
             */
            if ($(input).data("custom-file-initialized")) {
                return;
            }

            $(input).data("custom-file-initialized", true);

            /*
             * Guardamos el nombre del archivo seleccionado.
             */
            $(input).on("change.customCandidateFile", function () {
                self._showCustomFileInfo(input);
            });

            /*
             * Si ya existe un archivo al cargar el formulario,
             * mostramos también el control de eliminación.
             */
            if (input.files && input.files.length) {
                self._showCustomFileInfo(input);
            }
        });
    },

    /**
     * Muestra información del archivo y botón "Eliminar".
     */
    _showCustomFileInfo: function (input) {
        const $input = $(input);

        if (!input.files || !input.files.length) {
            return;
        }

        const file = input.files[0];

        /*
         * Buscamos el contenedor del input.
         */
        let $container = $input.closest(
            ".form-group, .mb-3, .o_field_widget"
        );

        if (!$container.length) {
            $container = $input.parent();
        }

        /*
         * Eliminamos solamente nuestra información anterior.
         */
        $container.find(".o_custom_file_info").remove();

        const $info = $(`
            <div class="o_custom_file_info mt-2">
                <span class="text-muted">
                    ${_.escape(file.name)}
                </span>

                <button
                    type="button"
                    class="btn btn-sm btn-link text-danger o_custom_remove_file">
                    Eliminar
                </button>
            </div>
        `);

        $container.append($info);

        /*
         * Botón eliminar.
         */
        $info.find(".o_custom_remove_file").on(
            "click.customCandidateFile",
            function (ev) {
                ev.preventDefault();
                ev.stopPropagation();

                self._removeCustomFile(input);
            }
        );
    },

    /**
     * Elimina el archivo seleccionado.
     */
    _removeCustomFile: function (input) {
        const $input = $(input);

        /*
         * La forma correcta de limpiar un <input type="file">
         * es asignarle una cadena vacía.
         */
        $input.val("");

        /*
         * Disparamos change para que cualquier lógica original
         * que dependa de ese evento pueda reaccionar.
         */
        $input.trigger("change");

        /*
         * Eliminamos nuestra interfaz.
         */
        $input
            .closest(".form-group, .mb-3, .o_field_widget, parent")
            .find(".o_custom_file_info")
            .remove();

        /*
         * Fallback por si el selector anterior no encontró
         * correctamente el contenedor.
         */
        $input.parent().find(".o_custom_file_info").remove();
    },

});