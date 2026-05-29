from odoo import models, api


class PreSyncMainWizard(models.TransientModel):
    _name = 'presync.main.wizard'
    _description = 'PreSync Main Wizard'

    @api.model
    def action_open_presync_attributes(self, *args):
        return {
            'name': 'PreSync Attributes',
            'type': 'ir.actions.act_window',
            'res_model': 'presync.attributes.wizard',
            'view_mode': 'form',
            'target': 'new',
        }

    @api.model
    def action_open_presync_brands(self, *args):
        return {
            'name': 'PreSync Brands',
            'type': 'ir.actions.act_window',
            'res_model': 'presync.brands.wizard',
            'view_mode': 'form',
            'target': 'new',
        }

    @api.model
    def action_open_presync_categories(self, *args):
        return {
            'name': 'PreSync Categories',
            'type': 'ir.actions.act_window',
            'res_model': 'presync.categories.wizard',
            'view_mode': 'form',
            'target': 'new',
        }

    @api.model
    def action_open_presync_vendors(self, *args):
        return {
            'name': 'PreSync Vendors',
            'type': 'ir.actions.act_window',
            'res_model': 'presync.vendors.wizard',
            'view_mode': 'form',
            'target': 'new',
        }

    @api.model
    def action_open_presync_customers(self, *args):
        return {
            'name': 'PreSync Customers',
            'type': 'ir.actions.act_window',
            'res_model': 'presync.customers.wizard',
            'view_mode': 'form',
            'target': 'new',
        }

    @api.model
    def action_open_presync_products(self, *args):
        return {
            'name': 'PreSync Products',
            'type': 'ir.actions.act_window',
            'res_model': 'presync.products.wizard',
            'view_mode': 'form',
            'target': 'new',
        }

    @api.model
    def action_open_presync_variants(self, *args):
        return {
            'name': 'PreSync Variants',
            'type': 'ir.actions.act_window',
            'res_model': 'presync.variants.wizard',
            'view_mode': 'form',
            'target': 'new',
        }


