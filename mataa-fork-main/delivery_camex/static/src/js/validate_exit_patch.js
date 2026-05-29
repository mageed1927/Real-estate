/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import BarcodePickingBatchModel from "@stock_barcode_picking_batch/models/barcode_picking_batch_model";
import { _t } from "@web/core/l10n/translation";

patch(BarcodePickingBatchModel.prototype, {
    async validate() {
        if (this.resModel === "stock.picking.batch" && this.resId) {
            try {
                await this.save();
                const context = Object.assign({}, this.context, {
                    'skip_pack_validation_wizard': true
                });
                const action = await this.orm.call(
                    "stock.picking.batch",
                    "action_done",
                    [[this.resId]],
                    { context: context }
                );
                if (action && typeof action === 'object' && action.type) {
                    // This opens the Backorder Wizard popup for the user
                    return await this.action.doAction(action);
                } else {
                    // Only show success if no wizard was needed
                    this.notification(_t("The Batch has been validated"), { type: "success" });

                    if (this.record && this.resId) {
                        // Refresh cache/UI so the user sees the 'Done' status
                        if (this.reload) {
                            await this.reload();
                        }
                        this.trigger("update");
                    }
                }
                return true;
            } catch (error) {
                console.error("Batch validation error", error);
                this.notification(_t("Error while validating batch"), { type: "warning" });
                return false;
            }
        }

        return await super.validate(...arguments);
    },
});