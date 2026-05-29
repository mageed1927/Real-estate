/** @odoo-module **/

import BarcodeModel from '@stock_barcode/models/barcode_model';
import { patch } from "@web/core/utils/patch";

// Save original implementation so we can call it
const _superProcessBarcode = BarcodeModel.prototype._processBarcode;

patch(BarcodeModel.prototype, {
    // Keep your button logic
    getDisplayButtons(line) {
        return this.groups.group_edit_lines_barcodes;
    },

    // Translate additional barcodes → main barcode
    async _processBarcode(barcode) {
        console.log("[mataa] scanned:", barcode);

        // If nothing was scanned, just call the original method
        if (!barcode) {
            return await _superProcessBarcode.call(this, barcode);
        }

        let translated = barcode;

        try {
            const orm =
                this.orm ||
                (this.env && this.env.services && this.env.services.orm);

            if (orm) {
                translated = await orm.call(
                    "product.product",
                    "mataa_translate_barcode",
                    [],
                    { barcode }
                );
                console.log("[mataa] translated:", barcode, "→", translated);
            } else {
                console.warn("[mataa] ORM service not found on BarcodeModel");
            }
        } catch (e) {
            console.warn("[mataa] RPC mataa_translate_barcode failed:", e);
            translated = barcode;  // fallback
        }

        // Call the original method with the translated barcode
        return await _superProcessBarcode.call(this, translated);
    },
});
