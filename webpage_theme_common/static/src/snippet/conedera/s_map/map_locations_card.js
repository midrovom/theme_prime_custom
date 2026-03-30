/** @odoo-module **/

import publicWidget from '@web/legacy/js/public/public_widget';
import { generateGMapLink, generateGMapIframe } from '@website/js/utils';

publicWidget.registry.MapLocationsCard = publicWidget.Widget.extend({
    selector: '.s_map',
    start: function () {
        this._loadCities();
    },

    _loadCities: function () {
        fetch('/locations')
            .then(response => response.json())
            .then(data => {
                console.log(">>> Datos recibidos desde /locations:", data);

                const citySelect = document.getElementById("citySelect");
                const localList = document.getElementById("localList");
                const section = document.querySelector(".s_map");

                if (!citySelect || !localList || !section) {
                    console.warn("No se encontraron los elementos del snippet en el DOM");
                    return;
                }

                // Ciudades únicas
                const cities = [...new Set(data.map(loc => loc.city))];

                // Limpiar todas las opciones y volver a la inicial
                citySelect.innerHTML = "";
                const defaultOpt = document.createElement("option");
                defaultOpt.value = "";
                defaultOpt.textContent = "-- Elegir tu ciudad --";
                defaultOpt.selected = true;
                citySelect.appendChild(defaultOpt);

                // Poblar el select con las ciudades
                cities.forEach(city => {
                    const opt = document.createElement("option");
                    opt.value = city;
                    opt.textContent = city;
                    citySelect.appendChild(opt);
                });

                // Evento al cambiar ciudad
                citySelect.addEventListener("change", function () {
                    const selectedCity = this.value;
                    localList.innerHTML = "";

                    const filtered = data.filter(loc => loc.city === selectedCity);

                    if (filtered.length > 0) {
                        const ul = document.createElement("ul");
                        ul.className = "list-group";

                        filtered.forEach(loc => {
                            const li = document.createElement("li");
                            li.className = "list-group-item btn btn-link text-start";
                            li.textContent = loc.name;

                            // Guardar coordenadas en atributos
                            li.dataset.lat = loc.latitude;
                            li.dataset.lng = loc.longitude;

                            // actualizar dataset y regenerar iframe
                            li.addEventListener("click", function () {
                                const lat = this.dataset.lat;
                                const lng = this.dataset.lng;
                                console.log("Moviendo mapa a:", lat, lng);

                                section.dataset.mapAddress = `${lat},${lng}`;
                                const iframeEl = section.querySelector(".s_map_embedded");
                                const url = generateGMapLink(section.dataset);

                                if (iframeEl) {
                                    iframeEl.setAttribute("src", url);
                                } else {
                                    const newIframe = generateGMapIframe();
                                    newIframe.setAttribute("src", url);
                                    section.querySelector(".s_map_color_filter").before(newIframe);
                                }
                            });

                            ul.appendChild(li);
                        });

                        localList.appendChild(ul);
                    }
                });
            })
            .catch(err => {
                console.error("Error al llamar al controlador /locations:", err);
            });
    }
});
