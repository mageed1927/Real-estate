/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";

import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class FilterAlertSystray extends Component {
    static components = { Dropdown, DropdownItem };
    static props = {};
    static template = "mataa_product_management.FilterAlertSystray";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({ alerts: [] });
        onWillStart(() => this.loadAlerts());
    }

    async loadAlerts() {
        try {
            this.state.alerts = await this.orm.searchRead(
                "product.filter.alert",
                [["enabled", "=", true]],
                ["id", "name", "product_count", "domain", "enabled"]
            );
        } catch (e) {
            console.warn("FilterAlertSystray: Could not load alerts —", e);
            this.state.alerts = [];
        }
    }

    get totalCount() {
        return this.state.alerts.reduce(
            (sum, alert) => (alert.enabled ? sum + alert.product_count : sum),
            0
        );
    }

    onBeforeOpen() {
        this.loadAlerts();
    }

    async openProductsList(alert) {
        const action = await this.orm.call(
            "product.filter.alert",
            "action_open_product_list",
            [alert.id]
        );
        this.action.doAction(action);
    }
}

registry.category("systray").add(
    "mataa_product_management.FilterAlertSystray",
    { Component: FilterAlertSystray },
    { sequence: 25 }
);