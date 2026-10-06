/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.MultistepFormCustom = publicWidget.registry.MultistepForm.extend({

    /**
     * @override
     */
    start() {
        // Mantener inicializaciones necesarias
        this._initializeForm();
        this._toggleFamilyKnownFields();
        this._toggleDisabilityFields();
        this._toggleParentescoField();
        this._toggleJobDisabilityFields();
        this._onChangeCountry({ currentTarget: this.$('#hr-country') });

        // Validaciones de campos conocidos
        this.$('input[name="knownPosee_1"]').on('change', () => {
            this._toggleFamilyKnownFields();
        });
        this.$('input[name="knownNombre_1"]').on('input', (ev) => {
            const $f = $(ev.currentTarget);
            $f.toggleClass('is-invalid', !$f.val().trim());
        });
        this.$('input[name="knownRelacion_1"]').on('change', () => {
            this._toggleParentescoField();
            this.$('input[name="knownRelacion_1"]').removeClass('is-invalid');
        });
        this.$('input[name="knownParentesco_1"]').on('input', (ev) => {
            const $f = $(ev.currentTarget);
            $f.toggleClass('is-invalid', !$f.val().trim());
        });
        this.$('input[name="studyOptions"]').on('change', () => {
            this.$('input[name="studyOptions"]').removeClass('is-invalid');
        });

        return this._super();
    },

    /**
     * @override
     * Opcional: habilitar el botón de educación desde el inicio
     */
    _initializeForm() {
        this.$('#add-experience').css({
            'opacity': '0.5',
            'pointer-events': 'none'
        });

        // 🔓 Habilitamos el botón de educación para que siempre se pueda añadir
        this.$('#add-education').css({
            'opacity': '1',
            'pointer-events': 'auto'
        });

        this._checkFieldsFilled();
        this._checkEducationFieldsFilled();
    },

    
    /**
     * Sobrescribimos la función _onNextClick
     */
    _onNextClick(ev) {
        ev.preventDefault();

        if (this._validateCurrentStep1()) {
            // Ocultar step 1
            this.$('#form-step-1').addClass('d-none');

            // Mostrar step 3 en lugar de step 2
            this.$('#form-step-3').removeClass('d-none');

            const numHijos = parseInt(this.$('#hr-hijos').val(), 10);
            this.$('#hr-hijos').prop('readonly', true);

            if (!isNaN(numHijos)) {
                const $hiddenHijos = this.$('input[name="numHijos"]');
                if ($hiddenHijos.length === 0) {
                    this.$('#hr-hijos').after(`<input type="hidden" name="numHijos" value="${numHijos}"/>`);
                } else {
                    $hiddenHijos.val(numHijos);
                }
            }

            // Generación de bloques familiares (igual que antes)
            if (this.familyBlocksGenerated) {
                return;
            }
            this.familyBlocksGenerated = true;

            const AUTO_FAMILY = ["Padre", "Madre", "Conyugue"];
            AUTO_FAMILY.forEach(tipo => {
                if (this.$(`.family-block[data-type="${tipo}"]`).length === 0) {
                    this.familyCount++;
                    const index = this.familyCount;

                    this._getFamilyBlock(tipo, index).then(blockHtml => {
                        const block = $(blockHtml);
                        const tipoVal = tipo === "Padre" ? "1" :
                                        tipo === "Madre" ? "2" :
                                        tipo === "Conyugue" ? "4" : tipo;

                        block.prepend(`<input type="hidden" name="famTipo_${index}" value="${tipoVal}"/>`);
                        block.prepend(`<input type="hidden" name="famIndex_${index}" value="${index}"/>`);
                        this.$('#family_container').append(block);

                        block.find(`input[name="famDisc_${index}"]`).on("change", () => {
                            this._toggleFamilyDisability(index);
                        });
                        this._toggleFamilyDisability(index);
                    });
                }
            });

            if (!isNaN(numHijos) && numHijos > 0) {
                for (let i = 0; i < numHijos; i++) {
                    this.familyCount++;
                    const index = this.familyCount;

                    this._getFamilyBlock("Hijo", index).then(blockHtml => {
                        const block = $(blockHtml);
                        block.prepend(`<input type="hidden" name="famTipo_${index}" value="5"/>`);
                        block.prepend(`<input type="hidden" name="famIndex_${index}" value="${index}"/>`);
                        this.$('#family_container').append(block);

                        block.find(`input[name="famDisc_${index}"]`).on("change", () => {
                            this._toggleFamilyDisability(index);
                        });
                        this._toggleFamilyDisability(index);
                    });
                }
            }
        }
    },

        /**
     * Sobrescribimos la función _onPrevClick para regresar de step 3 a step 1
     */
    _onPrevClick(ev) {
        ev.preventDefault();

        // Ocultar step 3
        this.$('#form-step-3').addClass('d-none');

        // Mostrar step 1 directamente
        this.$('#form-step-1').removeClass('d-none');
    },
});
