from odoo import models, fields, api
from odoo.exceptions import UserError
from ..data_models.job_dto import JobDTO
from ..services.detrack_service import DetrackService


class PurchaseRequisitionLine(models.Model):
    _inherit = 'purchase.requisition.line'

    ordered_qty = fields.Float(string='Ordered Qty', related='pol_id.product_qty', readonly=True)
    accepted_qty = fields.Float(string='Accepted Qty', related='pol_id.available_qty', readonly=True)
    rejected_qty = fields.Float(string='Rejected Quantity', readonly=True)

    pol_id = fields.Many2one('purchase.order.line', string="POL", readonly=True)
    po_id = fields.Many2one('purchase.order', string="PO", related='pol_id.order_id', readonly=True, store=True)
    so_id = fields.Many2one('sale.order', string="SO", readonly=True, store=True)

    def create_supplier_info(self):
        # don't use the odoo default since it creates supplier info
        pass