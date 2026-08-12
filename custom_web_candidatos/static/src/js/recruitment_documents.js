/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.CandidatosWidget.include({

    start: function () {
        var self = this;

        return this._super.apply(this, arguments).then(function () {
            self._initCustomFileFields();
            self._initCustomRequiredFields();

        });
    },

    _initCustomFileFields: function () {

        var self = this;

        this.$el
            .find('input[type="file"][data-custom-file="1"]')
            .each(function () {

                var $input = $(this);

                self._prepareCustomFileField($input);
            });
    },

    _prepareCustomFileField: function ($input) {

        var self = this;

        $input.off(
            'change.custom_web_candidatos'
        );

        $input.on(
            'change.custom_web_candidatos',
            function () {

                var file = this.files && this.files[0];

                if (!file) {
                    return;
                }

                self._showCustomFileDeleteButton(
                    $input,
                    file
                );
            }
        );
    },

    /**
     * Muestra el botón para eliminar el archivo seleccionado.
     */
    _showCustomFileDeleteButton: function ($input, file) {

        var $container = $input.closest(
            '.o_website_form_field, .form-group, .field-file'
        );

        if (!$container.length) {
            $container = $input.parent();
        }

        // Eliminamos únicamente nuestro botón anterior.
        $container
            .find('.o_custom_delete_file')
            .remove();

        var $deleteButton = $('<button/>', {
            type: 'button',
            class: 'btn btn-link text-danger o_custom_delete_file',
            text: 'Eliminar archivo',
        });

        $deleteButton.on(
            'click.custom_web_candidatos',
            function () {

                self._deleteCustomFile(
                    $input,
                    $container
                );
            }.bind(this)
        );

        $container.append($deleteButton);
    },

    /**
     * Elimina el archivo seleccionado.
     */
    _deleteCustomFile: function ($input, $container) {

        // Limpiamos el input file.
        $input.val('');

        // Eliminamos solamente nuestros elementos.
        $container
            .find('.o_custom_delete_file')
            .remove();

        // Eliminamos posible preview custom.
        $container
            .find('.o_custom_file_preview')
            .remove();
    },

    // ============================================================
    // CAMPOS OBLIGATORIOS
    // ============================================================

    /**
     * Inicializa los campos marcados como obligatorios.
     *
     * Ejemplo:
     *
     * <input
     *     type="file"
     *     data-custom-required="1"
     * >
     */
    _initCustomRequiredFields: function () {

        var self = this;

        this.$el
            .find('[data-custom-required="1"]')
            .each(function () {

                self._markCustomFieldRequired(
                    $(this)
                );
            });
    },

    /**
     * Marca visualmente el campo como obligatorio.
     */
    _markCustomFieldRequired: function ($field) {

        var $label = this.$el.find(
            'label[for="' + $field.attr('id') + '"]'
        );

        if ($label.length) {

            if (!$label.find('.o_custom_required').length) {

                $label.append(
                    $('<span/>', {
                        class: 'text-danger o_custom_required',
                        text: ' *',
                    })
                );
            }
        }

        // Para inputs HTML normales utilizamos required.
        $field.attr('required', 'required');
    },

    /**
     * Validación adicional de nuestros campos.
     *
     * No sustituye la validación original de Odoo.
     */
    _validateCustomRequiredFields: function () {

        var valid = true;

        this.$el
            .find('[data-custom-required="1"]')
            .each(function () {

                var $field = $(this);

                var value = $field.val();

                if (!value) {

                    valid = false;

                    $field.addClass(
                        'is-invalid'
                    );

                    if (
                        !$field.next(
                            '.o_custom_required_error'
                        ).length
                    ) {

                        $('<div/>', {
                            class:
                                'invalid-feedback o_custom_required_error',
                            text:
                                'Este campo es obligatorio.',
                        }).insertAfter($field);
                    }

                } else {

                    $field.removeClass(
                        'is-invalid'
                    );

                    $field.next(
                        '.o_custom_required_error'
                    ).remove();
                }
            });

        return valid;
    },

});