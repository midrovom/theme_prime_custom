/** @odoo-module **/

import { registry } from '@web/core/registry';
// All of our work will be trash because registry will be no longer useful in next version.
let PRODUCTS_DATA = { models: ['product.template', 'product.product'], fields: ['name', 'list_price', 'dr_stock_label'], fieldsToMarkUp: ['price', 'list_price', 'dr_stock_label']}
let SELECTOR_DATA = { TpRecordSelector: { ...PRODUCTS_DATA, defaultVal: { selectionType: 'manual', recordsIDs: [], model: 'product.template'}}};
let EXTRA_OPTIONS = { TpExtraOpts: { startDate: '', endDate: '', priceList: '*' } };

// registry.category('theme_prime_snippet_registry')
//     .add('s_d_image_products_block_conedera', { widgets: { ...SELECTOR_DATA, ...EXTRA_OPTIONS }, defaultValue: { hasSwitcher: true, } })


// Registrar snippet en el registry
registry.category('theme_prime_snippet_registry')
    .add('s_d_product_small_block_conedera', { widgets: { ...SELECTOR_DATA, ...EXTRA_OPTIONS }, defaultValue: { noSnippet: true }});
    // .add('s_d_image_products_block_conedera', { 
    //     // template: 's_d_image_products_block_conedera',
    //     widgets: { ...SELECTOR_DATA, ...EXTRA_OPTIONS }, 
    //     defaultValue: { hasSwitcher: true }
    // });