/** @odoo-module **/

document.addEventListener("DOMContentLoaded", function () {
    const fileFields = [
        {
            input: "fotografia",
            message: "file-selected-fotografia",
            multiple: false,
            allowedTypes: ["image/jpeg", "image/png", "image/webp"],
        },
        {
            input: "cedula-votacion",
            message: "file-selected-cedula-votacion",
            multiple: true,
            allowedTypes: [
                "application/pdf",
                "image/jpeg",
                "image/png",
                "image/webp",
            ],
        },
        {
            input: "historia-laboral-iess",
            message: "file-selected-historia-laboral-iess",
            multiple: false,
            allowedTypes: ["application/pdf"],
        },
        {
            input: "acta-matrimonio",
            message: "file-selected-acta-matrimonio",
            multiple: false,
            allowedTypes: [
                "application/pdf",
                "image/jpeg",
                "image/png",
                "image/webp",
            ],
        },
        {
            input: "hijos-menores",
            message: "file-selected-hijos-menores",
            multiple: true,
            allowedTypes: [
                "application/pdf",
                "image/jpeg",
                "image/png",
                "image/webp",
            ],
        },
        {
            input: "estudios-senecyt",
            message: "file-selected-estudios-senecyt",
            multiple: true,
            allowedTypes: [
                "application/pdf",
                "image/jpeg",
                "image/png",
                "image/webp",
            ],
        },
        {
            input: "cursos-realizados",
            message: "file-selected-cursos-realizados",
            multiple: true,
            allowedTypes: [
                "application/pdf",
                "image/jpeg",
                "image/png",
                "image/webp",
            ],
        },
        {
            input: "recomendaciones",
            message: "file-selected-recomendaciones",
            multiple: true,
            allowedTypes: [
                "application/pdf",
                "image/jpeg",
                "image/png",
                "image/webp",
            ],
        },
        {
            input: "certificados-trabajo",
            message: "file-selected-certificados-trabajo",
            multiple: true,
            allowedTypes: [
                "application/pdf",
                "image/jpeg",
                "image/png",
                "image/webp",
            ],
        },
        {
            input: "planilla-servicios",
            message: "file-selected-planilla-servicios",
            multiple: false,
            allowedTypes: [
                "application/pdf",
                "image/jpeg",
                "image/png",
                "image/webp",
            ],
        },
        {
            input: "croquis-domicilio",
            message: "file-selected-croquis-domicilio",
            multiple: false,
            allowedTypes: [
                "application/pdf",
                "image/jpeg",
                "image/png",
                "image/webp",
            ],
        },
        {
            input: "formulario-107",
            message: "file-selected-formulario-107",
            multiple: false,
            allowedTypes: [
                "application/pdf",
                "image/jpeg",
                "image/png",
                "image/webp",
            ],
        },
        {
            input: "cuenta-banco-internacional",
            message: "file-selected-cuenta-banco-internacional",
            multiple: false,
            allowedTypes: [
                "application/pdf",
                "image/jpeg",
                "image/png",
                "image/webp",
            ],
        },
        {
            input: "certificado-salud",
            message: "file-selected-certificado-salud",
            multiple: false,
            allowedTypes: [
                "application/pdf",
                "image/jpeg",
                "image/png",
                "image/webp",
            ],
        },
    ];

    fileFields.forEach(function (field) {
        const input = document.getElementById(field.input);
        const message = document.getElementById(field.message);

        if (!input || !message) {
            return;
        }

        input.addEventListener("change", function () {
            message.innerHTML = "";

            if (!input.files || input.files.length === 0) {
                return;
            }

            const files = Array.from(input.files);

            // Validar archivos
            const invalidFiles = files.filter(function (file) {
                return !field.allowedTypes.includes(file.type);
            });

            if (invalidFiles.length > 0) {
                message.innerHTML =
                    '<span class="text-danger">' +
                    "Archivo(s) no permitido(s): " +
                    invalidFiles
                        .map(function (file) {
                            return file.name;
                        })
                        .join(", ") +
                    "</span>";

                // Limpiar selección
                input.value = "";
                return;
            }

            // Mostrar archivos seleccionados
            if (files.length === 1) {
                message.innerHTML =
                    '<span class="text-success">' +
                    "Archivo seleccionado: " +
                    files[0].name +
                    "</span>";
            } else {
                let html =
                    '<span class="text-success">Archivos seleccionados:</span>';

                html += '<ul class="mb-0">';

                files.forEach(function (file) {
                    html += "<li>" + file.name + "</li>";
                });

                html += "</ul>";

                message.innerHTML = html;
            }
        });
    });
});