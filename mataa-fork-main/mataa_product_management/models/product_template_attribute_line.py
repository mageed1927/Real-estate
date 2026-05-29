from odoo import models, api, _
from odoo.exceptions import ValidationError


class ProductTemplateAttributeLine(models.Model):  # You need to inherit from models.Model
    _inherit = 'product.template.attribute.line'  # Inheriting the existing model

    _sql_constraints = [
        ("product_template_attribute_line_unique_product", "UNIQUE (product_tmpl_id, attribute_id)", "Attribute already added to the product"),
    ]

    def _get_restricted_attributes_ids(self):
        """Helper method to get restricted attribute IDs from settings."""
        return self.env.company.restricted_attribute_ids.ids

    @api.model
    def create(self, vals):
        """Override create to check for restricted attributes."""
        if 'attribute_id' in vals:
            restricted_ids = self._get_restricted_attributes_ids()
            if vals.get('attribute_id') in restricted_ids:
                attribute = self.env['product.attribute'].browse(vals.get('attribute_id'))
                error_msg = _("The attribute '%s' is restricted and cannot be added to products.") % attribute.name
                raise ValidationError(error_msg)
        return super(ProductTemplateAttributeLine, self).create(vals)

    def write(self, vals):
        """Override write to check if an attribute is being changed to a restricted one."""
        if 'attribute_id' in vals:
            restricted_ids = self._get_restricted_attributes_ids()
            if vals.get('attribute_id') in restricted_ids:
                attribute = self.env['product.attribute'].browse(vals.get('attribute_id'))
                error_msg = _("The attribute '%s' is restricted and cannot be assigned to products.") % attribute.name
                raise ValidationError(error_msg)
        return super(ProductTemplateAttributeLine, self).write(vals)

