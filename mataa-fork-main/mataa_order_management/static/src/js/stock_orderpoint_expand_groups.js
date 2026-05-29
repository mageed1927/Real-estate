/** @odoo-module **/
import {patch} from "@web/core/utils/patch";
import {StockOrderpointListController} from "@stock/views/stock_orderpoint_list_controller";


patch(StockOrderpointListController.prototype, {
  async onClickExpand(){
    const groups = this.model.root.groups || [];
    return this._setGroupOpenState(groups, true);
  },


  async _setGroupOpenState(groups, open){
    for (const group of groups) {
      if (!!group.isOpen !== open) {
        await group.toggle();
      }
      if (group.list?.groups?.length) {
        await this._setGroupOpenState(group.list.groups, open);
      }
    }
  },
});
