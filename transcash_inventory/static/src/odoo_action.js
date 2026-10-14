/** @odoo-module **/
import { Component } from '@odoo/owl';
import { registry } from '@web/core/registry';

export class TranscashDashboardAction extends Component {
    static template = 'transcash_inventory.DashboardAction';
}
registry.category('actions').add('transcash_inventory.dashboard', TranscashDashboardAction);
