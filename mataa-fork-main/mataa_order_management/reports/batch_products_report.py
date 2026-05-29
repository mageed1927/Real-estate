from odoo import models


class ReportBatchProducts(models.AbstractModel):
    _name = 'report.mataa_order_management.report_batch_products_template'
    _description = 'Batch Products Report Parser'

    def _get_report_values(self, docids, data=None):
        context = data.get('context') if data else {}
        active_ids = context.get('active_ids') or []
        batches = self.env['stock.picking.batch'].browse(docids or active_ids)

        lines = data.get('lines', [])
        for l in lines:
            l['vendor_bill_ref'] = l.get('vendor_bill_ref', '-')

        return {
            'doc_ids': batches.ids,
            'doc_model': 'stock.picking.batch',
            'docs': batches,
            'lines': lines,
        }