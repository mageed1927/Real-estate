from odoo import api, models
from odoo.exceptions import UserError


class CategoryService:

    @staticmethod
    def get_func_category(env, category_name):
        domain = [('name', '=', category_name)]

        category = env['product.category'].search(domain, limit=1)

        return category

    @staticmethod
    def get_web_category(env, category_name, mataa_id=None):
        domain = [('name', '=', category_name)]

        if mataa_id:
            domain.append(('mataa_id', '=', mataa_id))

        category = env['product.public.category'].search(domain, limit=1)

        return category

    @staticmethod
    def create_web_category(env, name, mataa_id, mataa_parent_id=None):
        existing_category = category = env['product.public.category'].search([('mataa_id', '=', mataa_id)], limit=1)

        if existing_category.exists():
            return existing_category

        parent_id = None
        if mataa_parent_id:
            parent_category = env['product.public.category'].search([('mataa_id', '=', mataa_parent_id)], limit=1)
            if not parent_category:
                raise UserError("parent_category doesn't exists")

            parent_id = parent_category.id

        category = env['product.public.category'].create({
            'name': name,
            'mataa_id': mataa_id,
            'parent_id': parent_id,
            'is_synced': True
        })

        return category

    @staticmethod
    def assign_public_categories(env, product_template, web_categories):
        """Assign categories (both web and functional) to the product template"""
        if web_categories:
            web_cat_ids = [cat.id for cat in web_categories]
            product_template.write({'public_categ_ids': [(6, 0, web_cat_ids)]})
