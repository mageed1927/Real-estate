from odoo import api, models


class TagService:

    @staticmethod
    def assign_tags(env, product, tag_names):
        """Assign product tags to a template or variant"""
        tag_model = env['product.tag']
        tag_ids = []
        for tag_name in tag_names.split(','):
            tag = tag_model.search([('name', '=', tag_name.strip())], limit=1)
            if not tag:
                tag = tag_model.create({'name': tag_name.strip()})
            tag_ids.append(tag.id)
        product.write({'product_tag_ids': [(6, 0, tag_ids)]})
