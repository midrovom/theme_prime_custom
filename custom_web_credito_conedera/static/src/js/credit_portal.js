/** Progressive enhancements for the CONEDERA credit portal. */
(function () {
    'use strict';

    function initCreditPortal() {
        // The checkbox is supplied by custom_web_hr_datos_candidatos.
        // The credit controller validates it server-side as well.
        var termsCheckbox = document.querySelector('form.oe_signup_form input#accept_terms[name="accept_terms"]');
        if (termsCheckbox) {
            termsCheckbox.required = true;
        }

        // Keep the native signup page behind the OTP modal while it is rendered.
        var signupOtpModal = document.getElementById('creditSignupOtpModal');
        if (signupOtpModal) {
            document.body.classList.add('modal-open');
            var otpInput = document.getElementById('verify_code');
            if (otpInput) {
                window.setTimeout(function () { otpInput.focus(); }, 50);
            }
        }

        // Recalculate from the server expiration timestamp on every tick. This avoids
        // a frozen or drifting countdown if the page loads late or an interval is delayed.
        var countdown = document.getElementById('credit-otp-countdown');
        if (countdown) {
            var expiresAtSeconds = Number(countdown.getAttribute('data-expires-at') || 0);
            var fallbackSeconds = Number(countdown.getAttribute('data-remaining-seconds') || 0);
            var expiresAtMs = expiresAtSeconds > 0
                ? expiresAtSeconds * 1000
                : Date.now() + Math.max(0, fallbackSeconds) * 1000;
            var timeLabel = document.getElementById('credit-otp-time');
            var waiting = document.getElementById('credit-otp-waiting');
            var expired = document.getElementById('credit-otp-expired');
            var resendForm = document.getElementById('credit-otp-resend-form');
            var timer = null;

            function paintCountdown() {
                var remaining = Math.max(0, Math.ceil((expiresAtMs - Date.now()) / 1000));
                if (remaining <= 0) {
                    if (timeLabel) { timeLabel.textContent = '00:00'; }
                    if (waiting) { waiting.classList.add('d-none'); }
                    if (expired) { expired.classList.remove('d-none'); }
                    if (resendForm) { resendForm.classList.remove('d-none'); }
                    if (timer !== null) {
                        window.clearInterval(timer);
                        timer = null;
                    }
                    return false;
                }

                var minutes = Math.floor(remaining / 60);
                var seconds = remaining % 60;
                if (timeLabel) {
                    timeLabel.textContent = String(minutes).padStart(2, '0') + ':' + String(seconds).padStart(2, '0');
                }
                if (waiting) { waiting.classList.remove('d-none'); }
                if (expired) { expired.classList.add('d-none'); }
                if (resendForm) { resendForm.classList.add('d-none'); }
                return true;
            }

            // Paint immediately, then re-check often against the absolute deadline.
            // The visible label changes once a second, and expiration is not delayed.
            if (paintCountdown()) {
                timer = window.setInterval(paintCountdown, 250);
            }
        }

        // Validar también el dígito verificador de las cédulas (sin llamadas de red).
        function validCedula(value) {
            if (!/^[0-9]{10}$/.test(value)) { return false; }
            var province = Number(value.slice(0, 2));
            if (!((province >= 1 && province <= 24) || province === 30) || Number(value[2]) > 5) {
                return false;
            }
            var weights = [2, 1, 2, 1, 2, 1, 2, 1, 2];
            var total = 0;
            for (var j = 0; j < 9; j++) {
                var product = Number(value[j]) * weights[j];
                total += product > 9 ? product - 9 : product;
            }
            return (10 - total % 10) % 10 === Number(value[9]);
        }

        function validCedulaOrRuc(value) {
            if (value.length === 10) { return validCedula(value); }
            if (!/^[0-9]{13}$/.test(value)) { return false; }
            var province = Number(value.slice(0, 2));
            if (!((province >= 1 && province <= 24) || province === 30)) { return false; }
            var kind = Number(value[2]);
            if (kind <= 5) { return validCedula(value.slice(0, 10)) && Number(value.slice(10)) > 0; }
            if (kind === 6) { return Number(value.slice(9)) > 0; }
            if (kind === 9) { return Number(value.slice(10)) > 0; }
            return false;
        }

        var identityType = document.getElementById('credit-identification-type');
        var applicantType = document.getElementById('credit-applicant-type');
        var lockedIdentityType = document.getElementById('credit-identification-type-locked');
        var creditForm = document.querySelector('form.credit-form[data-credit-wizard="1"]');
        // Conservar las opciones originales para recuperarlas cuando se seleccione
        // Persona natural. Una persona jurídica solo debe VER RUC, no opciones
        // de cédula deshabilitadas dentro de la lista desplegable.
        var documentTypeOptions = identityType
            ? Array.from(identityType.options).map(function (option) { return option.cloneNode(true); })
            : [];
        function updateApplicantDocumentType() {
            if (!identityType || !applicantType || !creditForm) { return; }
            var chosen = applicantType.options[applicantType.selectedIndex];
            var juridical = Boolean(chosen && chosen.dataset.typeCode === 'juridical');
            var selectedBefore = identityType.value;
            if (juridical) {
                // Eliminar físicamente las demás opciones del select, no solo
                // deshabilitarlas. Bloquear también el campo completo.
                var rucOption = documentTypeOptions.find(function (option) { return option.value === 'ruc'; });
                if (rucOption) {
                    identityType.replaceChildren(rucOption.cloneNode(true));
                }
                identityType.value = 'ruc';
                identityType.disabled = true;
                // Un SELECT deshabilitado no se envía con FormData ni con POST;
                // enviar RUC mediante un campo oculto mientras está bloqueado.
                if (lockedIdentityType) {
                    lockedIdentityType.name = 'identification_type';
                    lockedIdentityType.value = 'ruc';
                }
            } else {
                // Persona natural: cédula ecuatoriana, cédula extranjera y RUC.
                // Quitar primero el nombre del oculto para que FormData y los
                // borradores offline encuentren un único campo por nombre.
                if (lockedIdentityType) { lockedIdentityType.removeAttribute('name'); }
                identityType.replaceChildren.apply(identityType, documentTypeOptions.map(function (option) {
                    return option.cloneNode(true);
                }));
                identityType.disabled = false;
                identityType.value = documentTypeOptions.some(function (option) {
                    return option.value === selectedBefore;
                }) ? selectedBefore : 'cedula';
            }
            identityType.classList.toggle('credit-document-locked', juridical);
            identityType.setAttribute('aria-readonly', juridical ? 'true' : 'false');
            identityType.setAttribute('aria-disabled', juridical ? 'true' : 'false');
            // Sincronizar validaciones del documento y campos condicionales.
            identityType.dispatchEvent(new Event('change', {bubbles: true}));
        }
        function identityValidation(input) {
            var value = input.value.trim();
            var kind = input.dataset.creditId;
            var type = identityType ? identityType.value : 'cedula';
            var valid = !value;
            var message = '';
            if (kind === 'applicant') {
                valid = valid || (type === 'cedula' ? validCedula(value) :
                    type === 'ruc' ? /^[0-9]{13}$/.test(value) :
                    type === 'foreign' ? /^[0-9]{10}$/.test(value) : false);
                message = 'Documento inválido. Cédula ecuatoriana: 10 dígitos y verificador; RUC: 13 dígitos; extranjera: 10 dígitos numéricos.';
                input.maxLength = type === 'ruc' ? 13 : 10;
                input.pattern = type === 'ruc' ? '[0-9]{13}' : '[0-9]{10}';
            } else if (kind === 'spouse' || kind === 'authorized_buyer' || kind === 'authorized_pickup') {
                // La cédula ecuatoriana se comprueba primero y, si no es válida,
                // se acepta un documento extranjero de 10 dígitos numéricos.
                valid = valid || validCedula(value) || /^[0-9]{10}$/.test(value);
                message = kind === 'spouse'
                    ? 'El documento del cónyuge debe tener 10 dígitos numéricos.'
                    : 'El documento de la persona autorizada debe tener exactamente 10 dígitos numéricos (cédula ecuatoriana o documento extranjero).';
            } else if (kind === 'business_ruc') {
                valid = valid || /^[0-9]{13}$/.test(value);
                message = 'El RUC del negocio debe contener exactamente 13 dígitos.';
            } else if (kind === 'mobile') {
                valid = valid || /^[0-9]{10}$/.test(value);
                message = 'El celular debe tener exactamente 10 dígitos numéricos.';
            }
            input.setCustomValidity(valid ? '' : message);
        }
        document.querySelectorAll('form.credit-form [data-credit-id]').forEach(function (input) {
            var validate = function () { identityValidation(input); };
            input.addEventListener('input', validate);
            input.addEventListener('change', validate);
            validate();
        });
        if (identityType && creditForm) {
            identityType.addEventListener('change', function () {
                var chosen = applicantType && applicantType.options[applicantType.selectedIndex];
                if (chosen && chosen.dataset.typeCode === 'juridical') { identityType.value = 'ruc'; }
                var input = creditForm.querySelector('[data-credit-id="applicant"]');
                if (input) { identityValidation(input); }
            });
        }
        if (applicantType && creditForm) {
            applicantType.addEventListener('change', updateApplicantDocumentType);
            updateApplicantDocumentType();
        }

        // Los teléfonos siempre son dígitos ASCII. Delegado para referencias
        // añadidas dinámicamente (incluye pegar, arrastrar texto y móviles).
        function enforcePhoneDigits(input) {
            var previous = input.value;
            var max = input.name === 'mobile' ? 10 : Infinity;
            var cleaned = previous.replace(/[^0-9]/g, '').slice(0, max);
            if (previous !== cleaned) {
                input.value = cleaned;
            }
        }
        document.addEventListener('input', function (ev) {
            if (ev.target && ev.target.matches('[data-credit-phone="1"]')) {
                enforcePhoneDigits(ev.target);
            }
        }, true);
        document.querySelectorAll('[data-credit-phone="1"]').forEach(enforcePhoneDigits);

        // Estado civil configurable: decidir por código estable, nunca por el texto.
        var maritalSelect = creditForm && creditForm.querySelector('[name="marital_status_id"]');
        if (maritalSelect) {
            function adjustSpouse() {
                var option = maritalSelect.options[maritalSelect.selectedIndex];
                var needsSpouse = Boolean(option && option.dataset.requiresSpouse === '1');
                creditForm.querySelectorAll('.credit-spouse-field').forEach(function (wrap) {
                    wrap.hidden = !needsSpouse;
                    wrap.querySelectorAll('input').forEach(function (input) {
                        input.disabled = !needsSpouse;
                        input.required = needsSpouse;
                        if (!needsSpouse) { input.value = ''; input.setCustomValidity(''); }
                    });
                });
            }
            maritalSelect.addEventListener('change', adjustSpouse);
            adjustSpouse();
        }

        // La visa permanece visible. El tiempo de residencia solo aparece si
        // se contesta Sí a la visa de trabajo.
        if (creditForm) {
            var visa = creditForm.querySelector('[name="foreign_work_visa"]');
            var residence = creditForm.querySelector('[name="foreign_residence_time"]');
            var residenceWrap = creditForm.querySelector('.credit-foreign-residence');
            function adjustForeignFields() {
                var visaYes = visa && visa.value === 'yes';
                if (residenceWrap) { residenceWrap.hidden = !visaYes; }
                if (residence) {
                    residence.required = visaYes;
                    residence.disabled = !visaYes;
                }
                if (visa) { visa.required = Boolean(identityType && identityType.value === 'foreign'); }
            }
            if (visa) { visa.addEventListener('change', adjustForeignFields); }
            if (identityType) { identityType.addEventListener('change', adjustForeignFields); }
            adjustForeignFields();
        }

        // Mínimo definido por empresa en Configuración > Mínimos de referencias.
        function refreshReferenceRequirements(body) {
            var min = Number(body.dataset.minReferences || 1);
            body.querySelectorAll('.credit-reference-row').forEach(function (row, index) {
                var fields = Array.from(row.querySelectorAll('input, select'));
                var started = fields.some(function (field) { return field.value.trim() !== ''; });
                var requireRow = index < min || started;
                fields.forEach(function (field) { field.required = requireRow; });
            });
        }
        if (creditForm) {
            creditForm.querySelectorAll('[data-credit-reference-body]').forEach(function (body) {
                ['input', 'change'].forEach(function (eventName) {
                    body.addEventListener(eventName, function () { refreshReferenceRequirements(body); });
                });
                refreshReferenceRequirements(body);
            });
        }

        // Añadir referencias sin un límite fijo de tres (límite técnico 30 por sección).
        document.querySelectorAll('[data-credit-reference-body]').forEach(function (body) {
            var typ = body.dataset.creditReferenceBody;
            var add = document.querySelector('[data-credit-add-reference="' + typ + '"]');
            var countInput = creditForm && creditForm.querySelector('[name="' + typ + '_count"]');
            var maxRows = Number(body.dataset.maxReferences || 30);
            if (!add || !countInput) { return; }
            function renumber() {
                var rows = body.querySelectorAll('.credit-reference-row');
                rows.forEach(function (row, index) {
                    var n = index + 1;
                    row.querySelectorAll('[name]').forEach(function (field) {
                        field.name = field.name.replace(/_[0-9]+$/, '_' + n);
                    });
                });
                countInput.value = String(rows.length);
                add.disabled = rows.length >= maxRows;
                refreshReferenceRequirements(body);
            }
            add.addEventListener('click', function () {
                var rows = body.querySelectorAll('.credit-reference-row');
                if (!rows.length || rows.length >= maxRows) { return; }
                var clone = rows[0].cloneNode(true);
                clone.querySelectorAll('input').forEach(function (field) { field.value = ''; });
                clone.querySelectorAll('select').forEach(function (field) { field.selectedIndex = 0; });
                var actionCell = clone.querySelector('td:last-child');
                if (actionCell) {
                    actionCell.innerHTML = '';
                    var remove = document.createElement('button');
                    remove.type = 'button';
                    remove.className = 'btn btn-outline-danger btn-sm';
                    remove.dataset.creditRemoveReference = '1';
                    remove.textContent = 'Quitar';
                    actionCell.appendChild(remove);
                }
                body.appendChild(clone);
                renumber();
                var first = clone.querySelector('input');
                if (first) { first.focus(); }
            });
            body.addEventListener('click', function (event) {
                var remove = event.target.closest('[data-credit-remove-reference]');
                if (remove && body.querySelectorAll('.credit-reference-row').length > Number(body.dataset.minReferences || 1)) {
                    remove.closest('.credit-reference-row').remove();
                    renumber();
                }
            });
            renumber();
        });

        // Columnas legibles en celular: cada referencia se convierte en tarjeta
        // con la etiqueta de su cabecera, incluidas las filas añadidas con Agregar.
        if (creditForm) {
            creditForm.querySelectorAll('.credit-reference-table').forEach(function (table) {
                var labels = Array.from(table.querySelectorAll('thead th')).map(function (th) {
                    return th.textContent.trim();
                });
                var body = table.querySelector('tbody[data-credit-reference-body]');
                if (!body) { return; }
                function assignReferenceLabels() {
                    body.querySelectorAll('tr.credit-reference-row').forEach(function (row) {
                        row.querySelectorAll('td').forEach(function (cell, index) {
                            cell.setAttribute('data-label', labels[index] || 'Dato');
                        });
                    });
                }
                assignReferenceLabels();
                // MutationObserver solo actualiza etiquetas; no modifica el formulario.
                var observer = new MutationObserver(assignReferenceLabels);
                observer.observe(body, { childList: true });
            });
        }

        // Vista previa inmediata del croquis en el paso 3 del formulario.
        // El archivo se muestra localmente; solo se guarda cuando se envía la solicitud.
        var historySketchFile = document.getElementById('credit-review-sketch-file');
        var historySketchPreview = document.getElementById('credit-review-sketch-preview');
        if (historySketchFile && historySketchPreview) {
            var activeObjectUrl = null;
            var maxSize = 12 * 1024 * 1024;
            var dropzone = document.getElementById('credit-sketch-dropzone');
            var dropPrompt = dropzone && dropzone.querySelector('.credit-sketch-drop-prompt');
            var showWarning = document.getElementById('credit-review-sketch-warning');
            var setWarning = function (message) {
                if (showWarning) {
                    showWarning.textContent = message || '';
                    showWarning.hidden = !message;
                }
            };
            var validateSketchFile = function (file) {
                if (!file) { return false; }
                var ext = file.name.split('.').pop().toLowerCase();
                var image = ['png', 'jpg', 'jpeg', 'webp'].includes(ext) && (!file.type || file.type.startsWith('image/'));
                if (!image || !file.size || file.size > maxSize) {
                    setWarning('Adjunte una imagen PNG, JPG o WEBP de hasta 12 MB.');
                    return false;
                }
                setWarning('');
                return true;
            };
            var renderSketchPreview = function (file) {
                if (!validateSketchFile(file)) { return false; }
                if (activeObjectUrl) { URL.revokeObjectURL(activeObjectUrl); }
                activeObjectUrl = URL.createObjectURL(file);
                historySketchPreview.replaceChildren();
                var isPdf = file.name.toLowerCase().endsWith('.pdf');
                var preview = document.createElement(isPdf ? 'iframe' : 'img');
                preview.className = isPdf ? 'credit-sketch-review-pdf' : 'credit-sketch-review-image';
                preview.title = 'Vista previa del croquis seleccionado';
                if (!isPdf) { preview.alt = 'Croquis seleccionado para adjuntar'; }
                preview.src = activeObjectUrl;
                historySketchPreview.appendChild(preview);
                var description = document.createElement('small');
                description.className = 'd-block text-muted mt-2';
                description.textContent = file.name + ' · ' + (file.size / 1024 / 1024).toFixed(2) + ' MB';
                historySketchPreview.appendChild(description);
                return true;
            };
            historySketchFile.addEventListener('change', function () {
                var file = historySketchFile.files && historySketchFile.files[0];
                if (file && !renderSketchPreview(file)) { historySketchFile.value = ''; }
            });
            // Permite arrastrar el archivo al recuadro, además de seleccionarlo.
            if (dropzone) {
                var dragDepth = 0;
                ['dragenter', 'dragover'].forEach(function (eventName) {
                    dropzone.addEventListener(eventName, function (event) {
                        if (!event.dataTransfer || !Array.from(event.dataTransfer.types || []).includes('Files')) { return; }
                        event.preventDefault();
                        if (eventName === 'dragenter') { dragDepth += 1; }
                        if (event.dataTransfer) { event.dataTransfer.dropEffect = 'copy'; }
                        dropzone.classList.add('is-dragover');
                    });
                });
                dropzone.addEventListener('dragleave', function (event) {
                    event.preventDefault();
                    dragDepth = Math.max(0, dragDepth - 1);
                    if (!dragDepth) { dropzone.classList.remove('is-dragover'); }
                });
                dropzone.addEventListener('drop', function (event) {
                    event.preventDefault();
                    dragDepth = 0;
                    dropzone.classList.remove('is-dragover');
                    var dropped = event.dataTransfer && event.dataTransfer.files;
                    if (!dropped || !dropped.length) { return; }
                    if (dropped.length !== 1) {
                        setWarning('Seleccione un solo archivo para el croquis.');
                        return;
                    }
                    var file = dropped[0];
                    if (!validateSketchFile(file)) { return; }
                    try {
                        var transfer = new DataTransfer();
                        transfer.items.add(file);
                        historySketchFile.files = transfer.files;
                        historySketchFile.dispatchEvent(new Event('change', { bubbles: true }));
                    } catch (error) {
                        setWarning('No se pudo adjuntar el archivo arrastrado. Haga clic en el recuadro para seleccionarlo.');
                    }
                });
            }
            if (dropPrompt) {
                dropPrompt.addEventListener('click', function () { historySketchFile.click(); });
                dropPrompt.addEventListener('keydown', function (event) {
                    if (event.key === 'Enter' || event.key === ' ') {
                        event.preventDefault();
                        historySketchFile.click();
                    }
                });
            }
            window.addEventListener('pagehide', function () {
                if (activeObjectUrl) { URL.revokeObjectURL(activeObjectUrl); }
            }, { once: true });
        }

        // Dos formas de declarar la ubicación: capturar coordenadas del navegador
        // o introducirlas manualmente. Ambas se almacenan en latitud/longitud.
        var locateButton = document.getElementById('credit-get-location');
        var manualButton = document.getElementById('credit-enter-location-manually');
        var latitudeInput = document.getElementById('credit-business-latitude');
        var longitudeInput = document.getElementById('credit-business-longitude');
        var capturedInput = document.getElementById('credit-location-captured');
        var locationMethod = document.getElementById('credit-location-method');
        var locationStatus = document.getElementById('credit-location-status');
        var manualContainers = document.querySelectorAll('.credit-manual-coordinates');
        var automaticContainers = document.querySelectorAll('.credit-automatic-coordinates');
        if (latitudeInput && longitudeInput && locationMethod && capturedInput) {
            function showManualCoordinates(clearAutomatic) {
                manualContainers.forEach(function (el) { el.hidden = false; });
                automaticContainers.forEach(function (el) { el.hidden = true; });
                if (clearAutomatic) {
                    locationMethod.value = 'manual';
                    capturedInput.value = '';
                }
                latitudeInput.required = true;
                longitudeInput.required = true;
            }
            function showAutomaticallyCaptured(latitude, longitude) {
                latitudeInput.value = latitude.toFixed(7);
                longitudeInput.value = longitude.toFixed(7);
                locationMethod.value = 'automatic';
                capturedInput.value = latitudeInput.value + ', ' + longitudeInput.value;
                manualContainers.forEach(function (el) { el.hidden = true; });
                automaticContainers.forEach(function (el) { el.hidden = false; });
                latitudeInput.required = true;
                longitudeInput.required = true;
                latitudeInput.dispatchEvent(new Event('input', { bubbles: true }));
                longitudeInput.dispatchEvent(new Event('input', { bubbles: true }));
                if (locationStatus) { locationStatus.textContent = 'Ubicación capturada; las coordenadas se guardarán con la solicitud.'; }
            }
            // Mantener la modalidad con que se guardó una solicitud al volver a editarla.
            if (locationMethod.value === 'automatic' && capturedInput.value && latitudeInput.value && longitudeInput.value) {
                manualContainers.forEach(function (el) { el.hidden = true; });
                automaticContainers.forEach(function (el) { el.hidden = false; });
            } else {
                // En el primer ingreso se ofrecen ambos botones; los campos solo
                // aparecen cuando el usuario escoge el modo manual.
                manualContainers.forEach(function (el) { el.hidden = true; });
                if (latitudeInput.value && longitudeInput.value) { showManualCoordinates(false); }
            }
            if (manualButton) {
                manualButton.addEventListener('click', function () {
                    showManualCoordinates(true);
                    if (locationStatus) { locationStatus.textContent = 'Escriba las dos coordenadas del negocio para continuar.'; }
                    latitudeInput.focus();
                });
            }
            if (locateButton) {
                locateButton.addEventListener('click', function () {
                    // Mientras se solicita la geolocalización, mostrar solo el bloque automático.
                    manualContainers.forEach(function (el) { el.hidden = true; });
                    automaticContainers.forEach(function (el) { el.hidden = false; });
                    if (locationStatus) { locationStatus.textContent = 'Buscando la ubicación actual...'; }
                    function fallback(message) {
                        showManualCoordinates(true);
                        if (locationStatus) { locationStatus.textContent = message; }
                        window.alert(message);
                    }
                    if (!window.isSecureContext) {
                        fallback('La captura de ubicación requiere HTTPS. Puede escribir latitud y longitud manualmente.');
                        return;
                    }
                    if (!navigator.geolocation) {
                        fallback('Su navegador no permite obtener la ubicación. Ingrese latitud y longitud manualmente.');
                        return;
                    }
                    locateButton.disabled = true;
                    var originalText = locateButton.textContent;
                    locateButton.textContent = 'Obteniendo ubicación...';
                    function finish() { locateButton.disabled = false; locateButton.textContent = originalText; }
                    navigator.geolocation.getCurrentPosition(function (position) {
                        finish();
                        showAutomaticallyCaptured(position.coords.latitude, position.coords.longitude);
                    }, function (error) {
                        finish();
                        var msg = error.code === 1 ? 'El navegador denegó el permiso de ubicación.' :
                            (error.code === 2 ? 'No se pudo determinar la ubicación del dispositivo.' :
                            (error.code === 3 ? 'Se agotó el tiempo de espera para obtener la ubicación.' : 'No se pudo detectar la ubicación.'));
                        fallback(msg + ' Ingrese latitud y longitud manualmente o reintente con HTTPS y el permiso habilitado.');
                    }, { enableHighAccuracy: true, timeout: 20000, maximumAge: 30000 });
                });
            }
            function validateCoordinates() {
                var missingPair = Boolean(latitudeInput.value.trim()) !== Boolean(longitudeInput.value.trim());
                latitudeInput.setCustomValidity(missingPair ? 'Debe ingresar latitud y longitud juntas.' : '');
                longitudeInput.setCustomValidity(missingPair ? 'Debe ingresar latitud y longitud juntas.' : '');
                if (locationMethod.value === 'manual' && capturedInput.value) {
                    capturedInput.value = '';
                }
            }
            latitudeInput.addEventListener('input', function () {
                if (locationMethod.value === 'automatic' && capturedInput.value &&
                    capturedInput.value !== (latitudeInput.value + ', ' + longitudeInput.value)) {
                    showManualCoordinates(true);
                }
                validateCoordinates();
            });
            longitudeInput.addEventListener('input', validateCoordinates);
            validateCoordinates();
        }

        // Se muestra un solo vehículo por defecto. Cada clic agrega otro
        // vehículo opcional y se manda al servidor en vehicle_ids (One2many).
        var vehiclesContainer = document.getElementById('credit-vehicles');
        var addVehicleButton = document.getElementById('credit-add-vehicle');
        var vehicleCountInput = document.getElementById('credit-vehicle-count');
        if (vehiclesContainer && addVehicleButton && vehicleCountInput) {
            var maxVehicles = Number(vehiclesContainer.dataset.maxVehicles || 30);
            function renumberVehicles() {
                var rows = vehiclesContainer.querySelectorAll('.credit-vehicle-row');
                rows.forEach(function (row, index) {
                    var n = index + 1;
                    row.dataset.vehicleIndex = String(n);
                    var heading = row.querySelector('h3');
                    if (heading) { heading.textContent = 'Vehículo ' + n; }
                    row.querySelectorAll('[name]').forEach(function (input) {
                        input.name = input.name.replace(/^vehicle[0-9]+_/, 'vehicle' + n + '_');
                    });
                });
                vehicleCountInput.value = String(rows.length);
                addVehicleButton.disabled = rows.length >= maxVehicles;
            }
            addVehicleButton.addEventListener('click', function () {
                var rows = vehiclesContainer.querySelectorAll('.credit-vehicle-row');
                if (rows.length >= maxVehicles) { return; }
                var clone = rows[0].cloneNode(true);
                clone.querySelectorAll('input').forEach(function (input) { input.value = ''; });
                var headingWrap = clone.querySelector('.d-flex');
                if (headingWrap && !clone.querySelector('[data-credit-remove-vehicle]')) {
                    var remove = document.createElement('button');
                    remove.type = 'button';
                    remove.className = 'btn btn-outline-danger btn-sm';
                    remove.dataset.creditRemoveVehicle = '1';
                    remove.textContent = 'Quitar';
                    headingWrap.appendChild(remove);
                }
                vehiclesContainer.appendChild(clone);
                renumberVehicles();
                var firstField = clone.querySelector('input');
                if (firstField) { firstField.focus(); }
            });
            vehiclesContainer.addEventListener('click', function (event) {
                var remove = event.target.closest('[data-credit-remove-vehicle]');
                if (!remove) { return; }
                var row = remove.closest('.credit-vehicle-row');
                if (row && Number(row.dataset.vehicleIndex) > 1) {
                    row.remove();
                    renumberVehicles();
                }
            });
            renumberVehicles();
        }

        // Si se informa cualquier dato de un vehículo, completar el resto.
        function refreshVehicleRequirements() {
            if (!vehiclesContainer) { return; }
            vehiclesContainer.querySelectorAll('.credit-vehicle-row').forEach(function (row) {
                var fields = Array.from(row.querySelectorAll('input'));
                var started = fields.some(function (field) { return field.value.trim() !== ''; });
                fields.forEach(function (field) { field.required = started; });
            });
        }
        if (vehiclesContainer) {
            ['input', 'change'].forEach(function (ev) {
                vehiclesContainer.addEventListener(ev, refreshVehicleRequirements);
            });
            refreshVehicleRequirements();
            if (addVehicleButton) {
                addVehicleButton.addEventListener('click', refreshVehicleRequirements);
            }
        }

        // Actividad laboral: primero Sí/No, luego Privado/Público y campos.
        if (creditForm) {
            var employmentSelect = creditForm.querySelector('[name="employment_relationship"]');
            var employerSelect = creditForm.querySelector('[name="employment_employer_type_id"]');
            var employerChoice = creditForm.querySelector('.credit-employer-choice');
            var employmentWrap = creditForm.querySelector('.credit-employment-fields');
            var employmentFields = Array.from(creditForm.querySelectorAll(
                '[name="employment_company"], [name="employment_activity"], [name="employment_address"], '
                + '[name="employment_phone"], [name="employment_start_date"], [name="employment_position"], '
                + '[name="employment_salary"]'));
            function refreshEmploymentRequirements() {
                var working = employmentSelect && employmentSelect.value === 'yes';
                if (employerChoice) { employerChoice.hidden = !working; }
                if (employmentWrap) { employmentWrap.hidden = !working; }
                if (employerSelect) { employerSelect.required = working; employerSelect.disabled = !working; }
                employmentFields.forEach(function (field) {
                    field.required = working;
                    field.disabled = !working;
                });
            }
            if (employmentSelect) { employmentSelect.addEventListener('change', refreshEmploymentRequirements); }
            refreshEmploymentRequirements();
        }

        // Ver más permanece junto al texto inicial; Ver menos se sitúa después
        // de la última frase y devuelve al usuario al punto de expansión.
        var legalMore = document.getElementById('credit-legal-more');
        var legalLess = document.getElementById('credit-legal-less');
        var legalRest = document.getElementById('credit-legal-rest');
        if (legalMore && legalLess && legalRest) {
            legalMore.addEventListener('click', function () {
                legalRest.hidden = false;
                legalMore.hidden = true;
                legalMore.setAttribute('aria-expanded', 'true');
            });
            legalLess.addEventListener('click', function () {
                legalRest.hidden = true;
                legalMore.hidden = false;
                legalMore.setAttribute('aria-expanded', 'false');
                legalMore.focus({ preventScroll: true });
                legalMore.scrollIntoView({ behavior: 'smooth', block: 'center' });
            });
        }

        // Datos identificativos del paso 3: se reutilizan los del paso 1.
        if (creditForm) {
            [['[name="identification"]', 'credit-sketch-identification'],
             ['[name="applicant_name"]', 'credit-sketch-name']].forEach(function (pair) {
                var origin = creditForm.querySelector(pair[0]);
                var target = document.getElementById(pair[1]);
                if (origin && target) {
                    var sync = function () { target.value = origin.value; };
                    origin.addEventListener('input', sync);
                    origin.addEventListener('change', sync);
                    sync();
                }
            });
        }

        // Seis pasos: croquis integrado como paso 3.
        // El permiso exclusivo de croquis muestra ese MISMO paso del formulario,
        // y el servidor no permite editar otros apartados con ese permiso.
        var wizard = document.querySelector('form.credit-form[data-credit-wizard="1"]');
        if (wizard && !wizard.dataset.creditWizardInitialized) {
            wizard.dataset.creditWizardInitialized = '1';
            var sketchOnly = wizard.dataset.creditSketchOnly === '1';
            var panels = Array.from(wizard.querySelectorAll('.credit-step-panel[data-credit-step]'));
            var indicators = Array.from(wizard.querySelectorAll('[data-credit-step-indicator]'));
            if (sketchOnly) {
                panels = panels.filter(function (panel) { return panel.dataset.creditStep === '3'; });
                indicators = indicators.filter(function (indicator) { return indicator.dataset.creditStepIndicator === '3'; });
                wizard.querySelectorAll('[data-credit-step-indicator]').forEach(function (indicator) {
                    if (indicator.dataset.creditStepIndicator !== '3') { indicator.style.display = 'none'; }
                });
                var progressText = wizard.querySelector('.credit-wizard-progress p');
                if (progressText) { progressText.textContent = 'Corrección autorizada: complete únicamente ubicación y croquis.'; }
            }
            var backButton = wizard.querySelector('[data-credit-prev]');
            var nextButton = wizard.querySelector('[data-credit-next]');
            var submitButton = wizard.querySelector('[data-credit-submit]');
            var progress = wizard.querySelector('.credit-wizard-progress');
            var currentStep = sketchOnly ? 1 : Math.min(panels.length, Math.max(1, parseInt(wizard.dataset.startStep || '1', 10) || 1));

            function showStep(step, fromClick) {
                currentStep = Math.min(panels.length, Math.max(1, step));
                panels.forEach(function (panel, index) {
                    var active = (index + 1 === currentStep);
                    panel.classList.toggle('is-active', active);
                    panel.setAttribute('aria-hidden', String(!active));
                });
                indicators.forEach(function (indicator, index) {
                    var active = (index + 1 === currentStep);
                    indicator.classList.toggle('is-active', active);
                    indicator.classList.toggle('is-complete', index + 1 < currentStep);
                    if (active) {
                        indicator.setAttribute('aria-current', 'step');
                    } else {
                        indicator.removeAttribute('aria-current');
                    }
                });
                if (backButton) { backButton.hidden = currentStep === 1; }
                if (nextButton) { nextButton.hidden = currentStep === panels.length; }
                if (submitButton) { submitButton.hidden = currentStep !== panels.length; }
                if (fromClick && progress) {
                    progress.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }
            }

            window.creditWizardGoto = function (step) { showStep(step, false); };

            function validateStep(step) {
                var panel = panels[step - 1];
                if (!panel) { return true; }
                // En Negocio se debe escoger una de las dos opciones de ubicación;
                // los campos manuales no están visibles hasta activar esa opción.
                if (step === 2 && latitudeInput && longitudeInput &&
                        (!latitudeInput.value.trim() || !longitudeInput.value.trim())) {
                    if (locationStatus) {
                        locationStatus.textContent = 'Seleccione Usar mi ubicación actual o Ingresar latitud y longitud manualmente para continuar.';
                    }
                    var locationChoice = document.getElementById('credit-location-choice');
                    if (locationChoice) { locationChoice.scrollIntoView({ behavior: 'smooth', block: 'center' }); }
                    return false;
                }
                var fields = panel.querySelectorAll('input, select, textarea');
                for (var i = 0; i < fields.length; i++) {
                    var field = fields[i];
                    if (!field.disabled && !field.checkValidity()) {
                        showStep(step, true);
                        // El input del croquis no se dibuja: el recuadro es
                        // su control visible de selección y carga.
                        if (field === historySketchFile && dropPrompt) {
                            setWarning('Adjunte el croquis: arrastre una imagen o haga clic en el recuadro para seleccionarla.');
                            dropPrompt.focus();
                            dropPrompt.scrollIntoView({ behavior: 'smooth', block: 'center' });
                        } else {
                            field.reportValidity();
                            field.focus();
                        }
                        return false;
                    }
                }
                return true;
            }

            // Use JS client-side validation because hidden HTML5 controls in other
            // steps cannot be focused by the browser's native submit validator.
            // Hidden steps are validated in validateStep(), so disable native
            // submit validation, which cannot focus fields in hidden panels.
            wizard.noValidate = true;
            wizard.classList.add('credit-wizard-ready');
            showStep(currentStep, false);
            if (backButton) {
                backButton.addEventListener('click', function () {
                    showStep(currentStep - 1, true);
                });
            }
            if (nextButton) {
                nextButton.addEventListener('click', function () {
                    if (validateStep(currentStep)) { showStep(currentStep + 1, true); }
                });
            }
            wizard.addEventListener('submit', function (event) {
                // Check all pages, including the declaration and ALL the
                // additional consent checkboxes on the final page.
                for (var step = 1; step <= panels.length; step++) {
                    if (!validateStep(step)) {
                        event.preventDefault();
                        event.stopPropagation();
                        return;
                    }
                }
                showStep(panels.length, false);
                if (submitButton) {
                    submitButton.disabled = true;
                    submitButton.textContent = creditForm && creditForm.querySelector('[name="credit_edit_mode"]') ? 'Guardando cambios...' : 'Enviando solicitud...';
                }
            });
        }

        // Documentos solicitados: en cada requisito se permite arrastrar y agregar
        // varios lotes de archivos sin reemplazar selecciones previas. El input
        // conserva el FileList acumulado para que Odoo reciba todos con getlist().
        document.querySelectorAll('[data-credit-document-dropzone="1"]').forEach(function (zone) {
            var input = zone.querySelector('input[type="file"]');
            var pendingBox = zone.nextElementSibling;
            var fileList = pendingBox && pendingBox.querySelector('[data-credit-document-list="1"]');
            var countSpan = pendingBox && pendingBox.querySelector('[data-credit-document-count="1"]');
            var errorBox = pendingBox && pendingBox.querySelector('[data-credit-document-error="1"]');
            if (!input || !fileList || !countSpan || !errorBox) { return; }

            var allowMultiple = zone.dataset.allowMultiple === '1';
            var savedCount = Number(zone.dataset.savedCount || 0);
            var minimum = Number(zone.dataset.minimum || 0);
            var required = zone.dataset.required === '1';
            var pending = [];
            var maxFileBytes = 12 * 1024 * 1024;
            var dragDepth = 0;

            function showError(message) {
                errorBox.textContent = message || '';
                errorBox.classList.toggle('d-none', !message);
                zone.classList.toggle('is-invalid', Boolean(message));
            }
            function checkFile(file) {
                if (!file || !file.name || !file.size || file.size > maxFileBytes) {
                    return 'Cada archivo debe tener contenido y un tamaño máximo de 12 MB.';
                }
                var extension = '.' + file.name.split('.').pop().toLowerCase();
                var allowed = input.accept.split(',').map(function (value) { return value.trim().toLowerCase(); });
                var accepted = allowed.some(function (part) {
                    return part === extension || (part.indexOf('/') !== -1 && part === String(file.type || '').toLowerCase());
                });
                if (!accepted) {
                    return 'Formato no permitido para este requisito: ' + file.name;
                }
                return null;
            }
            function syncInput() {
                // Un FileList no permite .push(); DataTransfer crea uno acumulativo.
                // Esto evita el reemplazo cuando el usuario selecciona archivos de nuevo.
                var transfer = new DataTransfer();
                pending.forEach(function (file) { transfer.items.add(file); });
                input.files = transfer.files;
            }
            function renderFiles() {
                fileList.textContent = '';
                pending.forEach(function (file, index) {
                    var item = document.createElement('li');
                    item.className = 'credit-document-pending-item';
                    var fileName = document.createElement('span');
                    fileName.className = 'credit-document-pending-name';
                    fileName.textContent = file.name + ' (' + (file.size / 1024 / 1024).toFixed(2) + ' MB)';
                    var remove = document.createElement('button');
                    remove.type = 'button';
                    remove.className = 'credit-document-remove-file';
                    remove.textContent = 'Quitar';
                    remove.setAttribute('aria-label', 'Quitar ' + file.name);
                    remove.addEventListener('click', function (event) {
                        event.stopPropagation();
                        pending.splice(index, 1);
                        syncInput();
                        renderFiles();
                        showError('');
                    });
                    item.appendChild(fileName);
                    item.appendChild(remove);
                    fileList.appendChild(item);
                });
                countSpan.textContent = String(pending.length);
            }
            function addFiles(files) {
                var incoming = Array.from(files || []);
                if (!incoming.length) { return; }
                var problems = [];
                incoming.forEach(function (file) {
                    var error = checkFile(file);
                    if (error) { problems.push(error); return; }
                    var exists = pending.some(function (existing) {
                        return existing.name === file.name && existing.size === file.size && existing.lastModified === file.lastModified;
                    });
                    if (exists) { return; }
                    if (!allowMultiple) { pending = []; }
                    pending.push(file);
                });
                syncInput();
                renderFiles();
                showError(problems.join(' '));
            }

            input.addEventListener('change', function () {
                // Leer el lote recién elegido antes de reescribir input.files.
                addFiles(input.files);
            });
            zone.addEventListener('click', function (event) {
                if (event.target === input || event.target.closest('button')) { return; }
                input.click();
            });
            zone.addEventListener('keydown', function (event) {
                if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    input.click();
                }
            });
            ['dragenter', 'dragover'].forEach(function (name) {
                zone.addEventListener(name, function (event) {
                    event.preventDefault();
                    event.stopPropagation();
                    if (name === 'dragenter') { dragDepth += 1; }
                    if (event.dataTransfer) { event.dataTransfer.dropEffect = 'copy'; }
                    zone.classList.add('is-dragover');
                });
            });
            zone.addEventListener('dragleave', function (event) {
                event.preventDefault();
                dragDepth = Math.max(0, dragDepth - 1);
                if (!dragDepth) { zone.classList.remove('is-dragover'); }
            });
            zone.addEventListener('drop', function (event) {
                event.preventDefault();
                event.stopPropagation();
                dragDepth = 0;
                zone.classList.remove('is-dragover');
                if (event.dataTransfer) { addFiles(event.dataTransfer.files); }
            });
            // Para los requisitos obligatorios validar el acumulado nuevo + guardado.
            var form = zone.closest('form');
            if (form && !form.dataset.creditDocumentValidationBound) {
                form.dataset.creditDocumentValidationBound = '1';
                form.addEventListener('submit', function (event) {
                    var firstInvalid = null;
                    form.querySelectorAll('[data-credit-document-dropzone="1"]').forEach(function (item) {
                        var itemInput = item.querySelector('input[type="file"]');
                        var itemRequired = item.dataset.required === '1';
                        var itemSaved = Number(item.dataset.savedCount || 0);
                        var itemMinimum = Number(item.dataset.minimum || 0);
                        var itemMultiple = item.dataset.allowMultiple === '1';
                        var itemNew = (itemInput && itemInput.files) ? itemInput.files.length : 0;
                        var total = itemMultiple ? itemSaved + itemNew : (itemNew || itemSaved);
                        var itemError = item.nextElementSibling.querySelector('[data-credit-document-error="1"]');
                        var missing = itemRequired && total < itemMinimum;
                        if (missing) {
                            itemError.textContent = 'Debe adjuntar al menos ' + itemMinimum + ' archivo(s). Disponibles: ' + total + '.';
                            itemError.classList.remove('d-none');
                            item.classList.add('is-invalid');
                            if (!firstInvalid) { firstInvalid = item; }
                        }
                    });
                    if (firstInvalid) {
                        event.preventDefault();
                        firstInvalid.scrollIntoView({ behavior: 'smooth', block: 'center' });
                        firstInvalid.focus();
                    }
                });
            }
            // Evita la validación nativa del input invisible; el backend verifica
            // todos los requisitos otra vez antes de escribir archivos.
            input.required = false;
            renderFiles();
        });

        document.querySelectorAll('.credit-form input[type="file"]').forEach(function (input) {
            input.addEventListener('change', function () {
                if (input.files && input.files.length && input.files[0].size > 12 * 1024 * 1024) {
                    window.alert('El archivo supera el límite de 12 MB. Seleccione un archivo más pequeño.');
                    input.value = '';
                }
            });
        });
    }

    window.creditInitPortal = initCreditPortal;

    // Odoo can load frontend assets after DOMContentLoaded in some navigation flows.
    // Initialize in either case so the countdown never relies on a missed event.
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initCreditPortal, { once: true });
    } else {
        initCreditPortal();
    }
}());
