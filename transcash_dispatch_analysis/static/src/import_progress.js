/** @odoo-module **/
import { Component, onMounted, onWillStart, onWillUnmount, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class DispatchImportProgress extends Component {
    static template = "transcash_dispatch_analysis.ImportProgress";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.snapshotId = Number(this.props.action?.params?.snapshot_id || 0);
        this.destroyed = false;
        this.running = false;
        this.state = useState({progress: null, running: false, inflight: false, error: ""});
        onWillStart(() => this.refresh());
        // Do not await the whole import in onWillStart: render the progress
        // screen first, then perform one committed request for each batch.
        onMounted(() => {
            if (this.state.progress?.can_process && this.state.progress.can_continue) {
                this.start();
            }
        });
        onWillUnmount(() => { this.destroyed = true; });
    }

    format(value) {
        return new Intl.NumberFormat("es-EC").format(value || 0);
    }

    message(error) {
        return error.data?.message || error.message || "No se pudo comunicar con Odoo. Consulta el estado antes de continuar.";
    }

    async refresh() {
        if (!this.snapshotId) {
            this.state.error = "No se identificó la carga. Ábrela desde Importaciones e histórico.";
            return false;
        }
        try {
            const progress = await this.orm.call("dispatch.snapshot", "get_import_progress", [[this.snapshotId]]);
            if (!this.destroyed) {
                this.state.progress = progress;
                this.state.error = "";
            }
            return true;
        } catch (error) {
            if (!this.destroyed) this.state.error = this.message(error);
            return false;
        }
    }

    async start() {
        if (this.running || this.destroyed) return;
        this.running = true;
        this.state.running = true;
        this.state.error = "";
        try {
            if (!await this.refresh()) return;
            while (!this.destroyed && this.state.progress?.can_process && this.state.progress.can_continue) {
                this.state.inflight = true;
                const progress = await this.orm.call("dispatch.snapshot", "process_import_step", [[this.snapshotId]]);
                if (this.destroyed) return;
                this.state.progress = progress;
                this.state.inflight = false;
                if (!progress.can_continue) break;
                await new Promise(resolve => setTimeout(resolve, progress.busy ? 1000 : 80));
            }
        } catch (error) {
            if (!this.destroyed) this.state.error = this.message(error);
        } finally {
            this.running = false;
            if (!this.destroyed) {
                this.state.running = false;
                this.state.inflight = false;
            }
        }
    }

    async retry() {
        if (this.running || this.destroyed) return;
        try {
            await this.orm.call("dispatch.snapshot", "action_retry", [[this.snapshotId]]);
            await this.start();
        } catch (error) {
            if (!this.destroyed) this.state.error = this.message(error);
        }
    }

    openHistory() { return this.action.doAction("transcash_dispatch_analysis.action_snapshots"); }
    openDashboard() { return this.action.doAction("transcash_dispatch_analysis.action_dashboard"); }

    async openInvoices() {
        const action = await this.orm.call("dispatch.snapshot", "action_open_invoices", [[this.snapshotId]]);
        return this.action.doAction(action);
    }
}

registry.category("actions").add("transcash_dispatch_import_progress", DispatchImportProgress);
