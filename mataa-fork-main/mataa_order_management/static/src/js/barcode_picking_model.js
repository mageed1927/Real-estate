/** @odoo-module **/

import BarcodePickingModel from '@stock_barcode/models/barcode_picking_model';
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";

patch(BarcodePickingModel.prototype, {

    async validate() {
        const pickingId = this.record && this.record.id;
        if (!pickingId) {
            return await super.validate(...arguments);
        }
        await this.save();

        // Call the SAME method used by the Inventory form
        const action = await this.orm.call(
            "stock.picking",
            "button_validate_with_wizard",
            [[pickingId]],
            { context: this.context }
        );

        // PACK → action is the wizard act_window → open it
        // Non-PACK → button_validate() ran and usually returns nothing (or True)
        if (action && action.type) {
            await this.action.doAction(action);
        } else {
            // If no action returned, assume validation succeeded (standard Odoo behavior)
            
            // Notify the user
            if (this.notification) {
                this.notification(_t("The transfer has been validated"), { type: "success" });
            }
            
            // Navigate to the main menu (Operations overview)
            await this.action.doAction('stock_barcode.stock_barcode_action_main_menu', {
                clear_breadcrumbs: true,
            });
        }
        return true;
    },

    get printButtons() {
        const buttons = super.printButtons;
        buttons.push({
            name: ("Print Invoice"),
            class: 'o_print_mataa_invoice',
            method: 'action_print_related_invoice',
        });
        const printStockMoveButton = {
            name: _t("Print OUT Picking"),
            class: 'o_print_stock_move_out',
            method: 'action_print_out_picking_report',
        };
        buttons.splice(1, 0, printStockMoveButton);
        return buttons;
    },

    showTickets() {
        this.action.doAction({
            name: _t("Tickets"),
            type: "ir.actions.act_window",
            view_mode: "list,form",
            views: [[false, "list"], [false, 'form']],
            target: "current",
            res_model: 'helpdesk.ticket',
            domain: [
                ["mataa_so_id", "=", this.record.mataa_sale_order_id],
                ["mataa_so_id", '!=', false],
            ],
        });
    },

});
