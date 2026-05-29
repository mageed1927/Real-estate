/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import BarcodePickingBatchModel from "@stock_barcode_picking_batch/models/barcode_picking_batch_model";
import { _t } from "@web/core/l10n/translation";

patch(BarcodePickingBatchModel.prototype, {
    _createState() {
        super._createState(...arguments);
        if (this.record.scan_by_transfer) {
            this.scanTransferEnabled = true;
            console.log("Camex transfer scanning enabled for batch:", this.record.name);
        }
    },

    async onBarcodeScanned(barcode) {
        console.log("[Camex Patch] onBarcodeScanned:", barcode);
        if (this.scanTransferEnabled && barcode) {
            const scanned = barcode.trim().toLowerCase();
            const matchId = this.record.picking_ids.find((id) => {
                const picking = this.cache.getRecord("stock.picking", id);
                return picking && picking.name && picking.name.toLowerCase() === scanned;
            });

            if (matchId) {
                const picking = this.cache.getRecord("stock.picking", matchId);
                console.log("[Camex Patch] Matched transfer:", picking.name);
                this.picking = picking;
                this.notification(_t("Transfer %s selected", picking.name));
                this.trigger("update");
                return true;
            }
        }

        if (super.onBarcodeScanned) {
            return super.onBarcodeScanned(...arguments);
        } else if (super._barcodeScanned) {
            return super._barcodeScanned(...arguments);
        } else if (super._step) {
            return super._step(...arguments);
        }
    },
});
