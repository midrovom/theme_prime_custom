/** @odoo-module **/

import dynamicSnippetOptions from "@website/snippets/s_dynamic_snippet/options";
import { rpc } from "@web/core/network/rpc";

dynamicSnippetOptions.include({

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
