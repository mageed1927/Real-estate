from odoo import models, fields, api, _
import logging
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    dms_shipment_id = fields.Char(
        string="DMS Shipment ID",
        copy=False,
        readonly=True,
        help="Shipment ID returned by DMS API"
    )
    dms_shipment_status = fields.Selection([
        ('pending', 'قيد الانتظار'),
        ('draft', 'مسودة'),
        ('sent', 'أرسلت إلى DMS'),
        ('shipping_request', 'طلب شحن'),
        ('in_warehouse', 'في المخزن'),
        ('on_delivery', 'قيد التوصيل'),
        ('delivered', 'تم التسليم'),
        ('partially_delivered', 'تم التسليم جزئياً'),
        ('fail_and_retry', 'اعادة محاولة تسليم'),
        ('out_returned', 'ارجاع للمرسل'),
        # ('out_returned', 'ارجاع للعميل'),
        ('cancelled', 'ملغي'),
    ], string="DMS Shipment Status", default='draft', copy=False, tracking=True)

    dms_collected_price = fields.Float(
        string="DMS Collected Price",
        readonly=True,
        copy=False,
        tracking=True,
        help="The amount collected by DMS from the customer."
    )

    dms_delegate_commission = fields.Float(
        string="DMS Delegate Commission",
        readonly=True,
        copy=False,
        tracking=True,
        help="The commission amount for the DMS delegate."
    )

    def button_validate(self):
        result = super().button_validate()

        for picking in self:
            if (picking.picking_type_code == 'outgoing' and
                    picking.carrier_id and
                    picking.carrier_id.delivery_type == 'dms' and
                    not picking.dms_shipment_id):

                try:
                    _logger.info(f"Creating DMS shipment for picking {picking.name}")

                    picking.carrier_id.dms_send_shipping(picking)
                    picking.dms_shipment_status = 'sent'

                    _logger.info(f"DMS shipment created successfully for picking {picking.name}")

                except Exception as e:
                    _logger.error(f"Failed to create DMS shipment for picking {picking.name}: {str(e)}")
                    picking.message_post(
                        body=_("Failed to create DMS shipment: %s") % str(e),
                        message_type='comment'
                    )

        return result

    def action_create_dms_shipment(self):
        self.ensure_one()

        if not self.carrier_id or self.carrier_id.delivery_type != 'dms':
            raise UserError(_('This picking does not use DMS delivery carrier.'))

        if self.dms_shipment_id:
            raise UserError(_('DMS shipment already exists for this picking.'))

        if self.state not in ['assigned', 'done']:
            raise UserError(_('Picking must be ready or done to create DMS shipment.'))

        try:
            self.carrier_id.dms_send_shipping(self)
            self.dms_shipment_status = 'sent'
            self.message_post(
                body=_("DMS shipment created successfully with ID: %s") % self.dms_shipment_id,
                message_type='notification'
            )
        except Exception as e:
            raise UserError(_('Failed to create DMS shipment: %s') % str(e))

    def write(self, vals):
        """
        Intercepts the write call to check for DMS status changes and trigger
        the sale order finalization (invoicing and payment and shipment bill).
        """
        res = super(StockPicking, self).write(vals)

        if 'dms_shipment_status' in vals or 'dms_collected_price' in vals:
            for pick in self.filtered(
                    lambda p: p.picking_type_code == 'outgoing' and p.carrier_id.delivery_type == 'dms'):

                so_id = pick.sale_id or pick.group_id.sale_id

                if not so_id or so_id.is_handled:
                    continue


                is_delivered = (pick.dms_shipment_status == 'delivered')
                price_matches = (pick.dms_collected_price == so_id.amount_total)


                if is_delivered and price_matches:
                    try:
                        so_id.close_fully_delivered_order()

                        if not (so_id.is_refund_order or so_id.is_replacement_order):
                            _logger.info(f"SO {so_id.name}: Finalizing standard order.")
                            so_id.finalize_mataa_order()
                        else:
                            _logger.info(f"SO {so_id.name}: Shipment delivered. Finalization skipped (RO/Replacement).")
                            pick.message_post(
                                body=_(
                                    "DMS status is 'Delivered'. Shipment status updated. (Skipped Auto-Finalize for RO)")
                            )

                    except Exception as e:
                        _logger.error(f"Failed to finalize SO {so_id.name} for picking {pick.name}: {e}")
                        so_id.message_post(
                            body=_("Failed to auto-finalize order after DMS delivery: %s") % e
                        )


        return res
