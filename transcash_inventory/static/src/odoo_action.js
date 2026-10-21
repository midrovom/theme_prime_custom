/** @odoo-module **/
import { Component, onMounted, onWillUnmount, useRef, useState } from '@odoo/owl';
import { registry } from '@web/core/registry';
import { useService } from '@web/core/utils/hooks';

// The active company is independent of the user default company.  An iframe
// must be remounted on a company change, otherwise it retains stale JS data.
class TranscashCompanyAction extends Component {
    setup() {
        this.company = useService('company');
        this.scope = useState({ id: this.company.currentCompany.id });
        this._companyPoll = null;
        onMounted(() => {
            this._companyPoll = window.setInterval(() => {
                const id = this.company.currentCompany.id;
                if (id !== this.scope.id) this.scope.id = id;
            }, 650);
        });
        onWillUnmount(() => {
            if (this._companyPoll !== null) window.clearInterval(this._companyPoll);
        });
    }
    get frameSrc() {
        return `${this.constructor.route}?v=18.0.1.28.0&company_id=${encodeURIComponent(this.scope.id)}`;
    }
}

export class TranscashDashboardAction extends TranscashCompanyAction {
    static template = 'transcash_inventory.DashboardAction';
    static route = '/transcash_inventory/dashboard';
}
registry.category('actions').add('transcash_inventory.dashboard', TranscashDashboardAction);

export class TranscashImportAction extends TranscashCompanyAction {
    static template = 'transcash_inventory.ImportAction';
    static route = '/transcash_inventory/import';
    setup() {
        super.setup();
        this.action = useService('action');
        this.frame = useRef('importFrame');
        this.onUploadCompleted = (event) => {
            if (event.origin !== window.location.origin || !this.frame.el ||
                    event.source !== this.frame.el.contentWindow) return;
            if (event.data?.type === 'transcash_inventory:imported' ||
                    event.data?.type === 'transcash_inventory:view_dashboard') {
                this.action.doAction('transcash_inventory.action_transcash_dashboard');
            }
        };
        onMounted(() => window.addEventListener('message', this.onUploadCompleted));
        onWillUnmount(() => window.removeEventListener('message', this.onUploadCompleted));
    }
}
registry.category('actions').add('transcash_inventory.import', TranscashImportAction);

export class TranscashPhotosAction extends TranscashCompanyAction {
    static template = 'transcash_inventory.PhotosAction';
    static route = '/transcash_inventory/photos/scan';
}
registry.category('actions').add('transcash_inventory.photos', TranscashPhotosAction);

export class TranscashAIConfigurationAction extends TranscashCompanyAction {
    static template = 'transcash_inventory.AIConfigurationAction';
    static route = '/transcash_inventory/ai/configuration';
}
registry.category('actions').add('transcash_inventory.ai_configuration', TranscashAIConfigurationAction);

export class TranscashImportedAction extends TranscashCompanyAction {
    static template = 'transcash_inventory.ImportedAction';
    static route = '/transcash_inventory/imported';
}
registry.category('actions').add('transcash_inventory.imported', TranscashImportedAction);
