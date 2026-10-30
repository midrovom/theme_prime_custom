/** @odoo-module **/
import { Component, onMounted, onWillStart, onWillUnmount, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class DispatchImportProgress extends Component {
    static template = "transcash_dispatch_analysis.ImportProgress";

    setup() {
        this.orm = useService("orm");
        // Keep Odoo's global busy overlay off this dedicated progress view.
        const silent = this.orm.silent;
        this.backgroundOrm = silent && typeof silent === "object" && typeof silent.call === "function" ? silent : this.orm;
        this.action = useService("action");
        this.snapshotId = Number(this.props.action?.params?.snapshot_id || 0);
        this.sourceId = Number(this.props.action?.params?.source_id || 0);
        this.apiRequested = Boolean(this.sourceId && this.props.action?.params?.sync_api);
        this.destroyed = false;
        this.running = false;
        this.state = useState({progress: null, running: false, inflight: false,
            fetching: this.apiRequested, reconnecting: false, background: false, error: "", syncMessage: ""});
        onWillStart(() => this.apiRequested ? undefined : this.refresh());
        // Do not await the whole import in onWillStart: render the progress
        // screen first, then perform one committed request for each batch.
        onMounted(() => {
            if (this.apiRequested) {
                this.syncERP();
            } else if (this.state.progress?.can_process && this.state.progress.can_continue) {
                this.start();
            }
        });
        onWillUnmount(() => { this.destroyed = true; });
    }

    format(value) {
        return new Intl.NumberFormat("es-EC").format(value || 0);
    }

    get isERP() {
        if (this.state.progress?.input_type) return this.state.progress.input_type === "api";
        return Boolean(this.sourceId || this.state.progress?.input_type === "api" || this.props.action?.params?.input_type === "api");
    }

    get indeterminate() {
        return this.state.fetching || Boolean(this.state.running && this.state.progress?.state === "queued");
    }

    get phaseTitle() {
        const progress = this.state.progress;
        if (this.state.reconnecting) return "Restableciendo la conexión…";
        if (this.state.fetching) return "Recibiendo datos del ERP…";
        if (progress?.done) return this.isERP ? "Sincronización terminada" : "Importación terminada";
        if (progress?.failed) return this.isERP ? "La sincronización se detuvo" : "La importación se detuvo";
        if (progress?.busy) return "La actualización está en curso";
        if (progress?.state === "queued" && this.state.running) return this.isERP ? "Validando datos del ERP…" : "Leyendo y validando el Excel…";
        if (this.state.running) return this.isERP ? "Actualizando facturas…" : "Importando facturas…";
        return this.isERP ? "Datos recibidos del ERP" : "Archivo recibido";
    }

    async syncERP() {
        if (this.running || this.destroyed || !this.sourceId) return;
        this.running = true;
        this.state.running = true;
        this.state.fetching = true;
        this.state.error = "";
        this.state.syncMessage = "";
        try {
            const result = await this.backgroundOrm.call("dispatch.source", "sync_api_data", [[this.sourceId]]);
            if (this.destroyed) return;
            if (!result.snapshot_id || result.error) {
                this.state.error = result.message || "No se pudo recibir la información del ERP. Vuelve a intentar.";
                return;
            }
            this.snapshotId = Number(result.snapshot_id);
            this.state.progress = result.progress || null;
            this.state.syncMessage = result.unchanged ? "La información ya estaba actualizada." : "";
            this.state.fetching = false;
            this.running = false;
            this.state.running = false;
            await this.start();
        } catch (error) {
            if (!this.destroyed) this.state.error = this.message(error);
        } finally {
            this.running = false;
            if (!this.destroyed) {
                this.state.fetching = false;
                this.state.running = false;
                this.state.inflight = false;
            }
        }
    }

    message(error) {
        if (this.isConnectionError(error)) return "Se interrumpió la conexión con Odoo. Puedes consultar el último avance guardado y continuar esta misma carga desde el historial.";
        return error?.data?.message || error?.message || "No se pudo comunicar con Odoo. Consulta el estado antes de continuar.";
    }

    isConnectionError(error) {
        if (error?.data) return false;
        return error?.name === "ConnectionLostError" || /couldn.t be established|was interrupted|failed to fetch|networkerror|network disconnected|connection lost|connection to .*interrupted/i.test(error?.message || "");
    }

    pause(milliseconds) {
        return new Promise(resolve => setTimeout(resolve, milliseconds));
    }

    async refresh() {
        if (!this.snapshotId) {
            this.state.error = "No se identificó la carga. Ábrela desde Importaciones e histórico.";
            return false;
        }
        for (let attempt = 0; attempt < 4 && !this.destroyed; attempt++) {
            try {
                const progress = await this.backgroundOrm.call("dispatch.snapshot", "get_import_progress", [[this.snapshotId]]);
                if (this.destroyed) return false;
                this.state.progress = progress;
                this.state.error = "";
                this.state.reconnecting = false;
                return true;
            } catch (error) {
                if (this.destroyed) return false;
                if (this.isConnectionError(error) && attempt < 3) {
                    this.state.reconnecting = true;
                    await this.pause(1000 * (attempt + 1));
                    continue;
                }
                this.state.error = this.message(error);
                this.state.reconnecting = false;
                return false;
            }
        }
        return false;
    }

    async start() {
        if (this.running || this.destroyed) return;
        this.running = true;
        this.state.running = true;
        this.state.error = "";
        try {
            if (!await this.refresh()) return;
            let backgroundRequested = false;
            let lostSteps = 0;
            while (!this.destroyed && this.state.progress?.can_process && this.state.progress.can_continue) {
                if (this.state.progress.background_processing) {
                    this.state.background = true;
                    if (!backgroundRequested) {
                        backgroundRequested = true;
                        try {
                            const progress = await this.backgroundOrm.call("dispatch.snapshot", "request_background_processing", [[this.snapshotId]]);
                            if (this.destroyed) return;
                            this.state.progress = progress;
                        } catch (error) {
                            if (!this.isConnectionError(error)) throw error;
                            this.state.reconnecting = true;
                            await this.pause(1000);
                            if (!await this.refresh()) return;
                        }
                    } else {
                        await this.pause(1500);
                        if (!await this.refresh()) return;
                    }
                    continue;
                }
                this.state.background = false;
                this.state.inflight = true;
                let progress;
                try {
                    progress = await this.backgroundOrm.call("dispatch.snapshot", "process_import_step", [[this.snapshotId]]);
                    lostSteps = 0;
                } catch (error) {
                    this.state.inflight = false;
                    if (!this.isConnectionError(error) || ++lostSteps > 3) throw error;
                    // The response may have been lost AFTER commit. Read the
                    // persisted cursor before considering any new write.
                    this.state.reconnecting = true;
                    await this.pause(1000);
                    if (!await this.refresh()) return;
                    continue;
                }
                if (this.destroyed) return;
                this.state.progress = progress;
                this.state.inflight = false;
                if (!progress.can_continue) break;
                await this.pause(progress.busy ? 1000 : 80);
            }
        } catch (error) {
            if (!this.destroyed) this.state.error = this.message(error);
        } finally {
            this.running = false;
            if (!this.destroyed) {
                this.state.running = false;
                this.state.inflight = false;
                this.state.reconnecting = false;
            }
        }
    }

    async retry() {
        if (this.running || this.destroyed) return;
        try {
            await this.backgroundOrm.call("dispatch.snapshot", "action_retry", [[this.snapshotId]]);
            await this.start();
        } catch (error) {
            if (!this.destroyed) this.state.error = this.message(error);
        }
    }

    openHistory() { return this.action.doAction("transcash_dispatch_analysis.action_snapshots"); }
    openDashboard() { return this.action.doAction("transcash_dispatch_analysis.action_dashboard"); }

    async openInvoices() {
        const action = await this.backgroundOrm.call("dispatch.snapshot", "action_open_invoices", [[this.snapshotId]]);
        return this.action.doAction(action);
    }
}

registry.category("actions").add("transcash_dispatch_import_progress", DispatchImportProgress);
