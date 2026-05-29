from odoo import api, models
from odoo.exceptions import UserError


class AttributeService:
    @staticmethod
    def get_attribute(env, mataa_id):
        attribute = env['product.attribute'].search([('mataa_id', '=', mataa_id)], limit=1)

        return attribute

    @staticmethod
    def create_attribute(env, name, mataa_id):
        existing_attribute = env['product.attribute'].search([('mataa_id', '=', mataa_id)], limit=1)

        if existing_attribute.exists():
            return existing_attribute

        attribute = env['product.attribute'].create({
            'name': name,
            'mataa_id': mataa_id,
            'is_synced': True
        })

        return attribute

    @staticmethod
    def get_attribute_value(env, attribute_mataa_id, mataa_id):
        attribute = AttributeService.get_attribute(env, attribute_mataa_id)
        if not attribute:
            raise UserError("attribute doesn't exists")

        attribute_value = env['product.attribute.value'].search([
            ('mataa_id', '=', mataa_id),
            ('attribute_id', '=', attribute.id)
        ], limit=1)

        return attribute_value

    @staticmethod
    def create_attribute_value(env, attribute_mataa_id, name, mataa_id):
        attribute = AttributeService.get_attribute(env, attribute_mataa_id)
        if not attribute:
            raise UserError("attribute doesn't exists")

        existing_attribute_value = env['product.attribute.value'].search([
            ('mataa_id', '=', mataa_id),
            ('attribute_id', '=', attribute.id)
        ], limit=1)

        if existing_attribute_value.exists():
            return existing_attribute_value

        attribute_value = env['product.attribute.value'].create({
            'name': name,
            'mataa_id': mataa_id,
            'attribute_id': attribute.id,
            'is_synced': True
        })

        return attribute_value
