from odoo import api, models


class AttributeService:

    @staticmethod
    def get_or_create_attribute(env, attribute_name):
        """Get or create a product attribute"""
        attribute = env['product.attribute'].sudo().search([('name', '=', attribute_name)], limit=1)
        if not attribute:
            attribute = env['product.attribute'].sudo().create({'name': attribute_name})
        return attribute

    @staticmethod
    def get_or_create_attribute_value(env, attribute, value_name):
        """Get or create a product attribute value"""
        attribute_value = env['product.attribute.value'].sudo().search([
            ('name', '=', value_name), ('attribute_id', '=', attribute.id)
        ], limit=1)
        if not attribute_value:
            attribute_value = env['product.attribute.value'].sudo().create({
                'name': value_name,
                'attribute_id': attribute.id
            })
        return attribute_value
