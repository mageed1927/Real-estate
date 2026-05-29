/** @odoo-module **/

import { FormController } from "@web/views/form/form_controller";
import { ListController } from '@web/views/list/list_controller';
import { useService } from "@web/core/utils/hooks";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { registry } from "@web/core/registry";
import { patch } from "@web/core/utils/patch";

// Form duplicate
patch(FormController.prototype, {
    async duplicateRecord() {
        if (this.props.resModel === 'sale.order') {
            this.dialogService.add(ConfirmationDialog, {
                body: ("Are you sure you want to duplicate this record?"),
                confirm: () => { super.duplicateRecord(); },
                cancel: () => {},
            });
        } else {
            super.duplicateRecord();
        }
    }
});

// List duplicate
patch(ListController.prototype, {
    async duplicateRecords() {
        if (this.props.resModel === 'sale.order') {
            this.dialogService.add(ConfirmationDialog, {
                body: ("Are you sure you want to duplicate this records?"),
                confirm: () => { super.duplicateRecords(); },
                cancel: () => {},
            });
        } else {
            super.duplicateRecords();
        }
    }
});
