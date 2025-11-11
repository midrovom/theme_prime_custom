/** @odoo-module **/

import dynamicSnippetOptions from "@website/snippets/s_dynamic_snippet/options";

dynamicSnippetOptions.include({

    // async _fetchDynamicFilters() {

    //     console.log("INGRESA A FETCH DYNAMIC FILTERS");
    //     console.log(this.modelNameFilter);
    //     console.log(this.contextualFilterDomain);

    //     const res = await this._super(...arguments);

    //     console.log("MOSTRANDO RES");
    //     console.log(res)
    // },

    async _fetchDynamicFilterTemplates() {
        const filter = this.dynamicFilters[this.$target.get(0).dataset['filterId']] || this.dynamicFilters[this._defaultFilterId];
        
        console.log(filter);
        
        this.dynamicFilterTemplates = {};
        if (!filter) {
            return [];
        }
        const dynamicFilterTemplates = await rpc('/website/snippet/filter_templates', {
            filter_name: filter.model_name.replaceAll('.', '_'),
        });

        console.log(dynamicFilterTemplates);

        for (let index in dynamicFilterTemplates) {
            this.dynamicFilterTemplates[dynamicFilterTemplates[index].key] = dynamicFilterTemplates[index];
        }
        this._defaultTemplateKey = dynamicFilterTemplates[0].key;
    },
    
});

export default dynamicSnippetOptions;
