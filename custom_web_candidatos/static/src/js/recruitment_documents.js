/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import { _t } from "@web/core/l10n/translation";

publicWidget.registry.MultistepForm = publicWidget.Widget.extend({
    selector: '#hr_job_recruitment_form',

    events: {
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
    // Private
    //----------------------------------------------------------------------

    // función para mostrar archivos seleccionados
    _onFileSelected(ev) {
        const input = ev.currentTarget;
        const newFiles = Array.from(input.files);
        const container = document.getElementById(`file-selected-${input.id}`);

        if (!this.uploadedFiles) {
            this.uploadedFiles = [];
        }

        // Validar que sean PDF (excepto fotografía que es imagen)
        const invalidFiles = newFiles.filter(file => {
            if (input.id === "fotografia") {
                return !file.type.startsWith("image/");
            }
            return file.type !== "application/pdf" && !file.name.toLowerCase().endsWith(".pdf");
        });

        if (invalidFiles.length > 0) {
            container.innerHTML = `
                <div class="text-danger custom-message fs-6">
                    Solo se permiten archivos ${input.id === "fotografia" ? "de imagen" : "PDF"}.
                </div>
            `;
            input.value = "";
            return;
        }

        // Agregar nuevos archivos evitando duplicados por nombre
        this.uploadedFiles = this.uploadedFiles.concat(newFiles);
        this.uploadedFiles = this.uploadedFiles.filter(
            (file, index, self) => index === self.findIndex(f => f.name === file.name)
        );

        // Refrescar input y renderizar lista
        this._refreshFileInput(input);
        this._renderFileList(container, input);
    },

    _refreshFileInput(input) {
        input.value = "";
    },

    _renderFileList(container, input) {
        container.innerHTML = "";
        this.uploadedFiles.forEach((file, index) => {
            container.innerHTML += `
                <div>
                    ${file.name}
                    <button type="button" class="btn btn-sm btn-danger remove-file" data-index="${index}">
                        Quitar
                    </button>
                </div>
            `;
        });

        // Enganchar botones de quitar
        container.querySelectorAll(".remove-file").forEach(button => {
            button.addEventListener("click", (e) => {
                const index = parseInt(e.currentTarget.dataset.index);

                // Eliminar archivo
                this.uploadedFiles.splice(index, 1);

                // Reconstruir input
                this._refreshFileInput(input);

                // Re-renderizar
                this._renderFileList(container, input);
            });
        });
    },
});
