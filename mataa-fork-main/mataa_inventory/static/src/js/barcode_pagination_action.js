/** @odoo-module **/

import BarcodeQuantModel from "@stock_barcode/models/barcode_quant_model";
import { patch } from "@web/core/utils/patch";

patch(BarcodeQuantModel.prototype, {
    async openQuantPaginationView() {
        await this.save();
        const actionReference = 'mataa_inventory.action_stock_quant_barcode_pagination';
        return this.action.doAction(actionReference, {
            additionalContext: { search_default_my_count: 1 }
        });
    }
});
