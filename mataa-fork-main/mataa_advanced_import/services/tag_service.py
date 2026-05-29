from odoo import api, models


class TagService:

    @staticmethod
    def assign_tags(env, product, tag_names):
        """Assign product tags to a template or variant"""
        tag_model = env['product.tag'].sudo()

        tag_names = {tag_name.strip() for tag_name in tag_names.split(',') if tag_name.strip()}

        if not tag_names:
            return  # No valid tags provided

        # Search for existing tags in one batch query
        existing_tags = tag_model.sudo().search([('name', 'in', list(tag_names))])
        existing_tag_names = set(existing_tags.mapped('name'))

        new_tag_names = tag_names - existing_tag_names
        new_tags = tag_model.create([{'name': name} for name in new_tag_names])

        all_tag_ids = existing_tags.ids + new_tags.ids

        product.sudo().write({'product_tag_ids': [(6, 0, all_tag_ids)]})