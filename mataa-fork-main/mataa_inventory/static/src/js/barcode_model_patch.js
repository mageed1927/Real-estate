/** @odoo-module **/

import BarcodeQuantModel from "@stock_barcode/models/barcode_quant_model";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";

const VALIDATE_BATCH_SIZE = 500;
const VALIDATE_PROGRESS_EVERY_BATCHES = 5;


patch(BarcodeQuantModel.prototype, {
    async _parseBarcode(barcode, filters) {
        this._lastFetchedQuantIdsByBarcode = [];
        try {
            const result = await this.orm.call(
                'stock.quant',
                'fetch_quant_by_barcode',
                [barcode]
            );
            if (result && result.records) {
                this._lastFetchedQuantIdsByBarcode = this._addFetchedQuantRecords(result.records);
            }
        } catch (error) {
            console.warn("Failed fast ORM lookup:", error);
        }

        return super._parseBarcode(barcode, filters);
    },

    _sortLine(lines) {
        return [...lines].sort((l1, l2) => {
            if (l1.is_located !== l2.is_located) {
                return l1.is_located ? 1 : -1;
            }
            const p1 = l1.product_id?.display_name || '';
            const p2 = l2.product_id?.display_name || '';
            if (p1 < p2) return -1;
            if (p1 > p2) return 1;
            return l1.sortIndex > l2.sortIndex ? 1 : -1;
        });
    },

    lineIsSurplus(line) {
        return line.inventory_quantity_set && line.inventory_quantity > line.quantity;
    },

    lineIsFaulty(line) {
        return line.inventory_quantity_set && line.inventory_quantity < line.quantity;
    },

    lineIsComplete(line) {
        return line.inventory_quantity_set && line.inventory_quantity === line.quantity;
    },

    _lineIsNotComplete(line) {
        return !line.inventory_quantity_set || line.inventory_quantity < line.quantity;
    },

    get applyOn() {
        return this.pageLines.length;
    },

    get groupedLines() {
        return this._groupInventoryLinesForDisplay(this._getInventoryLinesForDisplay());
    },

    get displayApplyButton() {

        if (this._allowedAccountIdLoaded) {
            return this.userId === this._allowedAccountId;
        }
        if (!this._allowedAccountIdLoading) {
            this._allowedAccountIdLoading = true;
            this._loadAllowedAccountId();
        }
        return false;
    },

    async _loadAllowedAccountId() {
        try {
            const val = await this.orm.call('stock.quant', 'get_inventory_user_id', []);
            this._allowedAccountId = Number(val) || 0;
        } catch (e) {
            this._allowedAccountId = 0;
        }
        this._allowedAccountIdLoaded = true;
        this.trigger && this.trigger('update');
    },

    async apply() {

        for (const line of this.pageLines) {
            if (!line.inventory_quantity_set) {
                line.inventory_quantity = 0;
                line.inventory_quantity_set = true;
                this._markLineAsDirty(line);
            }


        }
        return await super.apply(...arguments);
    },

    _lineCannotBeTaken(line) {
        if (line.is_located) {
            return true;
        }
        return super._lineCannotBeTaken(...arguments);
    },

    _chunkIds(ids, size) {
        const chunks = [];
        for (let index = 0; index < ids.length; index += size) {
            chunks.push(ids.slice(index, index + size));
        }
        return chunks;
    },

    _addFetchedQuantRecords(records) {
        this.cache.setCache(records);
        const fetchedQuants = records['stock.quant'] || [];
        const fetchedQuantIds = fetchedQuants.map(quant => quant.id);
        const currentLineById = new Map(this.currentState.lines.map(line => [line.id, line]));
        const initialLineIds = new Set(this.initialState.lines.map(line => line.id));

        for (const quant of fetchedQuants) {
            if (currentLineById.has(quant.id)) {
                continue;
            }
            const line = this._quantToLine(quant, currentLineById);
            this.currentState.lines.push(line);
            if (!initialLineIds.has(line.id)) {
                this.initialState.lines.push(Object.assign({}, line));
                initialLineIds.add(line.id);
            }
            currentLineById.set(line.id, line);
        }
        return fetchedQuantIds;
    },

    async _refreshBarcodeData() {
        const result = await this.rpc('/stock_barcode/get_barcode_data', {
            model: this.resModel,
            res_id: this.resId || false,
        });
        await this.refreshCache(result.data.records);
        this.trigger('update');
    },

    _goBackAfterValidation() {
        this.trigger('history-back');
    },

    _recordId(value) {
        if (Array.isArray(value)) {
            return value[0] || false;
        }
        return value && typeof value === "object" ? value.id : value;
    },

    _isQuantAvailableForCurrentUser(quant, today) {
        const userId = this._recordId(quant.user_id);
        const assignedBy = this._recordId(quant.assigned_by);
        return (userId === this.userId || assignedBy === this.userId) && quant.inventory_date <= today;
    },

    _findLine(barcodeData) {
        const fetchedQuantIds = this._lastFetchedQuantIdsByBarcode || [];
        if (barcodeData.product && fetchedQuantIds.length) {
            const fetchedLine = this.pageLines.find(line =>
                fetchedQuantIds.includes(line.id) &&
                line.product_id.id === barcodeData.product.id &&
                !this._lineCannotBeTaken(line) &&
                this._lineIsNotComplete(line)
            );
            if (fetchedLine) {
                return fetchedLine;
            }
        }
        return super._findLine(...arguments);
    },

    _quantToLine(quant, previousLineById) {
        const previousLine = previousLineById.get(quant.id);
        const previousVirtualId = previousLine && previousLine.virtual_id;
        const productId = this._recordId(quant.product_id);
        const locationId = this._recordId(quant.location_id);
        const lotId = this._recordId(quant.lot_id);
        const packageId = this._recordId(quant.package_id);
        const ownerId = this._recordId(quant.owner_id);

        return Object.assign({}, quant, {
            dummy_id: quant.dummy_id && Number(quant.dummy_id),
            virtual_id: quant.dummy_id || previousVirtualId || this._uniqueVirtualId,
            product_id: this.cache.getRecord('product.product', productId),
            location_id: this.cache.getRecord('stock.location', locationId),
            lot_id: lotId && this.cache.getRecord('stock.lot', lotId),
            package_id: packageId && this.cache.getRecord('stock.quant.package', packageId),
            owner_id: ownerId && this.cache.getRecord('res.partner', ownerId),
        });
    },

    _createLinesState() {
        const today = new Date().toISOString().slice(0, 10);
        const previousLines = this.currentState?.lines || [];
        const previousLineById = new Map(previousLines.map(line => [line.id, line]));
        const lines = [];
        const addedIds = new Set();
        const quantIds = Object.keys(this.cache.dbIdCache['stock.quant'] || {}).map(id => Number(id));

        const addLine = id => {
            if (!id) {
                return;
            }
            if (addedIds.has(id)) {
                return;
            }
            const quant = this.cache.getRecord('stock.quant', id);
            if (!quant || !this._isQuantAvailableForCurrentUser(quant, today)) {
                return;
            }
            lines.push(this._quantToLine(quant, previousLineById));
            addedIds.add(id);
        };

        for (const previousLine of previousLines) {
            if (previousLine.inventory_quantity_set || previousLine.virtual_id === this.selectedLineVirtualId) {
                addLine(previousLine.id);
            }
        }
        for (const id of quantIds) {
            addLine(id);
        }
        return lines;
    },

    _getInventoryLinesForDisplay() {
        const lines = [];
        const addedVirtualIds = new Set();

        const addLine = line => {
            if (!line || addedVirtualIds.has(line.virtual_id)) {
                return;
            }
            lines.push(line);
            addedVirtualIds.add(line.virtual_id);
        };

        addLine(this.selectedLine);
        addLine(this.lastScannedLine);
        for (const line of this.pageLines) {
            if (line.inventory_quantity_set || line.virtual_id === this.selectedLineVirtualId) {
                addLine(line);
            }
        }
        return lines;
    },

    _groupInventoryLinesForDisplay(displayLines) {
        if (!this.groups.group_production_lot) {
            return this._sortLine(displayLines);
        }

        const lines = [...displayLines];
        const groupedLinesByKey = {};
        for (let index = lines.length - 1; index >= 0; index--) {
            const line = lines[index];
            if (line.product_id.tracking === 'none' || line.lines) {
                continue;
            }
            const key = this.groupKey(line);
            if (!groupedLinesByKey[key]) {
                groupedLinesByKey[key] = [];
            }
            groupedLinesByKey[key].push(...lines.splice(index, 1));
        }
        for (const sublines of Object.values(groupedLinesByKey)) {
            if (sublines.length === 1) {
                lines.push(...sublines);
                continue;
            }
            const ids = [];
            const virtual_ids = [];
            let [qtyDemand, qtyDone] = [0, 0];
            for (const subline of sublines) {
                ids.push(subline.id);
                virtual_ids.push(subline.virtual_id);
                qtyDemand += this.getQtyDemand(subline);
                qtyDone += this.getQtyDone(subline);
            }
            lines.push(this._groupSublines(sublines, ids, virtual_ids, qtyDemand, qtyDone));
        }
        return this._sortLine(lines);
    },

    async _processBarcode(barcode) {
        const barcodeData = await this._parseBarcode(barcode);

        if (barcodeData.location || barcodeData.package) {
            if (this._lastScanWasLocation) {
                this.notification(_t("يجب مسح منتج قبل مسح موقع جديد"), { type: "warning" });
                return;
            }

            let targetLocation = barcodeData.location;
            let targetPackage = barcodeData.package;

            if (!targetLocation && targetPackage) {
                const locId = Array.isArray(targetPackage.location_id) ? targetPackage.location_id[0] : targetPackage.location_id;
                if (locId) {
                    targetLocation = await this.cache.getRecord('stock.location', locId);
                }
            }

            if (targetLocation) {
                await this._processUILinesToLocation(targetLocation, targetPackage);
                this._lastScanWasLocation = true;
                return;
            }
        }

        this._lastScanWasLocation = false;
        return super._processBarcode(barcode);
    },

    lineIsInTheCurrentLocation(line) {
        return true;
    },


    async _processUILinesToLocation(location, pkg = false) {
        if (!location) return;

        await this.save();

        const linesToProcess = this.pageLines.filter(l => l.inventory_quantity_set && l.inventory_quantity > 0 && !l.is_located);

        if (linesToProcess.length === 0) {
            this.notification(_t("No products scanned to move."), { type: "warning" });
            await this._refreshBarcodeData();
            return;
        }


        const bufferData = linesToProcess.map(l => ({
            quant_id: l.id,
            product_id: Array.isArray(l.product_id) ? l.product_id[0] : l.product_id.id,
            quantity: l.inventory_quantity,
            location_id: l.location_id?.id || false,
            package_id: l.package_id?.id || false,
            owner_id: l.owner_id?.id || false,
            user_id: l.user_id?.id || l.user_id || false,
            assigned_by: l.assigned_by?.id || l.assigned_by || false,
        }));

        try {
            await this.orm.call("stock.quant", "action_process_barcode_buffer", [
                bufferData,
                location.id,
                pkg ? pkg.id : false
            ]);

            this.notification(_t("Successfully moved items to %s", location.display_name), { type: "success" });

            await this._refreshBarcodeData();
            
            this.trigger('refresh');
            return;

        } catch (e) {
            console.error("Move Error:", e);
            const errorMsg = e.message || e.data?.message || _t("Unknown error");
            this.notification(_t("Error moving items: ") + errorMsg, { type: "danger" });
        }
    },

    async confirmScannedMoves() {
        await this.save();

        const linesToConsider = this.pageLines.filter(l => l.inventory_quantity_set);
        const linesToValidate = linesToConsider.filter(l => l.inventory_quantity === l.quantity);
        const skippedCount = linesToConsider.length - linesToValidate.length;

        if (linesToValidate.length === 0) {
            const warningMsg = skippedCount > 0
                ? _t("All lines have deficits and require manager review.")
                : _t("No scanned lines to confirm.");
            this.notification(warningMsg, { type: "warning" });
            return;
        }

        const lineIds = linesToValidate.map(l => l.id);
        const batches = this._chunkIds(lineIds, VALIDATE_BATCH_SIZE);
        let action = false;
        let validatedCount = 0;

        if (batches.length > 1) {
            this.notification(
                _t("Validating %s lines in %s batches.", lineIds.length, batches.length),
                { type: "info" }
            );
        }

        for (let index = 0; index < batches.length; index++) {
            const batchAction = await this.orm.call('stock.quant', 'action_validate', [batches[index]]);
            validatedCount += batches[index].length;

            if (batchAction && batchAction.res_model) {
                action = batchAction;
                break;
            }

            if (
                batches.length > 1 &&
                ((index + 1) % VALIDATE_PROGRESS_EVERY_BATCHES === 0 || index + 1 === batches.length)
            ) {
                this.notification(
                    _t("Validated %s/%s lines.", validatedCount, lineIds.length),
                    { type: "info" }
                );
            }

            await new Promise(resolve => setTimeout(resolve, 0));
        }

        let successMsg = _t("%s lines validated.", validatedCount);
        if (skippedCount > 0) {
            successMsg += _t(" %s lines skipped due to deficit.", skippedCount);
        }
        this.notification(successMsg, { type: "success" });

        const notifyAndGoAhead = res => {
            if (res && res.special) {
                return this.trigger('refresh');
            }
            this.notification(_t("The inventory adjustment has been validated"), { type: "success" });
            return this._goBackAfterValidation();
        };
        if (action && action.res_model) {
            return this.action.doAction(action, { onClose: notifyAndGoAhead });
        }
        notifyAndGoAhead();
    },

    async confirmSurplusMoves() {
        await this.save();

        const linesToConsider = this.pageLines.filter(l => l.inventory_quantity_set);
        const linesToValidate = linesToConsider.filter(l => l.inventory_quantity > l.quantity);
        const skippedCount = linesToConsider.length - linesToValidate.length;

        if (linesToValidate.length === 0) {
            const warningMsg = skippedCount > 0
                ? _t("No surplus lines found. Nothing to validate.")
                : _t("No scanned lines to confirm.");
            this.notification(warningMsg, { type: "warning" });
            return;
        }

        const lineIds = linesToValidate.map(l => l.id);
        const batches = this._chunkIds(lineIds, VALIDATE_BATCH_SIZE);
        let action = false;
        let validatedCount = 0;

        if (batches.length > 1) {
            this.notification(
                _t("Validating %s surplus lines in %s batches.", lineIds.length, batches.length),
                { type: "info" }
            );
        }

        for (let index = 0; index < batches.length; index++) {
            const batchAction = await this.orm.call('stock.quant', 'action_validate', [batches[index]]);
            validatedCount += batches[index].length;

            if (batchAction && batchAction.res_model) {
                action = batchAction;
                break;
            }

            if (
                batches.length > 1 &&
                ((index + 1) % VALIDATE_PROGRESS_EVERY_BATCHES === 0 || index + 1 === batches.length)
            ) {
                this.notification(
                    _t("Validated %s/%s surplus lines.", validatedCount, lineIds.length),
                    { type: "info" }
                );
            }

            await new Promise(resolve => setTimeout(resolve, 0));
        }

        let successMsg = _t("%s surplus lines validated.", validatedCount);
        if (skippedCount > 0) {
            successMsg += _t(" %s lines skipped because they are not surplus.", skippedCount);
        }
        this.notification(successMsg, { type: "success" });

        const notifyAndGoAhead = res => {
            if (res && res.special) {
                return this.trigger('refresh');
            }
            this.notification(_t("The surplus lines have been validated"), { type: "success" });
            return this._goBackAfterValidation();
        };
        if (action && action.res_model) {
            return this.action.doAction(action, { onClose: notifyAndGoAhead });
        }
        notifyAndGoAhead();
    }
});
