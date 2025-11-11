/** @odoo-module **/

import dynamicSnippetOptions from "@website/snippets/s_dynamic_snippet/options";

dynamicSnippetOptions.include({

    async _fetchDynamicFilters() {

        console.log("INGRESA A FETCH DYNAMIC FILTERS");

        this._super(...arguments);
    },
    
});

export default dynamicSnippetOptions;
