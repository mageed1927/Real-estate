/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import MainComponent from "@stock_barcode/components/main";
import { _t } from "@web/core/l10n/translation";

patch(MainComponent.prototype, {
    async onBarcodeScanned(barcode) {
        const model = this.env.model;
        if (model?.record?.scan_by_transfer && barcode) {
            const scanned = barcode.trim().toLowerCase();

            // Find the transfer
            const matchId = model.record.picking_ids.find((id) => {
                const picking = model.cache.getRecord("stock.picking", id);
                return picking && picking.name && picking.name.toLowerCase() === scanned;
            });
            if (!matchId) return super.onBarcodeScanned(...arguments);

            const picking = model.cache.getRecord("stock.picking", matchId);
            console.log("[Camex] Transfer matched:", picking.name);

            try {
                const updatedCount = await model.orm.call(
                    "stock.picking.batch",
                    "camex_fill_quantities",
                    [[picking.id]]
                );

                const data = await model.orm.call(
                    "stock.picking.batch",
                    "camex_get_barcode_data",
                    [[model.resId]]
                );

                // Rebuild the barcode model cache
                if (model.refreshCache) {
                    await model.refreshCache(data.records);
                } else if (model.reload) {
                    await model.reload();
                }

                model.config = data.config || model.config;
                model.picking = model.cache.getRecord("stock.picking", matchId);
                model.trigger("update");

                if (updatedCount) {
                    model.notification(
                        _t("Transfer %s quantities set (%s lines) ✅ ", picking.name, updatedCount)
                    );
                } else {
                    model.notification(
                        _t("Transfer %s already fully processed", picking.name)
                    );
                }
                return true;
            } catch (error) {
                console.error("Camex qty update failed:", error);
                model.notification(
                    _t("Error updating transfer %s", picking.name),
                    { type: "warning" }
                );
    return true;
}
        }
        return super.onBarcodeScanned(...arguments);
    },
});
