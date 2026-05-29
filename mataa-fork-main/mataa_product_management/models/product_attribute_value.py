from odoo import models, fields, api

class ProductAttributeValue(models.Model):
    _inherit = 'product.attribute.value'

    # New field to compute the number of products
    products_count = fields.Integer(
        string="Products Count",
        compute='_compute_products_count',
        # We don't need to store this value in the database
        # It will be computed every time it's displayed
    )

    def _compute_products_count(self):
        """
        This method computes the number of product templates
        associated with each attribute value.
        """
        for value in self:
            # Domain to search for all products that have this value
            domain = [('attribute_line_ids.value_ids', 'in', value.id)]
            # search_count is faster than search() followed by len()
            value.products_count = self.env['product.template'].search_count(domain)

    def action_view_related_products(self):
        """
        When called, this method returns an action
        that opens a view of the related products.
        """
        self.ensure_one()
        return {
            'name': f"Products related to: {self.name}",
            'type': 'ir.actions.act_window',
            'res_model': 'product.template',
            'view_mode': 'tree,form',
            'domain': [('attribute_line_ids.value_ids', 'in', self.id)],
            'target': 'current',
        }