/** @odoo-module **/
import { Component, onMounted, onWillUnmount, useRef } from '@odoo/owl';
import { registry } from '@web/core/registry';
import { useService } from '@web/core/utils/hooks';

export class TranscashDashboardAction extends Component {
    static template = 'transcash_inventory.DashboardAction';
}
registry.category('actions').add('transcash_inventory.dashboard', TranscashDashboardAction);

export class TranscashImportAction extends Component {
    static template = 'transcash_inventory.ImportAction';
    setup() {
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

export class TranscashPhotosAction extends Component {
    static template = 'transcash_inventory.PhotosAction';
}
registry.category('actions').add('transcash_inventory.photos', TranscashPhotosAction);
