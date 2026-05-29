from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    inventory_user_id = fields.Many2one(
        'res.users',
        string='Inventory User',
        config_parameter='mataa_inventory.inventory_user_id',
    )
