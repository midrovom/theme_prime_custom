/** @odoo-module **/

import dynamicSnippetOptions from "@website/snippets/s_dynamic_snippet/options";

dynamicSnippetOptions.include({

    async _fetchDynamicFilters() {

        console.log("INGRESA A FETCH DYNAMIC FILTERS");
        console.log(this.modelNameFilter);
        console.log(this.contextualFilterDomain);

        const res = await this._super(...arguments);

        console.log("MOSTRANDO RES");
        console.log(res)
    },
    
});

export default dynamicSnippetOptions;
