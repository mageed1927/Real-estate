from odoo import models, fields, api
from odoo.exceptions import UserError
from ..data_models.job_dto import JobDTO
from ..services.detrack_service import DetrackService


class PurchaseRequisition(models.Model):
    _inherit = 'purchase.requisition'

    external_id = fields.Char(string="Dtrack Id", readonly=True)
    prevent_line_addition = fields.Boolean(string="Prevent Adding New Lines", default=False)
    ordering_date = fields.Date(string="Ordering Date", tracking=True, default=fields.Datetime.today())
    total_ordered_qty = fields.Float(string="Ordered Qty", compute="_compute_total_qtys", store=True)
    total_accepted_qty = fields.Float(string="Accepted Qty", compute="_compute_total_qtys", store=True)

    @api.depends('line_ids.product_qty', 'line_ids.ordered_qty', 'line_ids.accepted_qty')
    def _compute_total_qtys(self):
        for rec in self:
            rec.total_ordered_qty = sum(rec.line_ids.mapped('ordered_qty'))
            rec.total_accepted_qty = sum(rec.line_ids.mapped('accepted_qty'))

    @api.model
    def create(self, vals):

        pre_existing_bo = self.env['purchase.requisition'].search([
            ('vendor_id', '=', vals['vendor_id']),
            ('state', 'in', ['draft', 'ongoing']),
            ('prevent_line_addition', '=', False)
        ], limit=1)

        if pre_existing_bo:
            pre_existing_bo_total_qty = 0
            for line in pre_existing_bo.line_ids:
                pre_existing_bo_total_qty += line.product_qty

            current_bo_total_qty = 0
            for line in vals['line_ids']:
                current_bo_total_qty += line[2]['product_qty']

            qty_limit = self.env['res.partner'].browse(vals['vendor_id']).blanket_order_qty_limit

            if pre_existing_bo_total_qty + current_bo_total_qty <= qty_limit:
                pre_existing_bo.write({'line_ids': vals['line_ids']})
                return pre_existing_bo

        if not vals.get('name'):
            vals['name'] = self.env['ir.sequence'].with_company(self.company_id).next_by_code('purchase.requisition.blanket.order')

        return super(PurchaseRequisition, self).create(vals)

    def write(self, vals):

        updated = super(PurchaseRequisition, self).write(vals)

        if self.state == 'ongoing' and self.external_id:
            job_dto = JobDTO.from_odoo(self)
            data = DetrackService.update_collection_job(self.name, {"data": job_dto})

        return updated

    def send_to_dtrack(self):
        if not self.external_id:

            if not self.vendor_id:
                raise UserError("vendor is required")

            if not self.vendor_id.contact_address_complete:
                raise UserError("please fill vendor contact address, before sending the job to detrack")

            job_dto = JobDTO.from_odoo(self)
            data = DetrackService.create_collection_job({"data": job_dto})
            self.write({
                'external_id': data['data']['id'],
                'state': 'ongoing'
            })
        else:
            raise UserError("This Blanket order was already sent")