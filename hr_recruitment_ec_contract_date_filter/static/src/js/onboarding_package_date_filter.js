// /** @odoo-module **/

// import { Component, useState } from "@odoo/owl";
// import { ControlPanel } from "@web/search/control_panel/control_panel";
// import { patch } from "@web/core/utils/patch";

// export class EcOnboardingDateFilter extends Component {
//     static template = "hr_recruitment_ec_contract_date_filter.DateFilter";

//     setup() {
//         this.state = useState({
//             open: false,
//             date: "",
//         });

//         this.searchModel = this.env.searchModel;
//     }

//     toggle() {
//         this.state.open = !this.state.open;
//     }

//     onDateChange(ev) {
//         this.state.date = ev.target.value;
//     }

//     apply() {
//         const value = this.state.date;

//         if (!value) {
//             return;
//         }

//         // Eliminar filtros anteriores creados por este componente
//         this.clearSearchFilter();

//         // Crear filtro directamente sobre el campo Date
//         this.searchModel.createNewFilters([
//             {
//                 description: `Generado el: ${value}`,
//                 domain: [
//                     ["generated_date", "=", value],
//                 ],
//             },
//         ]);

//         this.state.open = false;
//     }

//     clearSearchFilter() {
//         // Elimina los filtros dinámicos anteriores de este componente.
//         // Si necesitas distinguir únicamente este filtro de otros
//         // filtros dinámicos, podemos guardar el ID retornado por
//         // createNewFilters().
//     }

//     clear() {
//         this.state.date = "";
//         this.state.open = false;

//         this.clearSearchFilter();
//     }
// }

// patch(ControlPanel.prototype, {
//     setup() {
//         super.setup(...arguments);
//     },
// });

// patch(ControlPanel, {
//     components: {
//         ...ControlPanel.components,
//         EcOnboardingDateFilter,
//     },
// });


/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { ControlPanel } from "@web/search/control_panel/control_panel";
import { patch } from "@web/core/utils/patch";


export class EcOnboardingDateFilter extends Component {

    static template =
        "hr_recruitment_ec_contract_date_filter.DateFilter";


    setup() {

        this.state = useState({
            open: false,
            date: "",
        });

        this.searchModel = this.env.searchModel;

        /*
         * Aquí guardamos el filtro creado por este componente.
         *
         * Mientras el componente exista:
         *
         * null       -> no existe filtro
         * objeto/ID  -> existe filtro
         */
        this.dateFilter = null;
    }


    // ========================================================
    // ABRIR / CERRAR POPUP
    // ========================================================

    toggle() {
        this.state.open = !this.state.open;
    }


    // ========================================================
    // CAMBIO DE FECHA
    // ========================================================

    onDateChange(ev) {
        this.state.date = ev.target.value;
    }


    // ========================================================
    // APLICAR FILTRO
    // ========================================================

    apply() {

        const value = this.state.date;

        if (!value) {
            return;
        }

        console.log(
            "[EC DATE FILTER] Aplicando fecha:",
            value
        );


        // ====================================================
        // SI YA EXISTE UN FILTRO, ELIMINARLO
        // ====================================================

        if (this.dateFilter) {

            console.log(
                "[EC DATE FILTER] Reemplazando filtro anterior:",
                this.dateFilter
            );

            this.removeDateFilter();
        }


        // ====================================================
        // CREAR EL NUEVO FILTRO
        // ====================================================

        const filters = this.searchModel.createNewFilters([
            {
                description: `Generado el: ${value}`,

                domain: [
                    ["generated_date", "=", value],
                ],
            },
        ]);


        // ====================================================
        // GUARDAR REFERENCIA DEL FILTRO
        // ====================================================

        if (filters && filters.length) {

            this.dateFilter = filters[0];

            console.log(
                "[EC DATE FILTER] Nuevo filtro guardado:",
                this.dateFilter
            );

        } else {

            console.warn(
                "[EC DATE FILTER] createNewFilters() no devolvió filtros"
            );

            this.dateFilter = null;
        }


        this.state.open = false;
    }


    // ========================================================
    // ELIMINAR FILTRO DE FECHA
    // ========================================================

    removeDateFilter() {

        if (!this.dateFilter) {

            console.log(
                "[EC DATE FILTER] No hay filtro para eliminar"
            );

            return;
        }


        try {

            console.log(
                "[EC DATE FILTER] Eliminando:",
                this.dateFilter
            );


            this.searchModel.deleteNewFilter(
                this.dateFilter
            );


            console.log(
                "[EC DATE FILTER] Filtro eliminado correctamente"
            );


        } catch (error) {

            console.error(
                "[EC DATE FILTER] Error eliminando filtro:",
                error
            );

        }


        /*
         * IMPORTANTE:
         *
         * Después de eliminarlo debemos ponerlo en null.
         *
         * De esta manera el siguiente apply()
         * creará un filtro nuevo.
         */
        this.dateFilter = null;
    }


    // ========================================================
    // LIMPIAR
    // ========================================================

    clear() {

        console.log(
            "[EC DATE FILTER] Limpiando filtro"
        );


        // Eliminar filtro existente
        this.removeDateFilter();


        // Limpiar fecha seleccionada
        this.state.date = "";


        // Cerrar popup
        this.state.open = false;
    }
}


// ============================================================
// CONTROL PANEL
// ============================================================

patch(ControlPanel, {

    components: {
        ...ControlPanel.components,
        EcOnboardingDateFilter,
    },

});


