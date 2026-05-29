/** @odoo-module */
import { PivotController } from "@web/views/pivot/pivot_controller";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { onMounted } from "@odoo/owl";

patch(PivotController.prototype, {
    setup() {
        super.setup();
        this.actionService = useService("action");
        this.orm = useService("orm");
        this.ui = useService("ui");

        const runExport = async () => {
            try {
                this.ui.block();
                
                const model = this.model;
                const exportData = model.exportData();
                const table = model.getTable();
                
                const rowGroupBys = model.metaData.rowGroupBys; 

                exportData.rows = exportData.rows.map((row, index) => {
                    const tableRow = table.rows[index];
                    let realProductId = false;
                    if (tableRow && tableRow.indent > 0) {
                        
                        // 1. الطريقة الرسمية (تعتمد على rowGroupBys)
                        const productIndex = rowGroupBys.findIndex(field => 
                            field.includes('product_id') || 
                            field.includes('product_tmpl_id') || 
                            field.includes('product_variant_id') ||
                            field.includes('product_product_id')
                        );
        
                        if (productIndex !== -1) {
                            if (tableRow.indent > productIndex) {
                                const pathArray = tableRow.groupId[0];
                                if (Array.isArray(pathArray) && pathArray.length > productIndex) {
                                    const rawValue = pathArray[productIndex];
                                    if (Array.isArray(rawValue) && rawValue.length > 0) {
                                        realProductId = rawValue[0];
                                    } else if (typeof rawValue === 'number') {
                                        realProductId = rawValue;
                                    }
                                }
                            }
                        }


                        if (!realProductId && rowGroupBys.length === 0 && tableRow.indent === 1) {
                             if (tableRow.groupId && tableRow.groupId.length > 0) {
                                 const ghostData = tableRow.groupId[0];
                                 

                                 if (Array.isArray(ghostData) && ghostData.length > 0) {
                                     realProductId = ghostData[0];
                                 } else if (typeof ghostData === 'number') {
                                     realProductId = ghostData;
                                 }
                             }
                        }
                    }

                    return { 
                        ...row, 
                        product_id: realProductId 
                    };
                });

                console.log(">>> Sending Data to Python...");

                const action = await this.orm.call(
                    'product.brand.sales.wizard', 
                    'generate_catalog', 
                    [], 
                    { json_data_str: JSON.stringify(exportData) }
                );

                await this.actionService.doAction(action);

            } catch (e) {
                console.error("Export Error:", e);
                this.actionService.doAction({
                    type: 'ir.actions.client',
                    tag: 'display_notification',
                    params: {
                        title: 'Error',
                        message: "Failed to generate Excel: " + (e.data?.message || e.message),
                        type: 'danger',
                        sticky: true,
                    }
                });
            } finally {
                this.ui.unblock();
            }
        };

        onMounted(() => {
            setTimeout(() => {
                const oldBtn = document.querySelector(".mataaa_export_btn");
                if (oldBtn) {
                    const newBtn = oldBtn.cloneNode(true);
                    oldBtn.parentNode.replaceChild(newBtn, oldBtn);
                    newBtn.addEventListener("click", runExport);
                }
            }, 1000);
        });
    },
});